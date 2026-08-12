import asyncio
from sqlalchemy import select, delete, or_
from core.database import async_session_maker, Topic, Chunk, UrgencyCache, TopicRelationship, Flashcard

async def clean_orphaned_topics():
    async with async_session_maker() as db:
        topics_with_chunks = select(Chunk.topic_name).where(Chunk.topic_name.is_not(None))
        orphaned_topics_query = select(Topic.id).where(~Topic.name.in_(topics_with_chunks))
        
        result = await db.execute(orphaned_topics_query)
        orphaned_topic_ids = [row[0] for row in result.all()]

        if orphaned_topic_ids:
            print(f"Found {len(orphaned_topic_ids)} orphaned topics. Deleting...")
            await db.execute(delete(UrgencyCache).where(UrgencyCache.topic_id.in_(orphaned_topic_ids)))
            await db.execute(delete(TopicRelationship).where(
                or_(
                    TopicRelationship.topic_a.in_(orphaned_topic_ids),
                    TopicRelationship.topic_b.in_(orphaned_topic_ids)
                )
            ))
            await db.execute(delete(Flashcard).where(Flashcard.topic_id.in_(orphaned_topic_ids)))
            await db.execute(delete(Topic).where(Topic.id.in_(orphaned_topic_ids)))
            await db.commit()
            print("Successfully cleaned up the database!")
        else:
            print("No orphaned topics found.")

if __name__ == "__main__":
    asyncio.run(clean_orphaned_topics())
