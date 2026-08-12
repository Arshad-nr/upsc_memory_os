"""APScheduler background jobs — daily urgency rescore."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


async def daily_urgency_rescore():
    """
    Recompute urgency scores for all topics.
    Pre-computed so dashboard loads instantly.
    Runs daily at 11:45 PM.
    Optimized: Uses bulk queries to prevent N+1 performance hangs.
    Scoped: Only scores topics that belong to each user's own documents.
    """
    from core.database import async_session_maker, User, Topic, Chunk, UrgencyCache
    from core.database import RevisionEvent, UserTopicProfile, TopicTypeStat
    from services.prediction.scoring import final_urgency_score, classify_urgency
    from models.enums import TopicType, Difficulty
    from sqlalchemy import select, delete
    from datetime import datetime, timezone

    async with async_session_maker() as db:
        # Get all users
        result = await db.execute(select(User))
        users = result.scalars().all()
        if not users:
            print("[Rescore] No users found, skipping")
            return

        # Fetch global TopicTypeStats in bulk
        result = await db.execute(select(TopicTypeStat))
        all_stats = result.scalars().all()
        stats_map = {s.topic_type: s for s in all_stats}

        # Get all topics indexed by name for fast lookup
        result = await db.execute(select(Topic))
        all_topics = result.scalars().all()
        topic_by_name = {}
        for t in all_topics:
            topic_by_name[t.name] = t

        count = 0
        for user in users:
            # ── KEY FIX: Only get topic_names from THIS user's chunks ──
            result = await db.execute(
                select(Chunk.topic_name).where(
                    Chunk.user_id == user.id,
                    Chunk.topic_name.is_not(None)
                ).distinct()
            )
            user_topic_names = {row[0] for row in result.all()}

            # Filter to only topics this user owns
            user_topics = [topic_by_name[name] for name in user_topic_names if name in topic_by_name]

            if not user_topics:
                continue

            # Fetch user profiles in bulk
            result = await db.execute(select(UserTopicProfile).where(UserTopicProfile.user_id == user.id))
            profiles = result.scalars().all()
            profile_map = {p.topic_type: p for p in profiles}

            # Fetch all user revision events in bulk
            result = await db.execute(
                select(RevisionEvent)
                .where(RevisionEvent.user_id == user.id)
                .order_by(RevisionEvent.revised_at)
            )
            events = result.scalars().all()
            history_map = {}
            for e in events:
                if e.topic_id not in history_map:
                    history_map[e.topic_id] = []
                history_map[e.topic_id].append(e)

            # Fetch existing UrgencyCache in bulk
            result = await db.execute(select(UrgencyCache).where(UrgencyCache.user_id == user.id))
            caches = result.scalars().all()
            cache_map = {c.topic_id: c for c in caches}

            # Clean up stale UrgencyCache entries for topics this user no longer owns
            user_topic_ids = {t.id for t in user_topics}
            stale_cache_ids = [c.topic_id for c in caches if c.topic_id not in user_topic_ids]
            if stale_cache_ids:
                await db.execute(
                    delete(UrgencyCache).where(
                        UrgencyCache.user_id == user.id,
                        UrgencyCache.topic_id.in_(stale_cache_ids)
                    )
                )

            for topic in user_topics:
                events_for_topic = history_map.get(topic.id, [])

                history = [
                    {"revised_at": e.revised_at, "accuracy_score": e.accuracy_score}
                    for e in events_for_topic
                    if e.revised_at is not None
                ]

                now = datetime.now(timezone.utc)
                scores_with_dates = []
                for e in events_for_topic:
                    if e.accuracy_score is not None and e.revised_at is not None:
                        revised_at = e.revised_at
                        if revised_at.tzinfo is None:
                            revised_at = revised_at.replace(tzinfo=timezone.utc)
                        scores_with_dates.append((e.accuracy_score, (now - revised_at).days))

                # Get personal profile
                profile = profile_map.get(topic.topic_type)
                interaction_count = profile.interaction_count if profile else 0
                stored_multiplier = profile.decay_multiplier if profile else 1.0
                importance_weight = profile.importance_weight if profile else 0.5

                # Get population stats
                stats = stats_map.get(topic.topic_type)
                pop_observed = stats.decay_constant if stats else None
                pop_sample = stats.sample_count if stats else 0

                # Compute urgency score
                score = final_urgency_score(
                    topic_type=TopicType(topic.topic_type),
                    exam_date=datetime.combine(user.exam_date, datetime.min.time()),
                    revision_history=history,
                    scores_with_dates=scores_with_dates,
                    interaction_count=interaction_count,
                    stored_multiplier=stored_multiplier,
                    pop_observed_decay=pop_observed,
                    pop_sample_count=pop_sample,
                    card_difficulty=Difficulty.MEDIUM,
                    global_wrong_rate=None,
                    topic_id=str(topic.id),
                    importance_weight=importance_weight,
                )

                tier = classify_urgency(score)
                cache_entry = cache_map.get(topic.id)

                if cache_entry:
                    cache_entry.urgency_score = score
                    cache_entry.urgency_tier = tier
                    cache_entry.computed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                else:
                    cache_entry = UrgencyCache(
                        user_id=user.id,
                        topic_id=topic.id,
                        urgency_score=score,
                        urgency_tier=tier,
                        computed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                    db.add(cache_entry)

                count += 1

        await db.commit()
        print(f"[Rescore] Updated urgency for {count} user-topic scores")


async def nightly_deprecation_check():
    """
    Cross-reference recently ingested chunks against existing flashcards.
    Runs after the urgency rescore so it doesn't delay dashboard data.
    Only checks volatile topic types (current_affairs, schemes, etc.).
    """
    from core.database import async_session_maker, User, Chunk, Document
    from services.prediction.deprecation import check_fact_deprecation
    from sqlalchemy import select
    from datetime import datetime, timezone, timedelta

    async with async_session_maker() as db:
        # Only check chunks ingested in the last 24 hours
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)

        result = await db.execute(select(User))
        users = result.scalars().all()

        for user in users:
            # Get recently ingested chunks for this user
            chunk_result = await db.execute(
                select(Chunk).where(
                    Chunk.user_id == user.id,
                    Chunk.ingested_at >= cutoff,
                )
            )
            recent_chunks = chunk_result.scalars().all()

            if not recent_chunks:
                continue

            chunk_dicts = [{"content": c.content} for c in recent_chunks]

            try:
                await check_fact_deprecation(chunk_dicts, str(user.id), db)
                print(f"[Deprecation] Checked {len(chunk_dicts)} chunks for user {user.id}")
            except Exception as e:
                print(f"[Deprecation] Failed for user {user.id}: {e}")


def setup_scheduler():
    """Configure and return the scheduler. Call from main.py."""
    scheduler.add_job(
        daily_urgency_rescore,
        "cron",
        hour=12,
        minute=0,
        id="daily_urgency_rescore",
        replace_existing=True,
        misfire_grace_time=3600,  # If server is off at 11:30 PM, it has 1 hour to catch up when turned on
    )
    scheduler.add_job(
        nightly_deprecation_check,
        "cron",
        hour=0,
        minute=0,
        id="nightly_deprecation_check",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    return scheduler

