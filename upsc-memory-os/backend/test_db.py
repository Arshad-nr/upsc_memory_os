import asyncio
from core.database import async_session_maker, Document, Topic, UrgencyCache, User
from sqlalchemy import select

async def main():
    async with async_session_maker() as db:
        users = (await db.execute(select(User))).scalars().all()
        print(f"Users: {len(users)}")
        for u in users:
            print(f" - {u.email}")
            
        docs = (await db.execute(select(Document))).scalars().all()
        print(f"\nDocuments: {len(docs)}")
        for d in docs:
            print(f" - {d.filename}: status={d.ingestion_status}, chunks={d.chunk_count}, error={d.error_message}")
            
        topics = (await db.execute(select(Topic))).scalars().all()
        print(f"\nTopics: {len(topics)}")
        
        cache = (await db.execute(select(UrgencyCache))).scalars().all()
        print(f"\nUrgency Cache: {len(cache)}")

if __name__ == "__main__":
    asyncio.run(main())
