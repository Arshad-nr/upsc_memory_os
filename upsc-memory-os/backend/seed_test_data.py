"""
Standalone script to seed the database with a mock user and ingest 4 specific PDFs
for RAGAS evaluation testing.

Usage:
    cd backend
    python seed_test_data.py
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import async_session_maker, User, Document
from api.routes.documents import run_ingestion
from core.vector_store import init_models


async def main():
    print("==================================================")
    print("  Initializing RAG Seeding Script...")
    print("==================================================")

    # 1. Initialize Embedding Models (Required for ingestion)
    print("\n[1/4] Loading embedding models...")
    init_models()
    
    # Define test PDF directory and expected files
    test_pdf_dir = os.path.join(os.path.dirname(__file__), "test_pdfs")
    expected_files = [
        "PR37.pdf",
        "Cabinet.pdf",
        "OF43.MH.pdf",
        "Bill Summary - The Tribunals Reforms Bill, 2021.pdf"
    ]
    
    # Validate files exist before starting
    print("\n[2/4] Validating PDF files...")
    if not os.path.exists(test_pdf_dir):
        print(f"❌ Error: Directory not found: {test_pdf_dir}")
        print("   Please create a 'test_pdfs' folder in the backend directory and add the PDFs.")
        sys.exit(1)
        
    for file_name in expected_files:
        file_path = os.path.join(test_pdf_dir, file_name)
        if not os.path.exists(file_path):
            print(f"❌ Error: Missing required file: {file_name}")
            sys.exit(1)
    print("✅ All 4 PDFs found.")

    # 2. Create Mock User
    print("\n[3/4] Creating mock user in database...")
    user_id = None
    async with async_session_maker() as db:
        # Check if user already exists (to allow running script multiple times)
        from sqlalchemy import select
        existing = await db.execute(select(User).where(User.email == "ragas_evaluator@test.com"))
        user = existing.scalars().first()
        
        if not user:
            user = User(
                email="ragas_evaluator@test.com",
                password_hash="fakehash_not_used",
                exam_date=datetime(2027, 5, 28).date()
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"✅ Created new mock user")
        else:
            print(f"✅ Re-using existing mock user")
            
        user_id = str(user.id)
        
    # 3. Ingest Documents
    print(f"\n[4/4] Starting Ingestion Pipeline for 4 PDFs...")
    for i, file_name in enumerate(expected_files):
        file_path = os.path.join(test_pdf_dir, file_name)
        file_size = os.path.getsize(file_path)
        
        print(f"\n--- Ingesting ({i+1}/4): {file_name} ---")
        async with async_session_maker() as db:
            doc = Document(
                user_id=uuid.UUID(user_id),
                filename=file_name,
                source_type="official_report",
                file_path=file_path,
                ingestion_status="pending"
            )
            db.add(doc)
            await db.commit()
            await db.refresh(doc)
            doc_id = str(doc.id)
            
        # Run the actual pipeline from documents.py
        try:
            await run_ingestion(
                doc_id=doc_id,
                file_path=file_path,
                user_id=user_id,
                source_type="official_report"
            )
        except Exception as e:
            print(f"❌ Ingestion failed for {file_name}: {e}")
            
    print("\n==================================================")
    print("  SEEDING COMPLETE")
    print("==================================================")
    print("Your RAGAS Evaluation User UUID is:")
    
    # Print the UUID in bright green with bold text
    print(f"\n\033[1;32;40m{user_id}\033[0m\n")
    print("Copy the ID above and paste it into evaluate_rag.py as TEST_USER_ID.")


if __name__ == "__main__":
    asyncio.run(main())
