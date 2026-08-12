from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, SparseVectorParams, SparseIndexParams

print("Connecting to local Python Qdrant database...")
client_local = QdrantClient(path="./data/qdrant_local")

print("Connecting to new Docker Qdrant database...")
client_docker = QdrantClient(url="http://localhost:6333")

collection_name = "upsc_chunks"

print(f"Checking if collection {collection_name} exists in local DB...")
if not client_local.collection_exists(collection_name):
    print("No collections found in local DB. Exiting.")
    exit()

print(f"Retrieving all points from local DB...")
# Scroll to get all points (max 10,000 for this script which is plenty for 382 chunks)
records, _ = client_local.scroll(
    collection_name=collection_name,
    limit=10000,
    with_payload=True,
    with_vectors=True
)

print(f"Found {len(records)} chunks. Recreating collection in Docker...")
if not client_docker.collection_exists(collection_name):
    client_docker.create_collection(
        collection_name=collection_name,
        vectors_config={"dense": VectorParams(size=768, distance=Distance.COSINE)},
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                index=SparseIndexParams(on_disk=False)
            )
        }
    )

print("Uploading chunks to Docker...")
# We need to map the Record objects back to PointStruct
from qdrant_client.models import PointStruct

points = []
for r in records:
    points.append(
        PointStruct(
            id=r.id,
            vector=r.vector,
            payload=r.payload
        )
    )

if points:
    client_docker.upsert(
        collection_name=collection_name,
        points=points
    )

print(f"Success! Migrated {len(points)} chunks to Docker Dashboard!")
