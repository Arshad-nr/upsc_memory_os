"""
Fact deprecation — runs after every new document upload.
Cross-references new chunks against existing flashcards.
Two-tier: embedding similarity filter → LLM conflict detection.
"""

from core.vector_store import embed_dense
import json
from services.llm import call_gemini_flash

VOLATILE_TYPES = [
    "current_affairs",
    "government_schemes",
    "reports_indices",
    "economy",
]


async def check_fact_deprecation(
    new_chunks: list[dict],
    user_id: str,
    db,
):
    """
    Cross-reference new chunks against existing flashcards.
    Only checks volatile topic types where facts change.
    """
    from sqlalchemy import select
    from core.database import Flashcard
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    # Get active flashcards for volatile types
    result = await db.execute(
        select(Flashcard).where(
            Flashcard.user_id == user_id,
            Flashcard.deprecated == False,
            Flashcard.card_type.in_(["flashcard", "mcq"]),
        )
    )
    existing = result.scalars().all()

    # Filter to volatile topic types only
    volatile_cards = []
    for card in existing:
        if card.topic_type in VOLATILE_TYPES if hasattr(card, "topic_type") else True:
            volatile_cards.append({
                "id": str(card.id),
                "question": card.question,
                "answer": card.answer,
            })

    if not volatile_cards or not new_chunks:
        return

    # Fully vectorize: Batch embed both chunks and cards at once
    from core.vector_store import embed_dense_batch
    
    chunk_texts = [c["content"] for c in new_chunks]
    chunk_embeddings = embed_dense_batch(chunk_texts)
    
    card_texts = [card["answer"] for card in volatile_cards]
    card_embeddings = embed_dense_batch(card_texts)

    # Perform a single M x N matrix multiplication in C
    # Returns a matrix where row i corresponds to card i, and col j is chunk j
    similarity_matrix = cosine_similarity(card_embeddings, chunk_embeddings)

    for i, card in enumerate(volatile_cards):
        # Extract the similarities for this specific card against all chunks
        similarities = similarity_matrix[i]
        
        candidates = []
        for j, sim in enumerate(similarities):
            sim_val = float(sim)
            if sim_val > 0.75:
                # Store tuple of (similarity, chunk) so we can sort
                candidates.append((sim_val, new_chunks[j]))

        if not candidates:
            continue

        # Sort candidates by highest similarity score first
        candidates.sort(key=lambda x: x[0], reverse=True)
        # Take the actual chunk dicts for the top 3 most similar matches
        top_candidates = [c[1] for c in candidates[:3]]

        # Tier 2: LLM conflict check only on similar candidates
        prompt = f"""Does any new fact contradict or update this flashcard?
Return a raw JSON object (no markdown formatting):
{{"conflict": true/false,
  "type": "contradiction|update|none",
  "new_answer": "updated answer (empty if no conflict)",
  "reason": "brief explanation"}}

Flashcard Q: {card["question"]}
Flashcard A: {card["answer"]}

New facts:
{[c["content"][:300] for c in top_candidates]}"""

        result_text = await call_gemini_flash(prompt)
        try:
            result = json.loads(result_text)
        except json.JSONDecodeError:
            result = {}

        if result.get("conflict"):
            await _deprecate_flashcard(db, card["id"], result.get("reason", ""))
            print(f"[Deprecation] Deprecated flashcard {card['id']}: {result.get('reason')}")


async def _deprecate_flashcard(db, flashcard_id: str, reason: str):
    """Mark a flashcard as deprecated."""
    from sqlalchemy import update
    from core.database import Flashcard
    from datetime import datetime, timezone
    import uuid

    await db.execute(
        update(Flashcard)
        .where(Flashcard.id == uuid.UUID(flashcard_id))
        .values(
            deprecated=True,
            deprecated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            deprecation_reason=reason,
        )
    )
    await db.commit()
