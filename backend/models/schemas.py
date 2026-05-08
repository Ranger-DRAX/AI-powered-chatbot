from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    question: str
    course: Optional[str] = None
    category: Optional[str] = None
    session_id: Optional[str] = None

    @field_validator("question")
    @classmethod
    def question_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("question must not be empty")
        return value.strip()


class Source(BaseModel):
    course: str = ""
    category: str = ""
    file_name: str = ""
    source_path: str = ""
    page_start: str = ""
    page_end: str = ""
    distance: Optional[float] = None
    chunk_id: str = ""


class ChatResponse(BaseModel):
    answer: str
    status: str
    question: str
    detected_course_code: Optional[str] = None
    resolved_course: Optional[str] = None
    category: Optional[str] = None
    retrieval_mode: str = "global"
    retrieved_chunks: int = 0
    best_distance: Optional[float] = None
    sources: List[Source] = Field(default_factory=list)
