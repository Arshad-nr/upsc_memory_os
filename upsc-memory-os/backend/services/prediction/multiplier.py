"""Personal multiplier update logic."""

from services.prediction.scoring import update_personal_multiplier


async def update_multiplier_after_quiz(
    db,
    user_id: str,
    topic_type: str,
    predicted_retention: float,
    actual_accuracy: float,
):
    """
    Update the personal decay multiplier after a quiz answer.
    Called from quiz answer submission.
    """
    from sqlalchemy import select
    from core.database import UserTopicProfile
    import uuid
    from datetime import datetime, timezone

    result = await db.execute(
        select(UserTopicProfile).where(
            UserTopicProfile.user_id == uuid.UUID(user_id),
            UserTopicProfile.topic_type == topic_type,
        )
    )
    profile = result.scalar_one_or_none()

    if profile is None:
        # Create profile if it doesn't exist
        profile = UserTopicProfile(
            user_id=uuid.UUID(user_id),
            topic_type=topic_type,
            decay_multiplier=1.0,
            interaction_count=0,
        )
        db.add(profile)
        # No need to commit yet; we will update and commit below

    # Update multiplier
    new_multiplier = update_personal_multiplier(
        profile.decay_multiplier,
        predicted_retention,
        actual_accuracy,
    )
    #modifing the profile with the new multiplier and incrementing interaction count changes the db also (ORM will track the changes and update on commit)
    profile.decay_multiplier = new_multiplier
    profile.interaction_count += 1
    # Ensure last_updated is explicitly updated with a naive UTC datetime
    profile.last_updated = datetime.now(timezone.utc).replace(tzinfo=None)
    
    await db.commit()

    return new_multiplier