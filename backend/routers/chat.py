import logging

from fastapi import APIRouter

from backend.models.schemas import ChatRequest, ChatResponse
from backend.services.rag_service import get_rag_response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    snippet = request.question[:120] + ("..." if len(request.question) > 120 else "")
    logger.info(
        "Chat request received | session_id=%s | course=%s | category=%s | question='%s'",
        request.session_id,
        request.course,
        request.category,
        snippet,
    )

    return await get_rag_response(
        question=request.question,
        explicit_course=request.course,
        category=request.category,
    )
