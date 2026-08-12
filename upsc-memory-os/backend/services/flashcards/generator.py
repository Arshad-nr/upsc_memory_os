"""
Flashcard & MCQ generation via Gemini 2.5 Flash — Batched & Structured.

This module takes pre-chunked UPSC study materials and generates interactive
study cards. It uses batching to process multiple chunks in a single network 
call and Pydantic schemas to guarantee perfect JSON formatting.
"""

import json
from enum import Enum
from pydantic import BaseModel, Field

# Ensure this import points to your actual LLM service that supports `response_schema`
from services.llm import call_gemini
from core.config import settings
from models.enums import Difficulty

# ─── DOMAIN ENUMS ───────────────────────────────────────────────────
# Difficulty imported from models.enums (single source of truth)

class CorrectOption(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"

# ─── PYDANTIC SCHEMAS (STRUCTURED OUTPUTS) ──────────────────────────
# These schemas force the LLM to return exact, mathematically perfect JSON.

class Flashcard(BaseModel):
    question: str = Field(description="Clear, specific UPSC-style question")
    answer: str = Field(description="Complete answer, 1-3 sentences max")
    difficulty: Difficulty = Field(
        description="EASY (single fact), MEDIUM (context/relations), HARD (doctrine/high confusion)"
    )

class BatchFlashcardResponse(BaseModel):
    cards: list[Flashcard] = Field(
        description="Must contain EXACTLY the same number of items as the input chunks, in the exact same order."
    )

class MCQ(BaseModel):
    question: str = Field(description="Question stem in UPSC Prelims format")
    option_a: str = Field(description="First option")
    option_b: str = Field(description="Second option")
    option_c: str = Field(description="Third option")
    option_d: str = Field(description="Fourth option")
    
    correct_answer: CorrectOption = Field(description="The exact letter of the correct option")
    explanation: str = Field(description="One sentence explaining why it is correct")
    difficulty: Difficulty

class BatchMCQResponse(BaseModel):
    cards: list[MCQ] = Field(
        description="Must contain EXACTLY the same number of items as the input chunks, in the exact same order."
    )


# ─── BATCH GENERATORS ───────────────────────────────────────────────

async def generate_flashcards_batch(chunks: list[dict]) -> list[dict]:
    """
    Generates multiple flashcards in a single Gemini call.
    Truncates chunks to 1000 characters to prevent context overload.
    """
    if not chunks:
        return []

    texts = [c.get("content", "")[:1000] for c in chunks]
    
    # ensure_ascii=False protects Indian languages and special characters
    prompt = f"""Generate UPSC study flashcards from these study note chunks.
You must output a list of exactly {len(texts)} flashcards, corresponding directly to the chunks below in the exact same order.

Chunks:
{json.dumps(texts, ensure_ascii=False)}"""

    raw = await call_gemini(
        prompt,
        model=settings.GEMINI_FLASH_MODEL,
        response_schema=BatchFlashcardResponse
    )

    return _process_batch_response(raw, chunks, "flashcard")


async def generate_mcqs_batch(chunks: list[dict]) -> list[dict]:
    """
    Generates multiple MCQs in a single Gemini call.
    """
    if not chunks:
        return []

    texts = [c.get("content", "")[:1000] for c in chunks]
    
    prompt = f"""Generate UPSC Prelims style Multiple Choice Questions (MCQs) from these study note chunks.
You must output a list of exactly {len(texts)} MCQs, corresponding directly to the chunks below in the exact same order.

CRITICAL FORMATTING INSTRUCTION: 
If the question stem includes multiple statements (e.g. "1. Statement A  2. Statement B"), you MUST separate them with literal newline characters (\\n) so they render properly in the UI.

Example Question Formatting:
"With reference to X, consider the following:\\n1. Statement A\\n2. Statement B\\nWhich of the above are correct?"

Chunks:
{json.dumps(texts, ensure_ascii=False)}"""

    raw = await call_gemini(
        prompt,
        model=settings.GEMINI_FLASH_MODEL,
        response_schema=BatchMCQResponse
    )

    return _process_batch_response(raw, chunks, "mcq")


# ─── HELPER FUNCTIONS (DATA INHERITANCE) ────────────────────────────

def _process_batch_response(raw_json: str, original_chunks: list[dict], card_type: str) -> list[dict]:
    """
    Safely parses the LLM JSON and zips it back with the original chunk data.
    Critically, this function inherits the topic_type directly from the database 
    chunk, preventing the LLM from hallucinating mismatched metadata.
    """
    try:
        parsed = json.loads(raw_json) #json.loads returns a Python dict from the raw JSON string
        cards_list = parsed.get("cards", [])
        if not isinstance(cards_list, list):
            return []
    except json.JSONDecodeError:
        print(f'[Generator] Failed to parse LLM response: {raw_json[:200]}')
        return []

    final_cards = []
    
    # Zip the generated cards with the original chunks to preserve metadata
    for i, chunk in enumerate(original_chunks):
        # Safety check in case the LLM returns fewer cards than requested
        if i < len(cards_list):
            card_data = cards_list[i]
            
            # 1. Base formatting & Data Inheritance
            formatted_card = {
                "chunk_id": chunk.get("chunk_id"),
                "topic_type": chunk.get("topic_type", "static_syllabus"),  # Inherited directly from DB
                "card_type": card_type,
                "difficulty": card_data.get("difficulty", "medium")
            }

            # 2. Map specific fields based on the requested card type
            if card_type == "flashcard":
                formatted_card["question"] = card_data.get("question", "")
                formatted_card["answer"] = card_data.get("answer", "")
            else:
                formatted_card["question"] = card_data.get("question", "")
                # Flattened options guarantee the LLM doesn't mess up nested JSON
                formatted_card["options"] = {
                    "A": card_data.get("option_a", ""),
                    "B": card_data.get("option_b", ""),
                    "C": card_data.get("option_c", ""),
                    "D": card_data.get("option_d", "")
                }
                formatted_card["correct"] = card_data.get("correct_answer", "A")
                formatted_card["explanation"] = card_data.get("explanation", "")
                
            final_cards.append(formatted_card)
            
    return final_cards


# ─── MAIN PUBLIC API ────────────────────────────────────────────────

async def generate_cards_for_topic(
    chunks: list[dict],
    count: int = 5,
    card_type: str = "flashcard",
) -> list[dict]:
    """
    Public entry point to generate cards for a frontend request. 
    Routes to the appropriate high-speed batch processor.
    
    Args:
        chunks: List of dictionary chunks retrieved from the database.
        count: Maximum number of cards to generate (default 5).
        card_type: 'flashcard' or 'mcq'.
    """
    # Slice the chunks to the requested count to limit batch size
    target_chunks = chunks[:count]
    
    if card_type == "flashcard":
        return await generate_flashcards_batch(target_chunks)
    elif card_type == "mcq":
        return await generate_mcqs_batch(target_chunks)
    else:
        raise ValueError(f"Invalid card_type: {card_type}. Must be 'flashcard' or 'mcq'.")