"""Query classifier — routes questions to the right RAG prompt.

Tier 1: Instant regex matching for standard UPSC question patterns (<1ms).
Tier 2: Gemini Flash LLM fallback for ambiguous queries (~4s).
"""

import re
from typing import Optional

# ── Keyword patterns (ordered by specificity) ────────────────────────
# UPSC questions follow highly standardised patterns.
# These regexes catch ~70-80 % of queries, saving an LLM call + 4-12 s.

_PATTERNS: dict[str, re.Pattern] = {
    # ── Must be checked FIRST — most distinctive markers ─────────
    "analytical": re.compile(
        r"critically\s+\w+"                              # "Critically examine…"
        r"|(?:evaluate|assess|analyze|analyse|examine"
        r"|discuss)\s+the\s+(?:role|impact|significance"
        r"|implications|challenges|importance"
        r"|effectiveness|merits|demerits)"               # "Evaluate the role of…"
        r"|comment\s+on\b"                               # "Comment on…"
        r"|what\s+are\s+the\s+(?:implications"
        r"|challenges|advantages|disadvantages"
        r"|merits|demerits|pros|cons)"                   # "What are the challenges…"
        r"|(?:explain|discuss)\s+the\s+(?:significance"
        r"|impact|role|importance|implications)\b",      # "Explain the significance…"
        re.IGNORECASE,
    ),
    "comparative": re.compile(
        r"differ(?:ence|ences|entiate)?\s+between\b"     # "Difference between X and Y"
        r"|distinguish\s+between\b"                      # "Distinguish between…"
        r"|compare\s+(?:and\s+contrast\s+)?"             # "Compare and contrast…"
        r"|\bvs\.?\b"                                    # "X vs Y"
        r"|\bversus\b",
        re.IGNORECASE,
    ),
    # ── Time-sensitive ────────────────────────────────────────────
    "current": re.compile(
        r"\b(?:recent|latest)\b"                         # "recent developments"
        r"|\b20(?:2[4-9]|[3-9]\d)\b"                    # year ≥ 2024
        r"|\bcurrent\s+affairs?\b"
        r"|\bbudget\s+20\d{2}\b",
        re.IGNORECASE,
    ),
    # ── Conceptual / explanatory ─────────────────────────────────
    "definition": re.compile(
        r"^(?:what\s+is|what\s+are)\b"                   # "What is federalism?"
        r"|^define\b"                                    # "Define sovereignty"
        r"|^explain\b(?!\s+the\s+(?:significance|impact" # "Explain X" but NOT
        r"|role|importance|implications))"               #   "Explain the significance…"
        r"|what\s+do\s+you\s+(?:mean|understand)\s+by\b",
        re.IGNORECASE,
    ),
    # ── Direct-fact queries ──────────────────────────────────────
    "factual": re.compile(
        r"\b(?:which|what)\s+(?:article|amendment"
        r"|committee|commission|act|scheme|body)\b"      # "Which article…"
        r"|^(?:when|where)\s+(?:was|did|is|are)\b"       # "When was X?"
        r"|^who\s+(?:was|is|founded|established"
        r"|chaired|headed|appointed)\b"                  # "Who chaired…"
        r"|^how\s+many\b"                                # "How many states…"
        r"|in\s+which\s+year\b",                         # "In which year…"
        re.IGNORECASE,
    ),
    # ── Enumerative / list queries ────────────────────────────────
    "enumerative": re.compile(
        r"^(?:list|enumerate|mention|state)\s+the\b"     # "List the functions…"
        r"|^name\s+the\b"                                # "Name the members…"
        r"|what\s+are\s+the\s+(?:features|functions"
        r"|objectives|components|types|provisions"
        r"|powers|duties|principles|elements"
        r"|characteristics|causes|effects"
        r"|factors|measures|steps|reforms)\b"            # "What are the features of…"
        r"|how\s+many\s+types\b",                        # "How many types of…"
        re.IGNORECASE,
    ),
}


def _classify_by_keywords(question: str) -> Optional[str]:
    """
    Fast keyword classification.  Returns the query type if a confident
    match is found, or ``None`` for ambiguous queries that need the LLM.

    Patterns are checked in order of specificity so that, for example,
    "What are the challenges…" matches *analytical* before it could
    reach *definition* via "What are…".
    """
    for qtype in ("analytical", "comparative", "current", "enumerative", "definition", "factual"):
        if _PATTERNS[qtype].search(question):
            return qtype
    return None


async def classify_query(question: str) -> str:
    """Classify a UPSC question into one of 6 types.

    Tier 1: keyword match (~70-80 % of queries, <1 ms)
    Tier 2: Fast default to 'analytical' (saves an API call!)
    """
    # Tier 1: instant keyword match
    result = _classify_by_keywords(question)
    if result:
        return result

    # Tier 2: Default to analytical instead of using an LLM to save quota
    return "analytical"


def dynamic_k(query_type: str) -> int:
    """Return number of chunks to retrieve based on query type."""
    return {
        "factual": 3,
        "analytical": 7,
        "current": 5,
        "comparative": 6,
        "definition": 4,
        "enumerative": 6,
    }.get(query_type, 5)
