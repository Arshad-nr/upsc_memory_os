"""
Wipe ALL data from PostgreSQL + Qdrant and start fresh.

Usage:
    cd backend
    python reset_db.py

This will:
  1. TRUNCATE all 11 PostgreSQL tables (CASCADE)
  2. Delete and recreate the Qdrant collection
  3. Keep the table schemas intact (no need to re-migrate)
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from core.database import engine
from core.config import settings


TABLES = [
    "urgency_cache",
    "flashcards",
    "topic_type_stats",
    "user_topic_profiles",
    "revision_events",
    "study_sessions",
    "topic_relationships",
    "chunks",
    "documents",
    "topics",
    "users",
]


async def reset_postgres():
    """Truncate all tables with CASCADE to handle foreign keys."""
    async with engine.begin() as conn:
        print("\n[Reset] Wiping PostgreSQL tables...")
        for table in TABLES:
            await conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
            print(f"  ✅ {table}")
        print(f"\n[Reset] All {len(TABLES)} tables truncated.")


def reset_qdrant():
    """Delete and recreate the Qdrant collection."""
    from core.vector_store import init_models, init_collection
    from qdrant_client import QdrantClient

    print("\n[Reset] Wiping Qdrant collection...")
    client = QdrantClient(path=settings.QDRANT_PATH)
    collections = [c.name for c in client.get_collections().collections]

    if settings.COLLECTION_NAME in collections:
        client.delete_collection(settings.COLLECTION_NAME)
        print(f"  ✅ Deleted collection '{settings.COLLECTION_NAME}'")
    else:
        print(f"  ⚠️  Collection '{settings.COLLECTION_NAME}' not found (already clean)")

    # Close this client, let init_models create a fresh one
    client.close()

    print("\n[Reset] Recreating Qdrant collection...")
    init_models()
    init_collection()
    print(f"  ✅ Collection '{settings.COLLECTION_NAME}' recreated (empty)")


async def main():
    print("=" * 50)
    print("  UPSC Memory OS — FULL DATABASE RESET")
    print("=" * 50)
    print("\n⚠️  This will DELETE ALL data:")
    print("   • All users and auth data")
    print("   • All uploaded documents and chunks")
    print("   • All flashcards and quiz history")
    print("   • All revision events and scores")
    print("   • All Qdrant vectors")

    confirm = input("\nType 'yes' to confirm: ")
    if confirm.strip().lower() != "yes":
        print("\n❌ Cancelled.")
        return

    await reset_postgres()
    reset_qdrant()

    print("\n" + "=" * 50)
    print("  ✅ Database fully reset. Start fresh!")
    print("=" * 50)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
