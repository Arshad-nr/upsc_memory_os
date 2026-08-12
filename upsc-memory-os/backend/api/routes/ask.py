"""RAG Q&A endpoint — classify → retrieve → synthesize."""

import asyncio

from fastapi import APIRouter, Depends


from api.dependencies import get_current_user
from core.database import User
from core.vector_store import retrieve_hybrid
from services.rag.classifier import classify_query, dynamic_k
from services.rag.synthesizer import synthesize
from models.schemas import AskRequest, AskResponse

router = APIRouter(prefix="/api/v1/ask", tags=["RAG"])


@router.post("", response_model=AskResponse)
async def ask(
    body: AskRequest,
    user: User = Depends(get_current_user),
):
    """
    End-to-end RAG:
    1. Classify query type (factual/analytical/current/comparative/definition/enumerative)
    2. Retrieve hybrid results from Qdrant (dense + sparse, user-isolated)
    3. Synthesize answer with query-type-specific prompt
    """
    # Step 0: Catch basic greetings instantly
    import re
    if re.search(r"^(hi|hello|hey|greetings|how are you|good morning|good evening|thanks|thank you)[\s.!?]*$", body.question.strip(), re.IGNORECASE):
        return AskResponse(
            answer="Hello! I am your UPSC Memory OS assistant. Ask me any question from your uploaded study materials!",
            sources=[],
            query_type="greeting",
        )

    # Step 1: Classify
    query_type = await asyncio.to_thread(classify_query, body.question)

    # Step 2: Retrieve (dynamic k based on query type)
    # retrieve_hybrid is synchronous (embedding + Qdrant I/O) — offload to thread
    k = dynamic_k(query_type)
    chunks = await asyncio.to_thread(retrieve_hybrid, str(user.id), body.question, k)

    # Step 3: Handle no results
    if not chunks:
        return AskResponse(
            answer="This is not in your uploaded notes.",
            sources=[],
            query_type=query_type,
        )

    # Step 4: Synthesize
    result = await synthesize(body.question, query_type, chunks)

    return AskResponse(
        answer=result["answer"],
        sources=result["sources"],
        query_type=result["query_type"],
        confidence=result.get("confidence") or "LOW",
    )
