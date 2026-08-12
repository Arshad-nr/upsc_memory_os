"""
Two-stage Parent → Child chunker for the UPSC Memory OS pipeline.

Stage 1 — MarkdownHeaderTextSplitter: splits by #/##/### into logical
          sections (Parents).  Pure string ops, zero model calls.
Stage 2 — RecursiveCharacterTextSplitter: breaks each parent into
          embedding-safe children sized for BAAI/bge-base-en-v1.5 (512 tokens).

Replaces the old SemanticChunker which required an embedding call for
every sentence boundary — this version is ~100× faster on CPU.
"""

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from core.config import settings


# ── Stage 1 config: header levels to split on ────────────────────────
# pymupdf4llm emits #/##/### for document structure.
# Typical UPSC materials map to:
#   H1 → Chapter / Major topic
#   H2 → Section  (e.g. "Fundamental Rights")
#   H3 → Sub-topic (e.g. "Right to Equality")
_HEADERS_TO_SPLIT_ON = [
    ("#", "Header 1"),
    ("##", "Header 2"),
    ("###", "Header 3"),
]

# ── Stage 2 config: child chunk sizing ───────────────────────────────
#
# BAAI/bge-base-en-v1.5 hard limit: 512 WordPiece tokens.
# Conservative ratio:  1 token ≈ 3.5 chars  →  512 × 3.5 = 1 792 chars.
# Reserve ≤ 200 chars for the header-context prefix injected below.
# ⇒ child body budget = 1 500 chars  →  after prefix ≤ 1 700 chars ≈ 486 tok.
#
# Overlap at 200 chars (≈ 2-3 sentences) gives smooth context continuity
# across child boundaries without wasting too much embedding capacity.
_CHILD_CHUNK_SIZE = settings.CHILD_CHUNK_SIZE
_CHILD_CHUNK_OVERLAP = settings.CHILD_CHUNK_OVERLAP


# ── Singletons — no model loading, pure text ops ─────────────────────

_md_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=_HEADERS_TO_SPLIT_ON,
    strip_headers=False,  # keep headers in page_content for complete parent text, by default it would be stripped out and only available in metadata, but we need it in the parent_content for the header breadcrumb context
)

_child_splitter = RecursiveCharacterTextSplitter(
    chunk_size=_CHILD_CHUNK_SIZE,
    chunk_overlap=_CHILD_CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
    length_function=len,
)


# ── Public API ────────────────────────────────────────────────────────

def chunk_document(pages: list[dict]) -> list[dict]:
    """
    Hierarchical chunking:
      Stage 1 — MarkdownHeaderTextSplitter finds section boundaries → PARENTS
      Stage 2 — RecursiveCharacterTextSplitter splits each parent   → CHILDREN

    Child ``content`` (with header breadcrumb prefix) is embedded in Qdrant.
    Parent ``parent_content`` is stored alongside for LLM context.

    Returns
    -------
    list[dict]
        Each dict has: content, parent_content, page_number, chunk_index,
        token_count — matching the downstream DB / Qdrant pipeline.
    """
    chunks: list[dict] = []
    chunk_idx = 0

    for page in pages:
        page_num = page["page_number"]
        page_text = page["text"]

        if not page_text.strip():
            continue

        # Stage 1: split by markdown headers → parent sections
        parents = _md_splitter.split_text(page_text)

        if not parents:
            # No headers at all → treat the whole page as one parent
            parents = _make_fallback_docs(page_text)

        for parent_doc in parents:
            """LangChain Document has exactly two parts:
            page_content: A giant string containing the actual words text.
            metadata: A dictionary containing data about the text (like headers, page numbers, etc.)
            """
            parent_text = parent_doc.page_content 
            if not parent_text.strip():
                continue

            # Build a compact header breadcrumb for child embedding context
            header_prefix = _build_header_prefix(parent_doc.metadata)

            # Stage 2: split parent into embedding-safe children
            child_texts = _child_splitter.split_text(parent_text)

            for child_body in child_texts:
                if not child_body.strip():
                    continue

                # Inject header context so the embedding model
                # "knows" which document section this child belongs to.
                content = (
                    f"{header_prefix}{child_body}"
                    if header_prefix
                    else child_body
                )

                chunks.append({
                    "content": content,
                    "parent_content": parent_text,
                    "page_number": page_num,
                    "chunk_index": chunk_idx,
                    "token_count": len(content.split()),
                })
                chunk_idx += 1

    return chunks


# ── Helpers ───────────────────────────────────────────────────────────

def _build_header_prefix(metadata: dict) -> str:
    """
    Convert MarkdownHeaderTextSplitter metadata into a breadcrumb prefix.

    Example metadata::

        {"Header 1": "Indian Polity", "Header 2": "Fundamental Rights"}

    Returns::

        "# Indian Polity > ## Fundamental Rights\\n\\n"

    This breadcrumb is prepended to every child chunk so the embedding
    vector captures the section context, not just the body text.
    """
    if not metadata:
        return ""

    parts = []
    for key in ("Header 1", "Header 2", "Header 3"):
        value = metadata.get(key)
        if value:
            level = int(key.split()[-1])
            parts.append(f"{'#' * level} {value}")

    return " > ".join(parts) + "\n\n" if parts else ""


def _make_fallback_docs(text: str) -> list:
    """
    Minimal Document-like wrapper for pages that contain no markdown
    headers, so the main loop can iterate uniformly.
    """

    class _Doc:
        __slots__ = ("page_content", "metadata")

        def __init__(self, content: str):
            self.page_content = content
            self.metadata = {}

    return [_Doc(text)]
