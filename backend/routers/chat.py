import logging

from fastapi import APIRouter
from models.schemas import ChatRequest, ChatResponse
from services.dummy_response import get_dummy_response

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Handle an incoming chat message and return a dummy response.
    Logs session_id, course, and a snippet of the message.
    """
    snippet = request.message[:80] + ("..." if len(request.message) > 80 else "")
    logger.info(
        "Chat request | session_id=%s | course=%s | message='%s'",
        request.session_id,
        request.course,
        snippet,
    )

    reply, confidence, source = await get_dummy_response(
        message=request.message,
        course=request.course,
    )

    return ChatResponse(
        reply=reply,
        confidence=confidence,
        source=source,
        session_id=request.session_id,
    )
