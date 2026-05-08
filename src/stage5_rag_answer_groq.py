import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer

from backend.services.course_detection import detect_course_code, strip_course_code


FALLBACK_MESSAGE = (
    "Sorry, I could not find this information in the provided course materials. "
    "Please try asking with a course code, topic name, lecture name, or more specific question."
)


@dataclass
class RetrievedChunk:
    chunk_id: str
    text: str
    metadata: Dict[str, Any]
    distance: Optional[float]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_groq_client() -> Groq:
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is missing. Add it to your .env file:\n"
            "GROQ_API_KEY=your_groq_api_key_here"
        )

    return Groq(api_key=api_key)


def get_groq_model(cli_model: Optional[str]) -> str:
    if cli_model:
        return cli_model

    load_dotenv()
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def load_chroma_collection(chroma_dir: Path, collection_name: str):
    if not chroma_dir.exists():
        raise FileNotFoundError(
            f"Chroma directory not found: {chroma_dir}\n"
            "Run Stage 3 embedding first."
        )

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False),
    )

    return client.get_collection(collection_name)


def build_where_filter(course: Optional[str], category: Optional[str]) -> Optional[Dict[str, Any]]:
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


def retrieve_chunks(
    question: str,
    model: SentenceTransformer,
    collection,
    top_k: int,
    course: Optional[str],
    category: Optional[str],
) -> List[RetrievedChunk]:
    query_embedding = model.encode(
        [question],
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0].tolist()

    query_args = {
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

    for i, chunk_id in enumerate(ids):
        chunks.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                text=documents[i] if i < len(documents) else "",
                metadata=metadatas[i] if i < len(metadatas) else {},
                distance=distances[i] if i < len(distances) else None,
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

    total_context_chars = sum(len(chunk.text.strip()) for chunk in chunks)

    if total_context_chars < min_context_chars:
        return True, f"Retrieved context is too small: {total_context_chars} characters."

    return False, "Relevant context found."


def truncate_text(text: str, max_chars: int) -> str:
    text = text.strip()

    if len(text) <= max_chars:
        return text

    return text[:max_chars].rstrip() + "\n...[truncated]"


def format_context(chunks: List[RetrievedChunk], max_context_chars: int) -> str:
    context_blocks = []
    used_chars = 0

    for idx, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata

        course = metadata.get("course", "unknown_course")
        category = metadata.get("category", "unknown_category")
        file_name = metadata.get("file_name", "unknown_file")
        source_path = metadata.get("source_path", "")
        page_start = metadata.get("page_start", "")
        page_end = metadata.get("page_end", "")
        distance = chunk.distance

        source_label = (
            f"[Source {idx}]\n"
            f"Course: {course}\n"
            f"Category: {category}\n"
            f"File: {file_name}\n"
            f"Path: {source_path}\n"
            f"Page range: {page_start}-{page_end}\n"
            f"Distance: {distance}\n"
            f"Content:\n"
        )

        remaining_chars = max_context_chars - used_chars - len(source_label)

        if remaining_chars <= 200:
            break

        chunk_text = truncate_text(chunk.text, remaining_chars)
        block = source_label + chunk_text

        context_blocks.append(block)
        used_chars += len(block)

        if used_chars >= max_context_chars:
            break

    return "\n\n" + ("\n\n" + "-" * 80 + "\n\n").join(context_blocks)


def build_sources(chunks: List[RetrievedChunk]) -> List[Dict[str, Any]]:
    sources = []
    seen = set()

    for chunk in chunks:
        metadata = chunk.metadata

        source_path = metadata.get("source_path", "")
        file_name = metadata.get("file_name", "")
        course = metadata.get("course", "")
        category = metadata.get("category", "")
        page_start = metadata.get("page_start", "")
        page_end = metadata.get("page_end", "")

        key = (source_path, page_start, page_end)

        if key in seen:
            continue

        seen.add(key)

        sources.append(
            {
                "course": metadata.get("course"),
                "category": category,
                "file_name": file_name,
                "source_path": source_path,
                "page_start": page_start,
                "page_end": page_end,
                "distance": chunk.distance,
                "chunk_id": chunk.chunk_id,
            }
        )

    return sources


def build_system_prompt() -> str:
    return """
You are a university course assistant for a course-material-based chatbot.

You must follow these rules strictly:

1. Answer ONLY using the provided course context.
2. Do NOT use outside knowledge.
3. If the answer is not present in the context, say:
   "Sorry, I could not find this information in the provided course materials."
4. Be accurate, clear, and student-friendly.
5. If the student asks for code or explanation, use the course context and explain step by step.
6. Mention source file names briefly when useful.
7. Do not invent page numbers, lecture names, definitions, examples, or facts.
8. If the context contains multiple possible answers, explain the most relevant one and mention the source.
""".strip()


def build_user_prompt(
    question: str,
    context: str,
    course: Optional[str],
    category: Optional[str],
) -> str:
    course_line = f"Selected course: {course}" if course else "Selected course: Not specified"
    category_line = f"Selected category: {category}" if category else "Selected category: Not specified"

    return f"""
{course_line}
{category_line}

Retrieved course context:
{context}

Student question:
{question}

Now answer the student's question using only the retrieved course context.
""".strip()


def generate_answer_with_groq(
    client: Groq,
    model_name: str,
    question: str,
    context: str,
    course: Optional[str],
    category: Optional[str],
    max_output_tokens: int,
    temperature: float,
) -> str:
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(
        question=question,
        context=context,
        course=course,
        category=category,
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        {
            "role": "user",
            "content": user_prompt,
        },
    ]

    try:
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_completion_tokens=max_output_tokens,
        )
    except TypeError:
        completion = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
        )
    except Exception as exc:
        return (
            "I found relevant course materials, but the Groq answer generation service "
            f"returned an error: {type(exc).__name__}: {str(exc)}"
        )

    try:
        answer = completion.choices[0].message.content
        return (answer or "").strip()
    except Exception:
        return ""

def get_available_courses(collection) -> List[str]:
    """
    Reads unique course names from Chroma metadata.
    For this project size, scanning metadata is acceptable.
    In backend integration, cache this result at startup.
    """
    result = collection.get(include=["metadatas"])
    metadatas = result.get("metadatas", [])

    courses = sorted({
        metadata.get("course")
        for metadata in metadatas
        if isinstance(metadata, dict) and metadata.get("course")
    })

    return courses


def normalize_course_code(value: str) -> str:
    """
    Converts:
    CSE220, CSE 220, CSE-220, cse_220
    into:
    CSE220
    """
    import re

    value = value.upper().strip()
    match = re.search(r"\b([A-Z]{2,4})[\s_-]?(\d{3})\b", value)

    if not match:
        return value.replace(" ", "").replace("-", "").replace("_", "")

    return f"{match.group(1)}{match.group(2)}"


def resolve_course_name(collection, requested_course: Optional[str]) -> Optional[str]:
    """
    Maps short course code to stored metadata course name.

    Example:
    CSE220 -> CSE220_Data_Structure
    CSE340 -> CSE340_Computer_Architecture
    """
    if not requested_course:
        return None

    available_courses = get_available_courses(collection)

    # Exact match first
    if requested_course in available_courses:
        return requested_course

    requested_code = normalize_course_code(requested_course)

    for course in available_courses:
        course_code = normalize_course_code(course)

        if course_code == requested_code:
            return course

        if course.upper().startswith(requested_code):
            return course

    return None

def answer_question(
    question: str,
    course: Optional[str],
    category: Optional[str],
    chroma_dir: Path,
    collection_name: str,
    embedding_model_name: str,
    groq_model_name: str,
    top_k: int,
    distance_threshold: float,
    min_context_chars: int,
    max_context_chars: int,
    max_output_tokens: int,
    temperature: float,
    no_llm: bool,
) -> Dict[str, Any]:
    collection = load_chroma_collection(
        chroma_dir=chroma_dir,
        collection_name=collection_name,
    )

    detected_course_code = detect_course_code(question)
    retrieval_question = strip_course_code(question) if detected_course_code else question
    requested_course = course or detected_course_code
    resolved_course = resolve_course_name(collection, requested_course)

    if requested_course and not resolved_course:
        print(f"[Stage 5] Course '{requested_course}' was not found in metadata. Searching globally.")

    embedding_model = SentenceTransformer(
        embedding_model_name,
        device="cpu",
    )

    chunks = retrieve_chunks(
        question=retrieval_question,
        model=embedding_model,
        collection=collection,
        top_k=top_k,
        course=resolved_course,
        category=category,
    )

    fallback, fallback_reason = should_fallback(
        chunks=chunks,
        distance_threshold=distance_threshold,
        min_context_chars=min_context_chars,
    )

    sources = build_sources(chunks)

    if fallback:
        return {
            "answer": FALLBACK_MESSAGE,
            "status": "fallback",
            "fallback_reason": fallback_reason,
            "question": question,
            "detected_course_code": detected_course_code,
            "resolved_course": resolved_course,
            "requested_course": course,
            "retrieval_mode": "course_filtered" if resolved_course else "global",
            "category": category,
            "retrieved_chunks": len(chunks),
            "best_distance": chunks[0].distance if chunks else None,
            "sources": [],
            "created_at_utc": utc_now(),
        }

    context = format_context(
        chunks=chunks,
        max_context_chars=max_context_chars,
    )

    if no_llm:
        return {
            "answer": "[NO_LLM_MODE] Retrieval succeeded. Groq call was skipped.",
            "status": "retrieval_only",
            "fallback_reason": fallback_reason,
            "question": question,
            "detected_course_code": detected_course_code,
            "resolved_course": resolved_course,
            "requested_course": course,
            "retrieval_mode": "course_filtered" if resolved_course else "global",
            "category": category,
            "retrieved_chunks": len(chunks),
            "best_distance": chunks[0].distance if chunks else None,
            "context_preview": context[:3000],
            "sources": sources,
            "created_at_utc": utc_now(),
        }

    client = load_groq_client()

    answer = generate_answer_with_groq(
        client=client,
        model_name=groq_model_name,
        question=question,
        context=context,
        course=resolved_course,
        category=category,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )

    if not answer:
        answer = (
            "Sorry, I found relevant course materials, but I could not generate "
            "a proper answer at this moment."
        )

    return {
        "answer": answer,
        "status": "answered",
        "fallback_reason": fallback_reason,
        "question": question,
        "detected_course_code": detected_course_code,
        "resolved_course": resolved_course,
        "requested_course": course,
        "retrieval_mode": "course_filtered" if resolved_course else "global",
        "category": category,
        "retrieved_chunks": len(chunks),
        "best_distance": chunks[0].distance if chunks else None,
        "sources": sources,
        "created_at_utc": utc_now(),
    }


def print_human_readable(result: Dict[str, Any]) -> None:
    print("\n" + "=" * 100)
    print("ANSWER")
    print("=" * 100)
    print(result.get("answer", ""))

    print("\n" + "=" * 100)
    print("DEBUG")
    print("=" * 100)
    print(f"Status: {result.get('status')}")
    print(f"Fallback reason: {result.get('fallback_reason')}")
    print(f"Best distance: {result.get('best_distance')}")
    print(f"Retrieved chunks: {result.get('retrieved_chunks')}")

    print("\n" + "=" * 100)
    print("SOURCES")
    print("=" * 100)

    sources = result.get("sources", [])

    if not sources:
        print("No sources.")
        return

    for i, source in enumerate(sources, start=1):
        print(f"{i}. {source.get('file_name')}")
        print(f"   Course: {source.get('course')}")
        print(f"   Category: {source.get('category')}")
        print(f"   Path: {source.get('source_path')}")
        print(f"   Page: {source.get('page_start')} - {source.get('page_end')}")
        print(f"   Distance: {source.get('distance')}")
        print(f"   Chunk ID: {source.get('chunk_id')}")


def save_result(out_file: Optional[Path], result: Dict[str, Any]) -> None:
    if not out_file:
        return

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nSaved result: {out_file}")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Stage 5: RAG answer generation using ChromaDB retrieval + Groq API."
    )

    parser.add_argument(
        "--query",
        required=True,
        help="Student question.",
    )

    parser.add_argument(
        "--course",
        default=None,
        help="Course filter, e.g. CSE220_Data_Structure.",
    )

    parser.add_argument(
        "--category",
        default=None,
        help="Optional category filter, e.g. Notes, LabProblem, PracticeSheets.",
    )

    parser.add_argument(
        "--chroma-dir",
        default=os.getenv("CHROMA_DIR", "vector_store/chroma"),
        help="Persistent ChromaDB directory.",
    )

    parser.add_argument(
        "--collection-name",
        default="course_knowledge",
        help="ChromaDB collection name.",
    )

    parser.add_argument(
        "--embedding-model",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Same embedding model used in Stage 3.",
    )

    parser.add_argument(
        "--groq-model",
        default=None,
        help="Groq model name. Defaults to GROQ_MODEL from .env or llama-3.3-70b-versatile.",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to retrieve.",
    )

    parser.add_argument(
        "--distance-threshold",
        type=float,
        default=1.15,
        help=(
            "Fallback threshold. Lower distance is better. "
            "If best distance is above this value, fallback is returned."
        ),
    )

    parser.add_argument(
        "--min-context-chars",
        type=int,
        default=150,
        help="Minimum total retrieved context characters required to answer.",
    )

    parser.add_argument(
        "--max-context-chars",
        type=int,
        default=8000,
        help="Maximum context characters sent to Groq.",
    )

    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=700,
        help="Maximum output tokens from Groq.",
    )

    parser.add_argument(
        "--temperature",
        type=float,
        default=0.1,
        help="Lower is more factual/deterministic.",
    )

    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Test retrieval and fallback only. Do not call Groq.",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON result instead of human-readable output.",
    )

    parser.add_argument(
        "--out-file",
        default=None,
        help="Optional path to save result JSON.",
    )

    args = parser.parse_args()

    groq_model_name = get_groq_model(args.groq_model)

    result = answer_question(
        question=args.query,
        course=args.course,
        category=args.category,
        chroma_dir=Path(args.chroma_dir),
        collection_name=args.collection_name,
        embedding_model_name=args.embedding_model,
        groq_model_name=groq_model_name,
        top_k=args.top_k,
        distance_threshold=args.distance_threshold,
        min_context_chars=args.min_context_chars,
        max_context_chars=args.max_context_chars,
        max_output_tokens=args.max_output_tokens,
        temperature=args.temperature,
        no_llm=args.no_llm,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_human_readable(result)

    if args.out_file:
        save_result(Path(args.out_file), result)


if __name__ == "__main__":
    main()
