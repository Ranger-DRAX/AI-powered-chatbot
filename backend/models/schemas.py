# pyrefly: ignore [missing-import]
from pydantic import BaseModel
    

class ChatRequest(BaseModel):
    message: str
    course: str = "General"
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    confidence: float
    source: str
    session_id: str
