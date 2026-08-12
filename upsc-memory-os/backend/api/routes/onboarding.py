"""Onboarding — 3 steps, none skippable."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.dependencies import get_current_user, get_db
from core.database import User, UserTopicProfile, UrgencyCache, Topic
from models.schemas import OnboardingExamDate, OnboardingSubjects
from models.enums import TopicType

router = APIRouter(prefix="/api/v1/onboarding", tags=["Onboarding"])

# Use the canonical TopicType enum for validation
VALID_TOPIC_TYPES = [t.value for t in TopicType]


@router.post("/exam-date")
async def set_exam_date(
    body: OnboardingExamDate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Step 1: Store exam date. Return days remaining."""
    user.exam_date = body.exam_date
    await db.commit()

    # Use UTC to be consistent with the rest of the codebase
    days_remaining = (body.exam_date - datetime.now(timezone.utc).date()).days

    return {
        "exam_date": body.exam_date.isoformat(),
        "days_remaining": max(days_remaining, 0),
    }


@router.post("/subjects")
async def set_weak_subjects(
    body: OnboardingSubjects,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 2: Multi-select weak subjects.
    Pre-seeds user_topic_profiles and urgency_cache so dashboard
    is not empty on first login.
    Uses upsert pattern to prevent duplicates on repeated calls.
    """
    selected = [s for s in body.weak_subjects if s in VALID_TOPIC_TYPES]
    if not selected:
        raise HTTPException(status_code=400, detail="Select at least one subject")

    topics_created = []

    for topic_type in selected:
        # ── Upsert UserTopicProfile (prevent duplicates) ─────────
        existing_profile = await db.execute(
            select(UserTopicProfile).where(
                UserTopicProfile.user_id == user.id,
                UserTopicProfile.topic_type == topic_type,
            )
        )
        if not existing_profile.scalar_one_or_none():
            profile = UserTopicProfile(
                user_id=user.id,
                topic_type=topic_type,
                decay_multiplier=1.0,
                interaction_count=0,
                importance_weight=0.7,  # Weak subjects get higher priority
            )
            db.add(profile)

        # ── Upsert Topic (prevent duplicates) ────────────────────
        existing_topic = await db.execute(
            select(Topic).where(
                Topic.name == topic_type.replace("_", " ").title(),
                Topic.topic_type == topic_type,
            )
        )
        topic = existing_topic.scalar_one_or_none()
        if not topic:
            topic = Topic(
                name=topic_type.replace("_", " ").title(),#this converts "current_affairs" into "Current Affairs" for better display in the UI. We can have a mapping dict if we want more control, but this simple transformation works for our predefined topic types.
                topic_type=topic_type,
            )
            db.add(topic)
            await db.flush()  # get topic.id

        # ── Upsert UrgencyCache (prevent duplicates) ─────────────
        existing_cache = await db.execute(
            select(UrgencyCache).where(
                UrgencyCache.user_id == user.id,
                UrgencyCache.topic_id == topic.id,
            )
        )
        if not existing_cache.scalar_one_or_none():
            cache = UrgencyCache(
                user_id=user.id,
                topic_id=topic.id,
                urgency_score=0.2,  # MEDIUM tier
                urgency_tier="MEDIUM",
            )
            db.add(cache)

        topics_created.append(topic_type)

    await db.commit()

    return {
        "subjects_selected": topics_created,
        "profiles_created": len(topics_created),
    }


@router.post("/complete")
async def complete_onboarding(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Step 3: Called after first PDF upload + first question answered.
    Sets onboarding_done=true.
    """
    user.onboarding_done = True
    await db.commit()

    return {"onboarding_done": True}
