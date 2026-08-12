"""RAG synthesizer — one prompt per query type, sends parent_content to LLM."""

import json
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from core.config import settings
from services.llm import call_gemini


# ── Response schema (enforced by Gemini Structured Outputs) ──────────

#Enum to enforce specific string values for confidence levels and str to ensure compatibility with Pydantic and JSON serialization
class Confidence(str, Enum): 
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SynthesizerResponse(BaseModel):
    answer: str = Field(
        description="The complete answer to the question"
    )
    confidence: Confidence = Field(
        description="HIGH if context fully supports the answer, "
                    "MEDIUM if partial, LOW if barely relevant"
    )
    used_chunk_indices: list[int] = Field(
        default_factory=list,
        description="A list of chunk indices (e.g., [1, 3]) that were actually used to formulate the answer. Leave empty if no context was used."
    )


# ── Prompt templates ─────────────────────────────────────────────────
# No JSON formatting instructions — response_schema enforces structure.
# Each prompt focuses purely on *how* to answer, not *how* to format.

PROMPTS = {
    "factual": """You are a UPSC study assistant.
Answer ONLY from the context chunks below. Rules:
1. Answer found → precise answer + cite source page (e.g., "Page 12")
2. Partial answer → answer what you can, state what is missing
3. No answer → say exactly: "This is not in your uploaded notes."
4. Never use training knowledge. Wrong exam info = worse than no info.

Context:
{chunks}

Question: {question}""",

    "analytical": """You are a UPSC Mains answer-writing assistant.
Answer ONLY from the context. Structure your answer for maximum marks:

1. **Introduction**: Brief context-setting (1-2 sentences)
2. **Body**: Analyze from multiple dimensions found in the context:
   - Constitutional / Legal aspects
   - Social / Economic / Political dimensions
   - Environmental or International perspective (if relevant)
   - Each point must cite the source page
3. **Way Forward**: Constructive, actionable suggestions drawn from the context
4. **Conclusion**: Balanced, forward-looking summary (1-2 sentences)

Never use training knowledge. Only use what appears in the context.

Context:
{chunks}

Question: {question}""",

    "current": """You are a UPSC current affairs assistant.
Today's date is {today}.
Answer ONLY from context. Each chunk has an ingested_at date.
If a chunk was ingested more than 30 days before today ({today}), explicitly warn the user that the information may be outdated and needs verification.
Never use training knowledge for current events.

Context (with dates):
{chunks}

Question: {question}""",

    "comparative": """You are a UPSC study assistant.
Compare using ONLY the context. Structure your answer as a clean Markdown table.

Use this exact structure for the table:
| Basis of Difference | [Concept A] | [Concept B] |
|---|---|---|

Cover dimensions such as: definition, constitutional basis, scope, applicability,
composition, powers, limitations, and any other aspects found in your notes.
Only compare aspects that appear in the context. Never use training knowledge.

Context:
{chunks}

Question: {question}""",

    "definition": """You are a UPSC study assistant.
Explain using ONLY the context. Structure your answer:

**Definition**: One clear, precise sentence
**Key Points**: Bullet points covering essential aspects from the context
**Significance**: Why it matters for UPSC (if apparent from context)
**Source**: Page numbers referenced

Never use training knowledge.

Context:
{chunks}

Question: {question}""",

    "enumerative": """You are a UPSC study assistant.
List ALL relevant items from the context. Rules:
1. Use a numbered list — do NOT skip any item found in your notes.
2. Each item: one clear sentence with the key detail.
3. If the context only partially covers the list, state what is missing.
4. Cite source pages for each item where possible.
Never use training knowledge. Only list what appears in the context.

Context:
{chunks}

Question: {question}""",

    "general": """You are a UPSC study assistant.
Answer the question naturally.
If the question is out of scope (e.g., a greeting, or not related to studies), respond politely and briefly.
If the question is related to studies but no context is available, state that you cannot find it in the notes.
If context is available and helpful, use it.

Context:
{chunks}

Question: {question}""",
}


# ── Chunk formatting ─────────────────────────────────────────────────

def format_chunks(chunks: list[dict], include_dates: bool = False) -> str:
    """Format retrieved chunks for LLM context.

    Sends parent_content for richer answers.  Dates are only included
    for current-affairs queries to avoid wasting context tokens.
    """
    parts = []
    for i, c in enumerate(chunks, 1):
        # Send parent_content to LLM — child was for retrieval precision,
        # parent captures the full topic section for answer quality
        text = c.get("parent_content") or c["content"]
        header = f"Chunk {i} [Source: page {c.get('page_number', '?')}]"
        if include_dates:
            header += f" [ingested_at: {c.get('ingested_at', '')}]"
        parts.append(f"{header}:\n{text}")
    return "\n\n---\n\n".join(parts)


# ── Synthesis ────────────────────────────────────────────────────────

async def synthesize(
    question: str,
    query_type: str,
    chunks: list[dict],
) -> dict:
    """Generate answer using the appropriate prompt template and Gemini model."""
    template = PROMPTS.get(query_type, PROMPTS["general"])

    # Build format kwargs — only "current" needs dates and today's date
    include_dates = query_type == "current"
    format_kwargs: dict = {
        "chunks": format_chunks(chunks, include_dates=include_dates),
        "question": question,
    }
    if include_dates:
        format_kwargs["today"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = template.format(**format_kwargs)

    # Use Pro for analytical (structured multi-point), Flash for the rest
    model = (
        settings.GEMINI_PRO_MODEL if query_type == "analytical" else settings.GEMINI_FLASH_MODEL
    )

    raw_answer = await call_gemini(
        prompt, model=model, response_schema=SynthesizerResponse
    )
    try:
        parsed = json.loads(raw_answer)
        answer = parsed.get("answer", "Could not generate answer.")
        confidence = parsed.get("confidence")
        used_indices = parsed.get("used_chunk_indices", [])
    except json.JSONDecodeError:
        answer = "Could not generate answer."
        confidence = None
        used_indices = []

    # Filter sources to only those actually cited by the LLM
    used_sources = []
    for idx in used_indices:
        # LLM returns 1-indexed (Chunk 1, Chunk 2...), we need 0-indexed
        i = idx - 1
        if 0 <= i < len(chunks):
            c = chunks[i]
            used_sources.append({
                "page": c.get("page_number"),
                "documentId": c.get("document_id"),
                "topicType": c.get("topic_type"),
            })
            
    # Fallback if the LLM forgot to include indices but still provided an answer
    if not used_sources and "not in your uploaded notes" not in answer.lower() and answer != "Could not generate answer.":
        used_sources = [
            {
                "page": c.get("page_number"),
                "documentId": c.get("document_id"),
                "topicType": c.get("topic_type"),
            }
            for c in chunks
        ]

    return {
        "answer": answer,
        "sources": used_sources,
        "query_type": query_type,
        "confidence": confidence,
    }
