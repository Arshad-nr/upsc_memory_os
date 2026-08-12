"""Quick reset — no confirmation prompt."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from reset_db import reset_postgres, reset_qdrant
from core.database import engine

async def main():
    await reset_postgres()
    reset_qdrant()
    print("\n✅ Database fully reset!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
