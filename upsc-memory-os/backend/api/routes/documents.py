"""Document upload + ingestion pipeline with atomic failure handling."""

import asyncio
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, or_, and_

from api.dependencies import get_current_user, get_db
from core.config import settings
from core.database import User, Document, Chunk, Topic, Flashcard, UrgencyCache, TopicRelationship, async_session_maker
from core.vector_store import store_chunks_batch, delete_document_chunks
from services.ingestion.parser import parse_pdf
from services.ingestion.chunker import chunk_document
from services.ingestion.topic_extractor import extract_topics_batch
from models.schemas import DocumentResponse, DocumentUploadResponse

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])#APIRouter is like a mini FastAPI app that we can mount onto the main app. It helps organize routes by functionality.


@router.post("/upload", response_model=DocumentUploadResponse)#response_model automatically converts the returned dict into a DocumentUploadResponse object, which ensures consistent API responses and auto-generates docs.
async def upload_document(
    file: UploadFile = File(...),#... means this parameter is required. FastAPI will handle parsing the multipart form data and provide an UploadFile object.
    topic_category: str = Form(""),
    source_type: str = Form("newspaper"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a PDF and trigger background ingestion."""
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save to local disk
    doc_id = str(uuid.uuid4())
    dir_path = os.path.join(settings.PDF_STORAGE_PATH, str(user.id))
    os.makedirs(dir_path, exist_ok=True)#exist_ok=True prevents an error if the directory already exists, which can happen if the user uploads multiple documents.
    file_path = os.path.join(dir_path, f"{doc_id}.pdf")

    content = await file.read()
    with open(file_path, "wb") as f:#wb = write binary mode, which is necessary for non-text files like PDFs.
        f.write(content)

    # Create document record
    doc = Document(
        id=uuid.UUID(doc_id),
        user_id=user.id,
        filename=file.filename,
        source_type=source_type if source_type in (
            "newspaper", "coaching_notes", "handwritten", "official_report"
        ) else "newspaper",
        topic_category=topic_category or None,
        file_path=file_path,
        ingestion_status="pending",
    )
    db.add(doc)
    await db.commit()

    # Detach ingestion from HTTP request lifecycle so connection closes instantly
    # Using asyncio.create_task ensures Cloudflare/Nginx don't timeout waiting for the task
    asyncio.create_task(
        run_ingestion(doc_id, file_path, str(user.id), source_type)
    )

    return DocumentUploadResponse(document_id=doc_id, status="processing")


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all documents for the current user."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == user.id)
        .order_by(Document.uploaded_at.desc())
    )
    docs = result.scalars().all()
    return [
        DocumentResponse(
            id=str(doc.id),
            filename=doc.filename,
            source_type=doc.source_type,
            topic_category=doc.topic_category,
            uploaded_at=doc.uploaded_at,
            chunk_count=doc.chunk_count or 0,
            ingestion_status=doc.ingestion_status,
            error_message=doc.error_message,
        )
        for doc in docs
    ]


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document — cascade: PostgreSQL chunks + Qdrant vectors."""
    doc_uuid = uuid.UUID(document_id)
    result = await db.execute(
        select(Document).where(
            Document.id == doc_uuid,
            Document.user_id == user.id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete from Qdrant first
    try:
        delete_document_chunks(document_id)
    except Exception as e:
        print(f"Warning: Qdrant cleanup failed for {document_id}: {e}")

    # Un-deprecate flashcards that were superseded by this document
    await db.execute(
        update(Flashcard)
        .where(Flashcard.superseded_by_doc == doc_uuid)
        .values(
            superseded_by_doc=None,
            deprecated=False,
            deprecation_reason=None,
            deprecated_at=None
        )
    )

    # Delete flashcards associated with chunks from this document
    await db.execute(
        delete(Flashcard).where(Flashcard.chunk_id.in_(
            select(Chunk.id).where(Chunk.document_id == doc_uuid)
        ))
    )

    # Delete chunks from PostgreSQL
    await db.execute(
        delete(Chunk).where(Chunk.document_id == doc_uuid)
    )

    # ── CLEANUP ORPHANED TOPICS ──
    # Find all topics that no longer have any chunks associated with them across ALL documents
    # (Since we just deleted this document's chunks, if a topic was unique to this doc, it's now orphaned)
    topics_with_chunks = select(Chunk.topic_name).where(Chunk.topic_name.is_not(None))
    
    orphaned_topics_query = select(Topic.id).where(
        ~Topic.name.in_(topics_with_chunks)
    )
    result = await db.execute(orphaned_topics_query)
    orphaned_topic_ids = [row[0] for row in result.all()] 

    if orphaned_topic_ids:
        # Delete dependencies first to avoid foreign key constraint errors
        await db.execute(delete(UrgencyCache).where(UrgencyCache.topic_id.in_(orphaned_topic_ids)))
        await db.execute(delete(TopicRelationship).where(
            or_(
                TopicRelationship.topic_a.in_(orphaned_topic_ids),
                TopicRelationship.topic_b.in_(orphaned_topic_ids)
            )
        ))
        await db.execute(delete(Flashcard).where(Flashcard.topic_id.in_(orphaned_topic_ids)))
        
        # Delete the orphaned topics themselves
        await db.execute(delete(Topic).where(Topic.id.in_(orphaned_topic_ids)))

    # Delete the document record
    await db.delete(doc)
    await db.commit()

    # Delete file from disk
    if doc.file_path and os.path.exists(doc.file_path):
        os.remove(doc.file_path)

    return {"status": "deleted", "document_id": document_id}


# ── Background ingestion ─────────────────────────────────────────


async def run_ingestion(doc_id: str, file_path: str, user_id: str, source_type: str = "newspaper"):
    """
    Full ingestion pipeline. Atomic: if Qdrant store fails after
    PostgreSQL succeeds, roll back PostgreSQL chunks.
    """
    # Start first session to update status
    async with async_session_maker() as db:
        try:
            # Update status → processing
            await db.execute(
                update(Document)
                .where(Document.id == uuid.UUID(doc_id))
                .values(ingestion_status="processing")
            )
            await db.commit()
        except Exception as e:
            print(f"[Ingestion] Failed to update status to processing: {e}")
            return

    # Do the long-running operations WITHOUT holding the DB connection
    # Step 1: Parse PDF
    pages = await asyncio.to_thread(parse_pdf, file_path)
    if not pages:
        async with async_session_maker() as db:
            await _update_doc_status(db, doc_id, "failed", error="No text extracted from PDF")
        return

    print(f"[Ingestion] Parsed {len(pages)} pages from {file_path}")

    # Step 2: Hierarchical chunking
    chunks = await asyncio.to_thread(chunk_document, pages)
    print(f"[Ingestion] Created {len(chunks)} chunks")

    # Step 3: Batch topic extraction — 50 chunks per LLM call (Huge speedup for large docs)
    BATCH_SIZE = 50
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        try:
            batch_tags = await extract_topics_batch([c["content"] for c in batch])
            for chunk, tags in zip(batch, batch_tags):
                chunk.update(tags)#.update() merges the topic tags (topic_type, topic_name) into the existing chunk dict. This way we keep all the original chunk metadata (page number, parent content, etc.) and just add the new topic info.
            print(f"[Ingestion] Tagged chunks {i+1}-{min(i+BATCH_SIZE, len(chunks))}/{len(chunks)}")
        except Exception as e:
            print(f"[Ingestion] Batch topic extraction failed for chunks {i+1}-{min(i+BATCH_SIZE, len(chunks))}: {e}")
            for chunk in batch:
                chunk["topic_type"] = "static_syllabus"
                chunk["topic_name"] = "Unknown"

    # Start a NEW DB session for the storage phase
    async with async_session_maker() as db:
        try:
            # Step 4: Ensure topics exist in database (BATCHED — single commit)
            unique_topics = set()
            for chunk in chunks:
                t_name = chunk.get("topic_name", "Unknown")
                t_type = chunk.get("topic_type", "static_syllabus")
                t_area = chunk.get("syllabus_area", "")
                unique_topics.add((t_name, t_type, t_area))

            await _ensure_topics_batch(db, unique_topics, user_id)

            # Step 5: Store in PostgreSQL first
            chunk_records = []
            for chunk in chunks:
                record = Chunk(
                    document_id=uuid.UUID(doc_id),
                    user_id=uuid.UUID(user_id),
                    content=chunk["content"],
                    parent_content=chunk.get("parent_content"),
                    page_number=chunk.get("page_number"),
                    chunk_index=chunk.get("chunk_index"),
                    token_count=chunk.get("token_count"),
                    topic_type=chunk.get("topic_type"),
                    topic_name=chunk.get("topic_name"),
                    section_header=chunk.get("syllabus_area"),
                )
                db.add(record)#db.add won't make an api call to the database immediately. It just adds the record to the session. The actual INSERT happens when we call db.commit() or db.flush(). This allows us to add all the chunk records in a loop and then commit them all at once, which is much more efficient than committing inside the loop.
                chunk_records.append(record)#chunk_records has db record id which we will link to the Qdrant vector IDs in the next step.

            await db.commit()#this flushes all the new chunk records to the database and assigns them IDs. We need these IDs to link the PostgreSQL records with the Qdrant vectors in the next step.
            
            # Note: We removed the `db.refresh(record)` loop here because 
            # uuid.uuid4() is generated by the client, so we already have the IDs!
            # This saves ~40 sequential network queries to the database.

            print(f"[Ingestion] Stored {len(chunk_records)} chunks in PostgreSQL")

            # Step 6: Batch store in Qdrant (may fail independently)
            try:
                ingested_at = datetime.now(timezone.utc).isoformat()
                batch = [
                    {
                        "chunk_id": str(record.id),
                        "user_id": user_id,
                        "content": chunk["content"],
                        "metadata": {
                            "parent_content": chunk.get("parent_content", ""),
                            "document_id": doc_id,
                            "page_number": chunk.get("page_number", 0),
                            "topic_type": chunk.get("topic_type", ""),
                            "topic_name": chunk.get("topic_name", ""),
                            "ingested_at": ingested_at,
                            "source_type": source_type,
                        },
                    }
                    for chunk, record in zip(chunks, chunk_records)
                ]
                qdrant_ids = store_chunks_batch(batch)
                for record, qid in zip(chunk_records, qdrant_ids):
                    record.qdrant_id = qid

                await db.commit()
                print(f"[Ingestion] Batch-stored {len(chunk_records)} vectors in Qdrant")

            except Exception as e:
                # Compensating transaction: remove postgres chunks
                print(f"[Ingestion] Qdrant store failed, rolling back: {e}")
                await db.execute(
                    delete(Chunk).where(Chunk.document_id == uuid.UUID(doc_id))
                )
                await db.commit()
                raise e

            # NOTE: Fact deprecation check is handled by the nightly cron job,
            # not here. Running it during upload would delay the document
            # status update by 3-10+ seconds (M×N embeddings + LLM calls).

            # Mark complete
            await _update_doc_status(
                db, doc_id, "complete", chunk_count=len(chunks)
            )
            
            print(f"[Ingestion] Complete: {len(chunks)} chunks ingested for doc {doc_id}")

        except Exception as e:
            print(f"[Ingestion] Failed for doc {doc_id}: {e}")
            await _update_doc_status(db, doc_id, "failed", error=str(e))


async def _update_doc_status(
    db: AsyncSession,
    doc_id: str,
    status: str,
    chunk_count: int = None,
    error: str = None,
):
    """Update document ingestion status."""
    values = {"ingestion_status": status}
    if chunk_count is not None:
        values["chunk_count"] = chunk_count
    if error is not None:
        values["error_message"] = error
    await db.execute(
        update(Document)
        .where(Document.id == uuid.UUID(doc_id))
        .values(**values)
    )
    await db.commit()


async def _ensure_topics_batch(
    db: AsyncSession,
    unique_topics: set,
    user_id: str = None,
):
    """Batch-create all topics + UrgencyCache in minimal DB round-trips.
    
    Old approach: 5 queries × N topics = ~200 round-trips for 40 topics.
    New approach: 2 SELECTs + bulk INSERTs + 1 COMMIT = ~4 round-trips total.
    """
    if not unique_topics:
        return

    # 1. Fetch ONLY the existing topics we care about using OR/AND conditions
    conditions = [
        and_(Topic.name == t_name, Topic.topic_type == t_type) 
        for t_name, t_type, _ in unique_topics
    ]
    result = await db.execute(select(Topic).where(or_(*conditions)))
    existing_topics = result.scalars().all()
    existing_map = {(t.name, t.topic_type): t for t in existing_topics}#create a lookup map of existing topics by (name, type) for quick access when we check which topics need to be created and when we create the UrgencyCache entries later. This way we avoid having to query the database again to get the topic IDs after we insert new topics.

    # 2. Bulk-insert missing topics
    new_topics = []
    for t_name, t_type, t_area in unique_topics:
        if (t_name, t_type) not in existing_map:
            topic = Topic(name=t_name, topic_type=t_type, syllabus_area=t_area)
            db.add(topic)
            new_topics.append(topic)

    if new_topics:
        await db.flush()  # single flush to get all IDs at once
        for t in new_topics:
            existing_map[(t.name, t.topic_type)] = t

    # 3. Fetch ONLY existing UrgencyCache entries for these specific topics
    if user_id:
        uid = uuid.UUID(user_id)
        all_topic_ids = [t.id for t in existing_map.values()]
        
        result = await db.execute(
            select(UrgencyCache.topic_id).where(
                UrgencyCache.user_id == uid,
                UrgencyCache.topic_id.in_(all_topic_ids)
            )
        )
        existing_cache_ids = {row[0] for row in result.all()}

        # 4. Bulk-insert missing UrgencyCache entries
        for t_id in all_topic_ids:
            if t_id not in existing_cache_ids:
                db.add(UrgencyCache(
                    user_id=uid,
                    topic_id=t_id,
                    urgency_score=0.2,
                    urgency_tier="MEDIUM",
                ))

    await db.commit()  # single commit for everything
    print(f"[Ingestion] Ensured {len(unique_topics)} topics ({len(new_topics)} new) with UrgencyCache")
