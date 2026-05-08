from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import rag_service
from backend.services.course_detection import (
    detect_course_code,
    resolve_course_name,
    strip_course_code,
)

client = TestClient(app)

AVAILABLE_COURSES = [
    "CSE220_Data_Structure",
    "CSE340_Computer_Architecture",
    "CSE422_Artificial_Intelligence",
    "HST103_History_of_Bangladesh",
]


class FakeCollection:
    def get(self, include=None):
        return {"metadatas": [{"course": course} for course in AVAILABLE_COURSES]}


def make_chunk(distance=0.5, text=None):
    return rag_service.RetrievedChunk(
        chunk_id="chunk-1",
        text=text
        or "An array is a data structure that stores elements in contiguous memory locations.",
        metadata={
            "course": "CSE220_Data_Structure",
            "category": "Notes",
            "file_name": "Array-Part-1.docx.pdf",
            "source_path": "CSE220_Data_Structure/Notes/Array-Part-1.docx.pdf",
            "page_start": "",
            "page_end": "",
            "chunk_id": "chunk-1",
        },
        distance=distance,
    )


def patch_rag_basics(monkeypatch):
    monkeypatch.setattr(rag_service, "_collection", None)
    monkeypatch.setattr(rag_service, "_available_courses_cache", None)
    monkeypatch.setattr(rag_service, "get_chroma_collection", lambda config: FakeCollection())
    monkeypatch.setattr(rag_service, "get_embed_model", lambda model_name: object())


def test_health_endpoint_returns_success():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_endpoint_validates_missing_or_empty_question():
    assert client.post("/api/chat", json={}).status_code == 422
    assert client.post("/api/chat", json={"question": "   "}).status_code == 422


def test_course_detection_variants():
    assert detect_course_code("What is an array in CSE220?") == "CSE220"
    assert detect_course_code("Explain datapath from CSE 340") == "CSE340"
    assert detect_course_code("Review CSE-422 search") == "CSE422"
    assert detect_course_code("Summarize HST_103") == "HST103"
    assert detect_course_code("query without course code") is None
    assert strip_course_code("What is an array in CSE220?") == "What is an array?"


def test_course_resolution_variants():
    assert resolve_course_name("CSE220", AVAILABLE_COURSES) == "CSE220_Data_Structure"
    assert resolve_course_name("CSE 340", AVAILABLE_COURSES) == "CSE340_Computer_Architecture"
    assert (
        resolve_course_name("CSE340_Computer_Architecture", AVAILABLE_COURSES)
        == "CSE340_Computer_Architecture"
    )
    assert resolve_course_name("ABC999", AVAILABLE_COURSES) is None


def test_query_without_course_code_uses_global_retrieval(monkeypatch):
    patch_rag_basics(monkeypatch)

    captured = {}

    def fake_retrieve(question, collection, embedding_model, top_k, course, category):
        captured["course"] = course
        return []

    monkeypatch.setattr(rag_service, "retrieve_relevant_chunks", fake_retrieve)
    groq = Mock()
    monkeypatch.setattr(rag_service, "call_groq", groq)

    response = client.post("/api/chat", json={"question": "What is an array?"})

    assert response.status_code == 200
    data = response.json()
    assert data["retrieval_mode"] == "global"
    assert data["detected_course_code"] is None
    assert captured["course"] is None
    assert groq.called is False


def test_unknown_course_code_falls_back_to_global_search(monkeypatch):
    patch_rag_basics(monkeypatch)

    captured = {}

    def fake_retrieve(question, collection, embedding_model, top_k, course, category):
        captured["course"] = course
        return []

    monkeypatch.setattr(rag_service, "retrieve_relevant_chunks", fake_retrieve)
    monkeypatch.setattr(rag_service, "call_groq", Mock())

    response = client.post("/api/chat", json={"question": "Explain sorting in ABC999"})

    assert response.status_code == 200
    data = response.json()
    assert data["detected_course_code"] == "ABC999"
    assert data["resolved_course"] is None
    assert data["retrieval_mode"] == "global"
    assert captured["course"] is None


def test_high_best_distance_returns_fallback_and_skips_groq(monkeypatch):
    patch_rag_basics(monkeypatch)
    monkeypatch.setattr(
        rag_service,
        "retrieve_relevant_chunks",
        lambda *args, **kwargs: [make_chunk(distance=0.95)],
    )
    groq = Mock(return_value="should not be called")
    monkeypatch.setattr(rag_service, "call_groq", groq)

    response = client.post("/api/chat", json={"question": "What is an array in CSE220?"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "fallback"
    assert data["sources"] == []
    assert groq.called is False


def test_answered_relevant_retrieval_calls_groq_and_returns_sources(monkeypatch):
    patch_rag_basics(monkeypatch)
    monkeypatch.setattr(
        rag_service,
        "retrieve_relevant_chunks",
        lambda *args, **kwargs: [make_chunk(distance=0.42)],
    )
    groq = Mock(return_value="An array stores elements in contiguous memory.")
    monkeypatch.setattr(rag_service, "call_groq", groq)

    response = client.post(
        "/api/chat",
        json={"question": "What is an array?", "course": "CSE220"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "answered"
    assert data["resolved_course"] == "CSE220_Data_Structure"
    assert data["retrieval_mode"] == "course_filtered"
    assert "array" in data["answer"].lower()
    assert len(data["sources"]) == 1
    assert groq.called is True


def test_groq_error_is_handled_gracefully(monkeypatch):
    patch_rag_basics(monkeypatch)
    monkeypatch.setattr(
        rag_service,
        "retrieve_relevant_chunks",
        lambda *args, **kwargs: [make_chunk(distance=0.42)],
    )
    monkeypatch.setattr(rag_service, "call_groq", Mock(side_effect=RuntimeError("boom")))

    response = client.post("/api/chat", json={"question": "What is an array in CSE220?"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert data["sources"] == []
    assert "unexpected error" in data["answer"].lower()


def test_missing_chromadb_path_is_handled_gracefully(monkeypatch, tmp_path):
    monkeypatch.setattr(rag_service, "_collection", None)
    monkeypatch.setattr(rag_service, "_available_courses_cache", None)
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "missing-chroma"))

    response = client.post("/api/chat", json={"question": "What is an array in CSE220?"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "error"
    assert "ChromaDB directory not found" in data["answer"]
    assert data["sources"] == []
