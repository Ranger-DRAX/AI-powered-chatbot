import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from tqdm import tqdm


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                item = json.loads(line)
                item["_line_no"] = line_no
                yield item
            except Exception as exc:
                yield {
                    "_line_no": line_no,
                    "_json_error": True,
                    "error": str(exc),
                    "raw_preview": line[:500],
                }


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def flatten_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chroma metadata must be simple:
    str, int, float, bool.
    Lists/dicts are converted to JSON strings.
    None is converted to empty string.
    """
    clean = {}

    for key, value in metadata.items():
        if value is None:
            clean[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            clean[key] = value
        elif isinstance(value, (list, dict)):
            clean[key] = json.dumps(value, ensure_ascii=False)
        else:
            clean[key] = str(value)

    return clean


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = text.strip()
    return text


def load_chunks(
    chunks_file: Path,
    include_courses: List[str],
    exclude_courses: List[str],
    max_chunks: Optional[int],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    chunks = []
    errors = []

    include_set = set(include_courses)
    exclude_set = set(exclude_courses)

    for item in read_jsonl(chunks_file):
        if item.get("_json_error"):
            errors.append(
                {
                    "line_no": item.get("_line_no"),
                    "error_type": "JSONDecodeError",
                    "error_message": item.get("error"),
                    "raw_preview": item.get("raw_preview"),
                    "created_at_utc": utc_now(),
                }
            )
            continue

        chunk_id = item.get("chunk_id")
        text = clean_text(item.get("text", ""))
        metadata = item.get("metadata", {})

        if not chunk_id:
            errors.append(
                {
                    "line_no": item.get("_line_no"),
                    "error_type": "MissingChunkID",
                    "error_message": "chunk_id is missing.",
                    "created_at_utc": utc_now(),
                }
            )
            continue

        if not text:
            errors.append(
                {
                    "line_no": item.get("_line_no"),
                    "chunk_id": chunk_id,
                    "error_type": "EmptyText",
                    "error_message": "Chunk text is empty.",
                    "created_at_utc": utc_now(),
                }
            )
            continue

        if not isinstance(metadata, dict):
            metadata = {}

        course = metadata.get("course", "")

        if include_set and course not in include_set:
            continue

        if course in exclude_set:
            continue

        metadata = flatten_metadata(metadata)

        # Add useful fields if missing.
        metadata.setdefault("chunk_id", chunk_id)
        metadata.setdefault("document_id", item.get("document_id", ""))
        metadata.setdefault("text_length", len(text))

        chunks.append(
            {
                "chunk_id": chunk_id,
                "document_id": item.get("document_id", ""),
                "text": text,
                "metadata": metadata,
            }
        )

        if max_chunks is not None and len(chunks) >= max_chunks:
            break

    return chunks, errors


def batch_list(items: List[Any], batch_size: int) -> Iterable[List[Any]]:
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


def get_chroma_collection(
    chroma_dir: Path,
    collection_name: str,
    reset: bool,
):
    if reset and chroma_dir.exists():
        print(f"[Stage 3] Resetting Chroma directory: {chroma_dir}")
        shutil.rmtree(chroma_dir)

    chroma_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False),
    )

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={
            "description": "University course chatbot knowledge base",
            "created_by": "stage3_embed_store.py",
        },
    )

    return client, collection


def get_existing_ids(collection, ids: List[str]) -> set[str]:
    """
    Checks which IDs already exist in Chroma.
    Useful when rerunning without --reset.
    """
    existing = set()

    for batch_ids in batch_list(ids, 500):
        try:
            result = collection.get(ids=batch_ids, include=[])
            existing.update(result.get("ids", []))
        except Exception:
            # If collection is empty or Chroma behaves differently, ignore.
            pass

    return existing


def embed_and_store(
    chunks: List[Dict[str, Any]],
    model_name: str,
    chroma_dir: Path,
    collection_name: str,
    batch_size: int,
    reset: bool,
    device: str,
    skip_existing: bool,
) -> Dict[str, Any]:
    print(f"[Stage 3] Loading embedding model: {model_name}")
    print(f"[Stage 3] Device: {device}")

    model = SentenceTransformer(model_name, device=device)

    client, collection = get_chroma_collection(
        chroma_dir=chroma_dir,
        collection_name=collection_name,
        reset=reset,
    )

    ids = [chunk["chunk_id"] for chunk in chunks]

    existing_ids = set()
    if skip_existing and not reset:
        print("[Stage 3] Checking existing IDs in Chroma...")
        existing_ids = get_existing_ids(collection, ids)
        print(f"[Stage 3] Existing chunks found: {len(existing_ids)}")

    chunks_to_add = [chunk for chunk in chunks if chunk["chunk_id"] not in existing_ids]

    print(f"[Stage 3] Chunks loaded: {len(chunks)}")
    print(f"[Stage 3] Chunks to embed/store: {len(chunks_to_add)}")

    total_added = 0

    for batch in tqdm(
        list(batch_list(chunks_to_add, batch_size)),
        desc="Embedding + storing",
    ):
        batch_ids = [item["chunk_id"] for item in batch]
        batch_texts = [item["text"] for item in batch]
        batch_metadatas = [item["metadata"] for item in batch]

        embeddings = model.encode(
            batch_texts,
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )

        collection.add(
            ids=batch_ids,
            documents=batch_texts,
            metadatas=batch_metadatas,
            embeddings=embeddings.tolist(),
        )

        total_added += len(batch)

    final_count = collection.count()

    return {
        "chunks_loaded": len(chunks),
        "chunks_skipped_existing": len(existing_ids),
        "chunks_added": total_added,
        "collection_count": final_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 3: Generate embeddings and store chunks in ChromaDB."
    )

    parser.add_argument(
        "--chunks-file",
        default=r"K:\Certificat course\AI-powered chatbot\storage\stage2\chunks.jsonl",
        help="Path to Stage 2 chunks.jsonl",
    )

    parser.add_argument(
        "--chroma-dir",
        default=r"K:\Certificat course\AI-powered chatbot\vector_store\chroma",
        help="Persistent ChromaDB directory.",
    )

    parser.add_argument(
        "--collection-name",
        default="course_knowledge",
        help="ChromaDB collection name.",
    )

    parser.add_argument(
        "--model-name",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="SentenceTransformer embedding model name.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Embedding batch size. Use 16/32 for low RAM.",
    )

    parser.add_argument(
        "--device",
        default="cpu",
        choices=["cpu", "cuda"],
        help="Embedding device.",
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing ChromaDB directory before storing.",
    )

    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip chunks that already exist in ChromaDB.",
    )

    parser.add_argument(
        "--max-chunks",
        type=int,
        default=None,
        help="For testing: only embed first N chunks.",
    )

    parser.add_argument(
        "--course",
        action="append",
        default=[],
        help="Only embed selected course. Can be used multiple times.",
    )

    parser.add_argument(
        "--exclude-course",
        action="append",
        default=[],
        help="Exclude selected course. Can be used multiple times.",
    )

    parser.add_argument(
        "--out-dir",
        default=r"K:\Certificat course\AI-powered chatbot\storage\stage3",
        help="Output directory for Stage 3 summary/errors.",
    )

    args = parser.parse_args()

    chunks_file = Path(args.chunks_file)
    chroma_dir = Path(args.chroma_dir)
    out_dir = Path(args.out_dir)

    summary_file = out_dir / "summary.json"
    errors_file = out_dir / "errors.jsonl"

    if not chunks_file.exists():
        raise FileNotFoundError(f"Chunks file not found: {chunks_file}")

    print(f"[Stage 3] Chunks file: {chunks_file}")
    print(f"[Stage 3] Chroma directory: {chroma_dir}")
    print(f"[Stage 3] Collection: {args.collection_name}")
    print(f"[Stage 3] Batch size: {args.batch_size}")

    chunks, errors = load_chunks(
        chunks_file=chunks_file,
        include_courses=args.course,
        exclude_courses=args.exclude_course,
        max_chunks=args.max_chunks,
    )

    print(f"[Stage 3] Valid chunks loaded: {len(chunks)}")
    print(f"[Stage 3] Initial errors: {len(errors)}")

    result = embed_and_store(
        chunks=chunks,
        model_name=args.model_name,
        chroma_dir=chroma_dir,
        collection_name=args.collection_name,
        batch_size=args.batch_size,
        reset=args.reset,
        device=args.device,
        skip_existing=args.skip_existing,
    )

    write_jsonl(errors_file, errors)

    summary = {
        "stage": "stage_3_embedding_and_chromadb_storage",
        "created_at_utc": utc_now(),
        "chunks_file": str(chunks_file),
        "chroma_dir": str(chroma_dir),
        "collection_name": args.collection_name,
        "model_name": args.model_name,
        "batch_size": args.batch_size,
        "device": args.device,
        "reset": args.reset,
        "skip_existing": args.skip_existing,
        "courses_included": args.course,
        "courses_excluded": args.exclude_course,
        "max_chunks": args.max_chunks,
        "chunks_loaded": result["chunks_loaded"],
        "chunks_skipped_existing": result["chunks_skipped_existing"],
        "chunks_added": result["chunks_added"],
        "collection_count": result["collection_count"],
        "errors": len(errors),
        "outputs": {
            "summary": str(summary_file),
            "errors": str(errors_file),
            "chroma_dir": str(chroma_dir),
        },
    }

    write_json(summary_file, summary)

    print("[Stage 3] Done.")
    print(f"[Stage 3] Chunks added: {result['chunks_added']}")
    print(f"[Stage 3] Collection count: {result['collection_count']}")
    print(f"[Stage 3] Errors: {len(errors)}")
    print(f"[Stage 3] Summary saved: {summary_file}")


if __name__ == "__main__":
    main()