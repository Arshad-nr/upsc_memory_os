"""Revision dashboard + session endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from api.dependencies import get_current_user, get_db
from core.database import User, UrgencyCache, Topic

router = APIRouter(prefix="/api/v1/revision", tags=["Revision"])


from models.schemas import DashboardResponse

@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Topics ranked by urgency_score, grouped into tier sections."""
    if not user.exam_date:
        raise HTTPException(status_code=400, detail="Exam date not set. Complete onboarding first.")

    result = await db.execute(
        select(UrgencyCache, Topic)
        .join(Topic, UrgencyCache.topic_id == Topic.id)
        .where(UrgencyCache.user_id == user.id)
        .order_by(UrgencyCache.urgency_score.desc())
    )
    rows = result.all()

    days_remaining = (user.exam_date - datetime.now(timezone.utc).date()).days

    items = []
    for cache, topic in rows:
        items.append({
            "topic_id": str(cache.topic_id),
            "topic_name": topic.name,
            "topic_type": topic.topic_type,
            "urgency_score": round(cache.urgency_score, 4),
            "urgency_tier": cache.urgency_tier,
            "computed_at": cache.computed_at.isoformat() if cache.computed_at else None,
        })

    # Group into tier sections for the frontend
    critical = [i for i in items if i.get("urgency_tier") in ("CRITICAL", "HIGH")]
    stable = [i for i in items if i.get("urgency_tier") not in ("CRITICAL", "HIGH")]

    return {
        "items": items,
        "critical": critical,
        "stable": stable,
        "days_remaining": max(days_remaining, 0),
        "total_topics": len(items),
    }


@router.get("/session")
async def get_revision_session(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get 10 interleaved revision items, CRITICAL first.
    Max 3 items from the same topic_type to prevent monotony.
    """
    result = await db.execute(
        select(UrgencyCache, Topic)
        .join(Topic, UrgencyCache.topic_id == Topic.id)
        .where(UrgencyCache.user_id == user.id)
        .order_by(UrgencyCache.urgency_score.desc())
    )
    rows = result.all()

    type_counts: dict[str, int] = {}
    selected = []

    for cache, topic in rows:
        tt = topic.topic_type
        if type_counts.get(tt, 0) >= 3:
            continue
        type_counts[tt] = type_counts.get(tt, 0) + 1
        selected.append({
            "topic_id": str(cache.topic_id),
            "topic_name": topic.name,
            "topic_type": topic.topic_type,
            "urgency_score": round(cache.urgency_score, 4),
            "urgency_tier": cache.urgency_tier,
        })
        if len(selected) >= 10:
            break

    return {"items": selected, "count": len(selected)}
