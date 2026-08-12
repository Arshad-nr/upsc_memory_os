"""Two-tier answer evaluation — embedding similarity + LLM for borderline cases."""

import json
import asyncio
import numpy as np
from pydantic import BaseModel, Field

from services.llm import call_gemini_flash
from core.vector_store import embed_dense


# ─── PYDANTIC SCHEMA ────────────────────────────────────────────────
class EvaluationResult(BaseModel):
    correct: bool = Field(description="True if the answer is conceptually correct")
    score: float = Field(description="Float between 0.0 (wrong) and 1.0 (perfect)")
    feedback: str = Field(description="One sentence explaining the score")


def _calculate_similarity(text1: str, text2: str) -> float:
    """Synchronous CPU-bound math isolated in its own function."""
    # We do a simple numpy cosine similarity to avoid importing the heavy scikit-learn library
    emb1 = np.array(embed_dense(text1))
    emb2 = np.array(embed_dense(text2))
    
    # Cosine similarity = dot(A, B) / (norm(A) * norm(B))
    dot = np.dot(emb1, emb2)
    norm = np.linalg.norm(emb1) * np.linalg.norm(emb2)
    
    # Handle zero division edge cases safely
    return float(dot / norm) if norm > 0 else 0.0


async def evaluate_answer(
    question: str,
    correct_answer: str,
    user_answer: str,
) -> dict:
    """
    Two-tier evaluation:
    Tier 1: Embedding cosine similarity — fast, free, no LLM call
    Tier 2: LLM evaluation for borderline cases (0.30-0.92)
    """
    if not user_answer or not user_answer.strip():
        return {
            "correct": False,
            "score": 0.0,
            "feedback": f"No answer provided. Correct answer: {correct_answer}",
        }

    # Tier 1: Embedding similarity — offloaded to a background thread to prevent blocking FastAPI
    #asyncio.to_thread allows us to run the synchronous _calculate_similarity function without blocking the main event loop, which is crucial for maintaining the responsiveness of our FastAPI application while still performing CPU-bound work. This way, we get the best of both worlds: efficient similarity calculation and a responsive API.
    sim = await asyncio.to_thread(_calculate_similarity, correct_answer, user_answer)

    # Fast-pass thresholds
    if sim > 0.92:
        return {"correct": True, "score": 1.0, "feedback": "Correct!"}
    if sim < 0.30:
        return {
            "correct": False,
            "score": 0.0,
            "feedback": f"Correct answer: {correct_answer}",
        }

    # Tier 2: LLM for borderline 0.30–0.92 range only
    prompt = f"""UPSC answer evaluation. 
Evaluate if the student's answer correctly matches the intent of the real answer.
Synonyms and paraphrasing count as correct.

Question: {question}
Correct Answer: {correct_answer}
Student Answer: {user_answer}"""

    raw = await call_gemini_flash(prompt, response_schema=EvaluationResult)
    
    try:
        parsed = json.loads(raw)
        return {
            "correct": parsed.get("correct", False),
            "score": float(parsed.get("score", 0.0)),
            "feedback": parsed.get("feedback", f"Correct answer: {correct_answer}"),
        }
    except json.JSONDecodeError:
        # Failsafe fallback
        return {
            "correct": False,
            "score": 0.0,
            "feedback": f"Correct answer: {correct_answer}",
        }
