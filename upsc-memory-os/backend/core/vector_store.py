from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, SparseVectorParams, SparseIndexParams,
    PointStruct, Filter, FieldCondition, MatchValue,
    Prefetch, FusionQuery, Fusion, SparseVector
)
from fastembed import SparseTextEmbedding
from sentence_transformers import SentenceTransformer
import uuid

from core.config import settings

COLLECTION = settings.COLLECTION_NAME  # 'upsc_chunks'
DENSE_DIM = settings.DENSE_DIM  # 768 (bge-base-en-v1.5)

# Singletons — loaded once at startup via init_models()
_qdrant = None
_dense = None
_sparse = None


def init_models():
    """Call once at FastAPI startup. Loads embedding models and creates Qdrant client."""
    global _qdrant, _dense, _sparse
    import os
    import torch

    # Qdrant connection priority:
    #   1. Cloud (QDRANT_API_KEY is set)      → connect with URL + API key
    #   2. Docker/HTTP (QDRANT_URL is set)    → connect via plain HTTP
    #   3. Local file mode (fallback)         → on-disk storage
    if settings.QDRANT_API_KEY:
        _qdrant = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
        print(f"[Startup] Connected to Qdrant Cloud: {settings.QDRANT_URL}")
    elif os.getenv("QDRANT_URL"):
        _qdrant = QdrantClient(url=settings.QDRANT_URL)
        print(f"[Startup] Connected to Qdrant via HTTP: {settings.QDRANT_URL}")
    else:
        os.makedirs(settings.QDRANT_PATH, exist_ok=True)
        _qdrant = QdrantClient(path=settings.QDRANT_PATH)
        print(f"[Startup] Connected to Qdrant via Local File: {settings.QDRANT_PATH}")

    # Explicitly select GPU if available
    device = "cuda" if torch.cuda.is_available() else "cpu"
    _dense = SentenceTransformer(settings.EMBEDDING_MODEL, device=device)

    # FastEmbed sparse model (BM25) — uses ONNX, GPU handled by onnxruntime-gpu
    _sparse = SparseTextEmbedding(settings.SPARSE_MODEL)

    print(f"[Startup] Dense model device: {_dense.device} ({'GPU: ' + torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU'})")
    print(f"[Startup] PyTorch CUDA available: {torch.cuda.is_available()}, version: {torch.__version__}")


def init_collection():
    """Create collection if it doesn't exist. Recreate if dimension changed (model upgrade)."""
    existing = [c.name for c in _qdrant.get_collections().collections]
    if COLLECTION in existing:
        # Check if vector dimension matches current model
        info = _qdrant.get_collection(COLLECTION)
        current_dim = info.config.params.vectors.get("dense")
        if current_dim and current_dim.size != DENSE_DIM:
            print(f"[Qdrant] Dimension mismatch: collection has {current_dim.size}, model needs {DENSE_DIM}")
            print(f"[Qdrant] Recreating collection (old vectors are from a different model)")
            _qdrant.delete_collection(COLLECTION)
        else:
            return  # Collection exists with correct dimensions

    _qdrant.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            "dense": VectorParams(size=DENSE_DIM, distance=Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(index=SparseIndexParams(on_disk=False))
        }
    )
    print(f"[Qdrant] Created collection '{COLLECTION}' with dense_dim={DENSE_DIM}")


def embed_dense(text: str) -> list[float]:
    if _dense is None:
        raise RuntimeError(
            "embed_dense called before init_models(). "
            "Ensure init_models() runs at FastAPI startup."
        )
    return _dense.encode(text).tolist()


def embed_sparse(text: str) -> SparseVector:
    if _sparse is None:
        raise RuntimeError(
            "embed_sparse called before init_models(). "
            "Ensure init_models() runs at FastAPI startup."
        )
    result = list(_sparse.embed([text]))[0]
    return SparseVector(indices=result.indices.tolist(), values=result.values.tolist())


def store_chunk(chunk_id: str, user_id: str, content: str, metadata: dict) -> str:
    point_id = str(uuid.uuid4())
    _qdrant.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(
            id=point_id,
            vector={"dense": embed_dense(content), "sparse": embed_sparse(content)},
            payload={"chunk_id": chunk_id, "user_id": user_id, "content": content, **metadata}
        )]
    )
    return point_id


def retrieve_hybrid(user_id: str, query: str, k: int = 5) -> list[dict]:
    user_filter = Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
    results = _qdrant.query_points(
        collection_name=COLLECTION,
        prefetch=[
            Prefetch(query=embed_dense(query), using="dense", limit=20, filter=user_filter),
            Prefetch(query=embed_sparse(query), using="sparse", limit=20, filter=user_filter),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=k
    )
    return [
        {
            "content": r.payload["content"],
            "parent_content": r.payload.get("parent_content", ""),
            "document_id": r.payload.get("document_id"),
            "page_number": r.payload.get("page_number"),
            "topic_type": r.payload.get("topic_type"),
            "ingested_at": r.payload.get("ingested_at", ""),
            "score": r.score,
        }
        for r in results.points
    ]


def delete_user_chunks(user_id: str):
    _qdrant.delete(
        collection_name=COLLECTION,
        points_selector=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
    )


def delete_document_chunks(document_id: str):
    """Delete all chunks for a specific document from Qdrant."""
    _qdrant.delete(
        collection_name=COLLECTION,
        points_selector=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))])
    )


# ── Batch operations (5-10× faster than one-at-a-time) ──────────────

def embed_dense_batch(texts: list[str]) -> list[list[float]]:
    """Batch-encode with SentenceTransformer. Leverages internal mini-batching."""
    if _dense is None:
        raise RuntimeError("embed_dense_batch called before init_models().")
    return _dense.encode(texts, show_progress_bar=False).tolist()


def embed_sparse_batch(texts: list[str]) -> list[SparseVector]:
    """Batch-encode with BM25 sparse model."""
    if _sparse is None:
        raise RuntimeError("embed_sparse_batch called before init_models().")
    results = list(_sparse.embed(texts))
    return [
        SparseVector(indices=r.indices.tolist(), values=r.values.tolist())
        for r in results
    ]


def store_chunks_batch(chunks: list[dict]) -> list[str]:
    """
    Batch embed + upsert into Qdrant.

    Each dict must have: chunk_id, user_id, content, metadata (dict).
    Returns list of Qdrant point IDs in the same order.

    ~5-10× faster than calling store_chunk() in a loop because:
    - SentenceTransformer.encode() batches CPU/GPU inference
    - Single Qdrant upsert call instead of N individual round-trips
    """
    if not chunks:
        return []

    contents = [c["content"] for c in chunks]

    # Batch embedding — the big speedup
    dense_vectors = embed_dense_batch(contents)
    sparse_vectors = embed_sparse_batch(contents)

    points = []
    point_ids = []
    for i, chunk in enumerate(chunks):
        pid = str(uuid.uuid4())
        point_ids.append(pid)
        points.append(PointStruct(
            id=pid,
            vector={"dense": dense_vectors[i], "sparse": sparse_vectors[i]},
            payload={
                "chunk_id": chunk["chunk_id"],
                "user_id": chunk["user_id"],
                "content": chunk["content"],
                **chunk.get("metadata", {}),
            },
        ))

    # Single upsert — avoids N round-trips to Qdrant
    _qdrant.upsert(collection_name=COLLECTION, points=points)
    return point_ids
