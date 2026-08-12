"""One-time migration: Add topic_name column to chunks table."""
import asyncio
from sqlalchemy import text
from core.database import engine

async def migrate():
    async with engine.begin() as conn:
        await conn.execute(text("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS topic_name VARCHAR;"))
        print("[Migration] Added 'topic_name' column to chunks table.")

if __name__ == "__main__":
    asyncio.run(migrate())
