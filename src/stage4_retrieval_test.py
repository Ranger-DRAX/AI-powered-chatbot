import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


def print_result(result: Dict[str, Any]) -> None:
    ids = result.get("ids", [[]])[0]
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    if not ids:
        print("No results found.")
        return

    for i, chunk_id in enumerate(ids, start=1):
        metadata = metadatas[i - 1] if i - 1 < len(metadatas) else {}
        document = documents[i - 1] if i - 1 < len(documents) else ""
        distance = distances[i - 1] if i - 1 < len(distances) else None

        print("=" * 100)
        print(f"Rank: {i}")
        print(f"Chunk ID: {chunk_id}")
        print(f"Distance: {distance}")
        print(f"Course: {metadata.get('course')}")
        print(f"Category: {metadata.get('category')}")
        print(f"File: {metadata.get('file_name')}")
        print(f"Source: {metadata.get('source_path')}")
        print("-" * 100)
        print(document[:1000])


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 4: Test retrieval from ChromaDB.")

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
        help="Same embedding model used in Stage 3.",
    )

    parser.add_argument(
        "--query",
        required=True,
        help="User question/query.",
    )

    parser.add_argument(
        "--course",
        default=None,
        help="Optional course filter, e.g. CSE220_Data_Structure.",
    )

    parser.add_argument(
        "--category",
        default=None,
        help="Optional category filter, e.g. Notes, LabProblem, PracticeSheets.",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of retrieved chunks.",
    )

    args = parser.parse_args()

    chroma_dir = Path(args.chroma_dir)

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False),
    )

    collection = client.get_collection(args.collection_name)

    print(f"Collection count: {collection.count()}")

    model = SentenceTransformer(args.model_name, device="cpu")

    query_embedding = model.encode(
        [args.query],
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0].tolist()

    where = {}

    if args.course:
        where["course"] = args.course

    if args.category:
        where["category"] = args.category

    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": args.top_k,
        "include": ["documents", "metadatas", "distances"],
    }

    if where:
        query_kwargs["where"] = where

    result = collection.query(**query_kwargs)

    print_result(result)


if __name__ == "__main__":
    main()