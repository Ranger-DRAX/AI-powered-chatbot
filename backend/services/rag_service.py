import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer

from backend.models.schemas import ChatResponse, Source
from backend.services.course_detection import (
    detect_course_code,
    resolve_course_name,
    strip_course_code,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = (
    "Sorry, I could not find this information in the provided course materials. "
    "Please try asking with a course code, topic name, lecture name, or more specific question."
)

_embed_model: Optional[SentenceTransformer] = None
_chroma_client = None
_collection = None
_groq_client: Optional[Groq] = None
_available_courses_cache: Optional[List[str]] = None


class ConfigurationError(RuntimeError):
    pass


class ChromaUnavailableError(RuntimeError):
    pass


@dataclass
class RagConfig:
    groq_model: str
    chroma_dir: Path
    collection_name: str
    embedding_model: str
    top_k: int
    distance_threshold: float
    max_context_chars: int
    min_context_chars: int
    max_output_tokens: int
    temperature: float


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    distance: Optional[float]


def get_config() -> RagConfig:
    return RagConfig(
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        chroma_dir=Path(os.getenv("CHROMA_DIR", "vector_store/chroma")),
        collection_name=os.getenv("CHROMA_COLLECTION", "course_knowledge"),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        ),
        top_k=int(os.getenv("RAG_TOP_K", "4")),
        distance_threshold=float(os.getenv("RAG_DISTANCE_THRESHOLD", "0.90")),
        max_context_chars=int(os.getenv("RAG_MAX_CONTEXT_CHARS", "8000")),
        min_context_chars=int(os.getenv("RAG_MIN_CONTEXT_CHARS", "30")),
        max_output_tokens=int(os.getenv("RAG_MAX_OUTPUT_TOKENS", "700")),
        temperature=float(os.getenv("RAG_TEMPERATURE", "0.1")),
    )


def get_embed_model(model_name: str) -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        logger.info("Loading embedding model: %s", model_name)
        _embed_model = SentenceTransformer(model_name, device="cpu")
    return _embed_model


def get_chroma_collection(config: RagConfig):
    global _chroma_client, _collection
    if _collection is None:
        if not config.chroma_dir.exists():
            raise ChromaUnavailableError(
                f"ChromaDB directory not found: {config.chroma_dir}. Run Stage 3 first."
            )

        logger.info(
            "Connecting to ChromaDB at %s collection=%s",
            config.chroma_dir,
            config.collection_name,
        )
        _chroma_client = chromadb.PersistentClient(
            path=str(config.chroma_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        try:
            _collection = _chroma_client.get_collection(config.collection_name)
        except Exception as exc:
            raise ChromaUnavailableError(
                f"ChromaDB collection '{config.collection_name}' is not available."
            ) from exc
    return _collection


def get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ConfigurationError("GROQ_API_KEY is not set.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def load_available_courses_from_collection(collection) -> List[str]:
    result = collection.get(include=["metadatas"])
    metadatas = result.get("metadatas", [])
    return sorted(
        {
            metadata.get("course")
            for metadata in metadatas
            if isinstance(metadata, dict) and metadata.get("course")
        }
    )


def get_available_courses(collection) -> List[str]:
    global _available_courses_cache
    if _available_courses_cache is None:
        logger.info("Loading available course names from Chroma metadata.")
        _available_courses_cache = load_available_courses_from_collection(collection)
        logger.info("Loaded %s course names.", len(_available_courses_cache))
    return _available_courses_cache


def build_where_filter(
    course: Optional[str],
    category: Optional[str],
) -> Optional[Dict[str, Any]]:
    conditions = []
    if course:
        conditions.append({"course": course})
    if category:
        conditions.append({"category": category})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _embedding_to_list(embedding: Any) -> List[float]:
    if hasattr(embedding, "tolist"):
        embedding = embedding.tolist()
    if isinstance(embedding, list) and embedding and isinstance(embedding[0], list):
        return embedding[0]
    return embedding


def retrieve_relevant_chunks(
    question: str,
    collection,
    embedding_model: SentenceTransformer,
    top_k: int,
    course: Optional[str],
    category: Optional[str],
) -> List[RetrievedChunk]:
    encoded = embedding_model.encode(
        [question],
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    query_embedding = _embedding_to_list(encoded)

    query_args: Dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }

    where_filter = build_where_filter(course=course, category=category)
    if where_filter:
        query_args["where"] = where_filter

    result = collection.query(**query_args)
    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    chunks: List[RetrievedChunk] = []
    for index, chunk_id in enumerate(ids):
        chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                text=documents[index] if index < len(documents) else "",
                metadata=metadatas[index] if index < len(metadatas) else {},
                distance=distances[index] if index < len(distances) else None,
            )
        )
    return chunks


def should_fallback(
    chunks: List[RetrievedChunk],
    distance_threshold: float,
    min_context_chars: int,
) -> Tuple[bool, str]:
    if not chunks:
        return True, "No chunks retrieved."

    best_distance = chunks[0].distance
    if best_distance is None:
        return True, "Best distance is missing."

    if best_distance > distance_threshold:
        return True, (
            f"Best distance {best_distance:.4f} is above threshold "
            f"{distance_threshold:.4f}."
        )

    context_chars = sum(len(chunk.text.strip()) for chunk in chunks)
    if context_chars < min_context_chars:
        return True, f"Retrieved context is too small: {context_chars} characters."

    return False, "Relevant context found."


def build_sources(chunks: Iterable[RetrievedChunk]) -> List[Source]:
    sources: List[Source] = []
    seen = set()

    for chunk in chunks:
        metadata = chunk.metadata or {}
        source_path = str(metadata.get("source_path", ""))
        page_start = str(metadata.get("page_start", ""))
        page_end = str(metadata.get("page_end", ""))
        key = (source_path, page_start, page_end, chunk.chunk_id)
        if key in seen:
            continue
        seen.add(key)

        sources.append(
            Source(
                course=str(metadata.get("course", "")),
                category=str(metadata.get("category", "")),
                file_name=str(metadata.get("file_name", "")),
                source_path=source_path,
                page_start=page_start,
                page_end=page_end,
                distance=chunk.distance,
                chunk_id=str(metadata.get("chunk_id") or chunk.chunk_id),
            )
        )
    return sources


def truncate_text(text: str, max_chars: int) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n...[truncated]"


def format_context(chunks: List[RetrievedChunk], max_context_chars: int) -> str:
    blocks = []
    used_chars = 0

    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata or {}
        label = (
            f"[Source {index}]\n"
            f"Course: {metadata.get('course', '')}\n"
            f"Category: {metadata.get('category', '')}\n"
            f"File: {metadata.get('file_name', '')}\n"
            f"Path: {metadata.get('source_path', '')}\n"
            f"Page range: {metadata.get('page_start', '')}-{metadata.get('page_end', '')}\n"
            f"Distance: {chunk.distance}\n"
            "Content:\n"
        )
        remaining = max_context_chars - used_chars - len(label)
        if remaining <= 200:
            break

        text = truncate_text(chunk.text, remaining)
        block = label + text
        blocks.append(block)
        used_chars += len(block)

        if used_chars >= max_context_chars:
            break

    return "\n\n" + ("\n\n" + "-" * 80 + "\n\n").join(blocks)


def build_system_prompt() -> str:
    return """
You are UniBot, a university course assistant for a course-material-based chatbot.

Rules:
1. Answer ONLY from the provided course context.
2. Do NOT use outside knowledge.
3. If the context does not contain the answer, say:
   "Sorry, I could not find this information in the provided course materials."
4. Be accurate, clear, and student-friendly.
5. Do not invent page numbers, lecture names, definitions, examples, or facts.
""".strip()


def build_user_prompt(
    question: str,
    context: str,
    course: Optional[str],
    category: Optional[str],
) -> str:
    course_line = f"Resolved course: {course}" if course else "Resolved course: Not specified"
    category_line = f"Category: {category}" if category else "Category: Not specified"
    return f"""
{course_line}
{category_line}

Retrieved course context:
{context}

Student question:
{question}

Answer the student's question using only the retrieved course context.
""".strip()


def call_groq(
    question: str,
    context: str,
    course: Optional[str],
    category: Optional[str],
    config: RagConfig,
) -> str:
    logger.info("Groq call started.")
    client = get_groq_client()
    try:
        completion = client.chat.completions.create(
            model=config.groq_model,
            messages=[
                {"role": "system", "content": build_system_prompt()},
                {
                    "role": "user",
                    "content": build_user_prompt(question, context, course, category),
                },
            ],
            temperature=config.temperature,
            max_completion_tokens=config.max_output_tokens,
        )
    except TypeError:
        completion = client.chat.completions.create(
            model=config.groq_model,
            messages=[
                {"role": "system", "content": build_system_prompt()},
                {
                    "role": "user",
                    "content": build_user_prompt(question, context, course, category),
                },
            ],
            temperature=config.temperature,
            max_tokens=config.max_output_tokens,
        )

    answer = (completion.choices[0].message.content or "").strip()
    logger.info("Groq call completed.")
    return answer


def _response(
    *,
    answer: str,
    status: str,
    question: str,
    detected_course_code: Optional[str],
    resolved_course: Optional[str],
    category: Optional[str],
    retrieval_mode: str,
    retrieved_chunks: int = 0,
    best_distance: Optional[float] = None,
    sources: Optional[List[Source]] = None,
) -> ChatResponse:
    return ChatResponse(
        answer=answer,
        status=status,
        question=question,
        detected_course_code=detected_course_code,
        resolved_course=resolved_course,
        category=category,
        retrieval_mode=retrieval_mode,
        retrieved_chunks=retrieved_chunks,
        best_distance=best_distance,
        sources=sources or [],
    )


async def get_rag_response(
    question: str,
    explicit_course: Optional[str] = None,
    category: Optional[str] = None,
) -> ChatResponse:
    config = get_config()
    detected_course_code = detect_course_code(question)
    retrieval_question = strip_course_code(question) if detected_course_code else question
    requested_course = explicit_course or detected_course_code
    resolved_course: Optional[str] = None
    retrieval_mode = "global"

    logger.info("Question: %s", question)
    logger.info("Detected course code: %s", detected_course_code)

    try:
        collection = get_chroma_collection(config)

        if requested_course:
            available_courses = get_available_courses(collection)
            resolved_course = resolve_course_name(requested_course, available_courses)
            if resolved_course:
                retrieval_mode = "course_filtered"
            else:
                logger.info(
                    "Course '%s' could not be resolved. Falling back to global retrieval.",
                    requested_course,
                )

        logger.info("Resolved course: %s", resolved_course)
        logger.info("Retrieval mode: %s", retrieval_mode)

        embedding_model = get_embed_model(config.embedding_model)
        chunks = retrieve_relevant_chunks(
            question=retrieval_question,
            collection=collection,
            embedding_model=embedding_model,
            top_k=config.top_k,
            course=resolved_course,
            category=category,
        )

        best_distance = chunks[0].distance if chunks else None
        logger.info("Retrieved chunk count: %s", len(chunks))
        logger.info("Best distance: %s", best_distance)

        fallback, fallback_reason = should_fallback(
            chunks=chunks,
            distance_threshold=config.distance_threshold,
            min_context_chars=config.min_context_chars,
        )

        if fallback:
            logger.info("Fallback triggered: %s", fallback_reason)
            return _response(
                answer=FALLBACK_MESSAGE,
                status="fallback",
                question=question,
                detected_course_code=detected_course_code,
                resolved_course=resolved_course,
                category=category,
                retrieval_mode=retrieval_mode,
                retrieved_chunks=len(chunks),
                best_distance=best_distance,
                sources=[],
            )

        context = format_context(chunks, config.max_context_chars)
        answer = call_groq(
            question=question,
            context=context,
            course=resolved_course,
            category=category,
            config=config,
        )

        if not answer:
            answer = (
                "Sorry, I found relevant course materials, but I could not generate "
                "a proper answer at this moment."
            )

        return _response(
            answer=answer,
            status="answered",
            question=question,
            detected_course_code=detected_course_code,
            resolved_course=resolved_course,
            category=category,
            retrieval_mode=retrieval_mode,
            retrieved_chunks=len(chunks),
            best_distance=best_distance,
            sources=build_sources(chunks),
        )

    except ChromaUnavailableError as exc:
        logger.error("ChromaDB unavailable: %s", exc)
        return _response(
            answer=str(exc),
            status="error",
            question=question,
            detected_course_code=detected_course_code,
            resolved_course=resolved_course,
            category=category,
            retrieval_mode=retrieval_mode,
            sources=[],
        )
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        return _response(
            answer=f"Configuration error: {exc}",
            status="error",
            question=question,
            detected_course_code=detected_course_code,
            resolved_course=resolved_course,
            category=category,
            retrieval_mode=retrieval_mode,
            sources=[],
        )
    except Exception as exc:
        logger.exception("Unexpected RAG error: %s", exc)
        return _response(
            answer="I encountered an unexpected error processing your request. Please try again later.",
            status="error",
            question=question,
            detected_course_code=detected_course_code,
            resolved_course=resolved_course,
            category=category,
            retrieval_mode=retrieval_mode,
            sources=[],
        )
