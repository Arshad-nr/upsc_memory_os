import json
from pydantic import BaseModel, Field

from core.config import settings
from services.llm import call_gemini
from models.enums import TopicType

class ChunkMetadata(BaseModel):
    topic_type: TopicType
    topic_name: str = Field(description="Specific topic e.g. 'Paris Agreement' or 'Article 32'")
    key_entities: list[str] = Field(description="List of 2-3 key terms from the text")
    syllabus_area: str = Field(description="e.g. 'GS3 > Environment > International Conventions'")

class BatchMetadataResponse(BaseModel):
    metadata_list: list[ChunkMetadata] = Field(
        description="Must contain EXACTLY the same number of items as the input chunks, in the exact same order."
    )

_DEFAULT = {
    "topic_type": TopicType.STATIC_SYLLABUS.value,
    "topic_name": "Unknown",
    "key_entities": [],
    "syllabus_area": "",
}

async def extract_chunk_topics(chunk_text: str) -> dict:
    """Single chunk extraction — kept for backward compatibility."""
    results = await extract_topics_batch([chunk_text])
    return results[0] if results else _DEFAULT.copy()

async def extract_topics_batch(chunk_texts: list[str]) -> list[dict]:
    """
    Extract topic metadata for up to 5 chunks in a single Gemini call.
    Uses Structured Outputs to guarantee perfectly ordered JSON arrays.
    """
    if not chunk_texts:
        return []

    # Truncate each chunk to 400 chars — enough context, fewer tokens
    truncated = [t[:400] for t in chunk_texts]

    prompt = f"""Tag each of these {len(truncated)} UPSC study note chunks.
You must output a list of exactly {len(truncated)} objects, corresponding directly to the chunks below in the exact same order.

Chunks:
{json.dumps(truncated, ensure_ascii=False)}""" # to preserve Unicode characters and ensure valid JSON formatting

    # Call Gemini using structured outputs
    # Adjust model name if needed (e.g., gemini-2.5-flash)
    raw = await call_gemini(
        prompt, 
        model=settings.GEMINI_FLASH_MODEL, 
        response_schema=BatchMetadataResponse
    )
    
    try:
        parsed = json.loads(raw)
        metadata_list = parsed.get("metadata_list", [])
        
        if not isinstance(metadata_list, list):
            metadata_list = []
            
    except json.JSONDecodeError:
        metadata_list = []

    # Map the results back to standard dicts, padding with defaults if the LLM missed any
    result = []
    for i in range(len(chunk_texts)):
        if i < len(metadata_list):
            item = metadata_list[i]
            result.append({
                "topic_type": item.get("topic_type", TopicType.STATIC_SYLLABUS.value),
                "topic_name": item.get("topic_name", "Unknown"),
                "key_entities": item.get("key_entities", []),
                "syllabus_area": item.get("syllabus_area", ""),
            })
        else:
            result.append(_DEFAULT.copy())

    return result
