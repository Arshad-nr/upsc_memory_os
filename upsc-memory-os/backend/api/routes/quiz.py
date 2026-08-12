"""Quiz session + answer submission endpoints."""

import uuid
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from api.dependencies import get_current_user, get_db
from core.database import (
    User, Flashcard, StudySession, RevisionEvent,
    Chunk, Topic, UrgencyCache,
)
from services.flashcards.evaluator import evaluate_answer
from services.flashcards.generator import generate_cards_for_topic
from models.schemas import QuizSessionRequest, QuizAnswerRequest, QuizAnswerResponse
from services.prediction.scoring import (
    days_since_valid_revision,
    weighted_accuracy,
    DECAY_CONSTANTS,
    DIFFICULTY_MULTIPLIER,
)
from models.enums import TopicType, Difficulty

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/quiz", tags=["Quiz"])


# ── Topic Discovery ─────────────────────────────────────────────────
@router.get("/topics")
async def get_quiz_topics(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all topic_names the user has content for, grouped by topic_type."""
    result = await db.execute(
        select(Chunk.topic_type, Chunk.topic_name)
        .where(
            Chunk.user_id == user.id,
            Chunk.topic_name.isnot(None),
            Chunk.topic_name != "Unknown",
        )
        .distinct()
    )
    rows = result.all()

    grouped: dict[str, list[str]] = {}
    for topic_type, topic_name in rows:
        tt = topic_type or "static_syllabus"
        if tt not in grouped:
            grouped[tt] = []
        if topic_name not in grouped[tt]:
            grouped[tt].append(topic_name)

    # Sort topic names alphabetically within each type
    for tt in grouped:
        grouped[tt].sort()

    return {"topics": grouped}


# ── Stats ────────────────────────────────────────────────────────────
@router.get("/stats")
async def get_quiz_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return card counts grouped by topic_type and card_type."""
    result = await db.execute(
        select(Flashcard).where(
            Flashcard.user_id == user.id,
            Flashcard.deprecated == False,
        )
    )
    all_cards = result.scalars().all()

    total_flashcards = 0
    total_mcqs = 0
    topic_breakdown: dict[str, dict] = {}

    # Pre-fetch all chunks referenced by these flashcards
    chunk_ids = [c.chunk_id for c in all_cards if c.chunk_id]
    chunk_map: dict[uuid.UUID, dict] = {}
    if chunk_ids:
        chunk_result = await db.execute(
            select(Chunk).where(Chunk.id.in_(chunk_ids))
        )
        for chunk in chunk_result.scalars().all():
            chunk_map[chunk.id] = {
                "topic_type": chunk.topic_type or "unknown",
                "topic_name": chunk.topic_name or "Unknown",
            }

    for card in all_cards:
        ct = card.card_type or "flashcard"
        info = chunk_map.get(card.chunk_id, {"topic_type": "unknown", "topic_name": "Unknown"})
        tt = info["topic_type"]

        if ct == "mcq":
            total_mcqs += 1
        else:
            total_flashcards += 1

        if tt not in topic_breakdown:
            topic_breakdown[tt] = {
                "topicType": tt,
                "topicName": tt.replace("_", " ").title(),
                "flashcards": 0,
                "mcqs": 0,
            }
        if ct == "mcq":
            topic_breakdown[tt]["mcqs"] += 1
        else:
            topic_breakdown[tt]["flashcards"] += 1

    return {
        "totalFlashcards": total_flashcards,
        "totalMcqs": total_mcqs,
        "topicBreakdown": list(topic_breakdown.values()),
    }


# ── Quiz Session ─────────────────────────────────────────────────────
@router.post("/session")
async def create_quiz_session(
    body: QuizSessionRequest = QuizSessionRequest(),
    card_type: str = None,
    topic_type: str = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a quiz session.
    Supports filtering by:
      - body.topic_ids: list of Topic UUIDs (multi-select topic names)
      - topic_type query param: broad topic type string
      - Neither: returns cards across all topics prioritized by urgency
    """
    session = StudySession(user_id=user.id, item_count=0)
    db.add(session)
    await db.commit()
    await db.refresh(session)

    query = (
        select(Flashcard)
        .where(
            Flashcard.user_id == user.id,
            Flashcard.deprecated == False,
        )
    )

    if card_type:
        query = query.where(Flashcard.card_type == card_type)

    # Filter by specific topic IDs (multi-select topic names)
    if body.topic_ids:
        query = query.where(Flashcard.topic_id.in_(body.topic_ids))

    result = await db.execute(query)
    all_cards = result.scalars().all()

    if not all_cards:
        return {
            "sessionId": str(session.id),
            "items": [],
            "message": "No flashcards available. Upload a document and generate flashcards first.",
        }

    # Pre-fetch chunks to resolve topic_type for filtering
    chunk_ids = [c.chunk_id for c in all_cards if c.chunk_id]
    chunk_topic_map: dict[uuid.UUID, str] = {}
    if chunk_ids:
        chunk_result = await db.execute(
            select(Chunk).where(Chunk.id.in_(chunk_ids))
        )
        for chunk in chunk_result.scalars().all():
            chunk_topic_map[chunk.id] = chunk.topic_type or "unknown"

    # Filter by topic_type if specified (and no topic_ids were given)
    filtered_cards = []
    for card in all_cards:
        tt = chunk_topic_map.get(card.chunk_id, "unknown") if card.chunk_id else "unknown"
        card.resolved_topic_type = tt

        if topic_type and not body.topic_ids and tt != topic_type:
            continue
        filtered_cards.append(card)

    if not filtered_cards:
        return {
            "sessionId": str(session.id),
            "items": [],
            "message": f"No flashcards available for topic: {topic_type}",
        }

    # Sort by urgency (highest first)
    urgency_map = {}
    urgency_result = await db.execute(
        select(UrgencyCache).where(UrgencyCache.user_id == user.id)
    )
    for cache in urgency_result.scalars().all():
        urgency_map[str(cache.topic_id)] = cache.urgency_score

    sorted_cards = sorted(
        filtered_cards,
        key=lambda c: urgency_map.get(str(c.topic_id), 0.0),
        reverse=True,
    )

    selected = sorted_cards[:body.size]
    session.item_count = len(selected)
    await db.commit()

    return {
        "sessionId": str(session.id),
        "items": [
            {
                "flashcardId": str(card.id),
                "question": card.question,
                "answer": card.answer,
                "cardType": card.card_type,
                "difficulty": card.llm_difficulty,
                "topicType": getattr(card, "resolved_topic_type", "unknown"),
            }
            for card in selected
        ],
    }


# ── Answer Submission ────────────────────────────────────────────────
@router.post("/answer", response_model=QuizAnswerResponse)
async def submit_answer(
    body: QuizAnswerRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit an answer → evaluate → log revision event → update multiplier."""
    card_result = await db.execute(
        select(Flashcard).where(
            Flashcard.id == body.flashcard_id,
            Flashcard.user_id == user.id,
        )
    )
    card = card_result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    eval_result = await evaluate_answer(
        question=card.question,
        correct_answer=card.answer,
        user_answer=body.answer,
    )

    from models.enums import ErrorType, ERROR_TYPE_CONFIG

    if eval_result["correct"]:
        error_type = ErrorType.CORRECT
    elif body.error_type:
        error_type = body.error_type
    else:
        error_type = ErrorType.PARTIAL_RECALL

    cfg = ERROR_TYPE_CONFIG.get(error_type, {"anchor": 1.0, "alpha": 0.0})
    raw_score = eval_result["score"]
    adjusted_score = (1 - cfg["alpha"]) * raw_score + cfg["alpha"] * cfg["anchor"]

    event = RevisionEvent(
        user_id=user.id,
        topic_id=card.topic_id,
        flashcard_id=card.id,
        accuracy_score=adjusted_score,
        error_type=error_type.value,
        time_spent_sec=body.time_spent_sec,
        session_id=body.session_id if body.session_id else None,
        revised_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(event)

    card.last_shown_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()

    # Update personal multiplier
    if card.topic_id:
        from services.prediction.multiplier import update_multiplier_after_quiz
        topic_result = await db.execute(
            select(Topic).where(Topic.id == card.topic_id)
        )
        topic = topic_result.scalar_one_or_none()
        if topic:
            rev_result = await db.execute(
                select(RevisionEvent).where(
                    RevisionEvent.user_id == user.id,
                    RevisionEvent.topic_id == card.topic_id,
                )
            )
            rev_events = rev_result.scalars().all()

            revision_history = [
                {"revised_at": r.revised_at, "accuracy_score": r.accuracy_score}
                for r in rev_events
                if r.revised_at is not None
            ]

            now_utc = datetime.now(timezone.utc)
            scores_with_dates = [
                (
                    r.accuracy_score or 0.5,
                    max((now_utc - (r.revised_at.replace(tzinfo=timezone.utc)
                          if r.revised_at.tzinfo is None else r.revised_at)).total_seconds() / 86400, 0),
                )
                for r in rev_events
                if r.revised_at is not None and r.accuracy_score is not None
            ]

            days_since = days_since_valid_revision(revision_history)
            acc = weighted_accuracy(scores_with_dates)

            try:
                topic_type_enum = TopicType(topic.topic_type)
            except ValueError:
                topic_type_enum = None
            base_decay = DECAY_CONSTANTS.get(topic_type_enum, 7.0)

            try:
                diff_enum = Difficulty(card.llm_difficulty)
            except ValueError:
                diff_enum = Difficulty.MEDIUM
            diff_mult = DIFFICULTY_MULTIPLIER.get(diff_enum, 1.0)
            final_decay = max(base_decay * diff_mult, 0.1)

            predicted_retention = max(0.0, min(1.0,
                1.0 - (days_since / final_decay) * (1.1 - acc)
            ))

            await update_multiplier_after_quiz(
                db=db,
                user_id=str(user.id),
                topic_type=topic.topic_type,
                predicted_retention=predicted_retention,
                actual_accuracy=adjusted_score,
            )

    error_options = None
    if not eval_result["correct"]:
        error_options = [
            {"value": "complete_blank",   "label": "I had no idea"},
            {"value": "confused_similar", "label": "I confused it with something"},
            {"value": "partial_recall",   "label": "I partially remembered"},
            {"value": "careless_mistake", "label": "Careless mistake"},
        ]

    return QuizAnswerResponse(
        correct=eval_result["correct"],
        score=adjusted_score,
        feedback=eval_result["feedback"],
        error_type=error_type.value,
        error_type_options=error_options,
    )


# ── Flashcard Generation ─────────────────────────────────────────────
@router.post("/flashcards/generate")
async def generate_flashcards_endpoint(
    topic_id: str = None,
    topic_type: str = None,
    topic_names: str = None,  # Comma-separated topic names for multi-select
    limit: int = 5,
    offset: int = 0,
    randomize: bool = True,
    card_type: str = "flashcard",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate flashcards for a topic using batched structured outputs."""
    query = select(Chunk).where(Chunk.user_id == user.id)

    # Priority: topic_names > topic_type > topic_id
    if topic_names:
        names_list = [n.strip() for n in topic_names.split(",") if n.strip()]
        if names_list:
            query = query.where(Chunk.topic_name.in_(names_list))
            # Also filter by topic_type if provided (for safety)
            if topic_type:
                query = query.where(Chunk.topic_type == topic_type)

    elif topic_type:
        ownership_check = await db.execute(
            select(func.count()).select_from(Chunk).where(
                Chunk.user_id == user.id,
                Chunk.topic_type == topic_type,
            )
        )
        if ownership_check.scalar() == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No content found for topic '{topic_type}'. Upload a document for this topic first.",
            )
        query = query.where(Chunk.topic_type == topic_type)

    elif topic_id:
        topic_result = await db.execute(
            select(Topic).where(Topic.id == uuid.UUID(topic_id))
        )
        topic = topic_result.scalar_one_or_none()
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")
        query = query.where(Chunk.topic_type == topic.topic_type)

    if randomize:
        query = query.order_by(func.random())
    else:
        query = query.offset(offset)
        
    query = query.limit(limit)

    result = await db.execute(query)
    chunks = result.scalars().all()

    if not chunks:
        return {"cards": [], "message": "No chunks found for this topic"}

    chunk_dicts = [
        {
            "chunk_id": chunk.id,
            "content": chunk.content,
            "topic_type": chunk.topic_type,
            "topic_name": chunk.topic_name,
        }
        for chunk in chunks
    ]

    try:
        cards_data = await generate_cards_for_topic(
            chunk_dicts, count=limit, card_type=card_type
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    saved_cards = []
    save_errors = []
    for card in cards_data:
        try:
            # Resolve topic_id from the chunk's topic_name + topic_type
            chunk_id = card.get("chunk_id")
            resolved_topic_id = None
            if chunk_id:
                # Find the chunk to get its topic info
                matching_chunk = next((c for c in chunks if c.id == chunk_id), None)
                if matching_chunk and matching_chunk.topic_name:
                    topic_result = await db.execute(
                        select(Topic).where(
                            Topic.name == matching_chunk.topic_name,
                            Topic.topic_type == (matching_chunk.topic_type or "static_syllabus"),
                        )
                    )
                    found_topic = topic_result.scalar_one_or_none()
                    if found_topic:
                        resolved_topic_id = found_topic.id

            answer_val = card.get("answer", "")
            if card_type == "mcq":
                answer_val = json.dumps({
                    "correct": card.get("correct", "A"),
                    "options": card.get("options", {}),
                    "explanation": card.get("explanation", "")
                })

            fc = Flashcard(
                user_id=user.id,
                chunk_id=card["chunk_id"],
                topic_id=resolved_topic_id,
                question=card.get("question", ""),
                answer=answer_val,
                card_type=card_type,
                llm_difficulty=card.get("difficulty", "medium"),
            )
            db.add(fc)
            saved_cards.append(card)
        except Exception as e:
            logger.error(
                "[Generate] Failed to save card for topic_id=%s, chunk_id=%s: %s",
                topic_id,
                card.get("chunk_id", "unknown"),
                e,
                exc_info=True,
            )
            save_errors.append({
                "chunk_id": str(card.get("chunk_id", "unknown")),
                "error": str(e),
            })
            continue

    await db.commit()

    response = {"cards": saved_cards, "count": len(saved_cards)}
    if save_errors:
        response["partial_errors"] = save_errors
        response["message"] = f"{len(save_errors)} card(s) failed to save"
    return response
