from __future__ import annotations

import traceback
from typing import Any

# pyrefly: ignore [missing-import]
from llama_index.readers.file import UnstructuredReader

from .discover import SourceFile
from .utils import safe_jsonable, stable_id, utc_now


def _document_text(doc: Any) -> str:
    if hasattr(doc, "get_content"):
        return doc.get_content().strip()

    if hasattr(doc, "text"):
        return str(doc.text).strip()

    return str(doc).strip()


def _document_id(doc: Any, source_file: SourceFile, index: int, text: str) -> str:
    doc_id = getattr(doc, "doc_id", None) or getattr(doc, "id_", None)

    if doc_id:
        return str(doc_id)

    return stable_id("llamaindex", source_file.relative_path, index, text[:300])


def parse_file_with_llamaindex_unstructured_reader(
    source_file: SourceFile,
    strategy: str = "auto",
    split_documents: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    try:
        loader = UnstructuredReader()

        docs = loader.load_data(
            unstructured_kwargs={
                "filename": source_file.file_path,
                "strategy": strategy,
            },
            split_documents=split_documents,
        )

        rows: list[dict[str, Any]] = []

        for index, doc in enumerate(docs):
            text = _document_text(doc)

            if not text:
                continue

            original_metadata = getattr(doc, "metadata", {}) or {}

            row = {
                "id": _document_id(doc, source_file, index, text),
                "source_reader": "llama_index.readers.file.UnstructuredReader",
                "text": text,
                "text_length": len(text),
                "document_index": index,
                "created_at_utc": utc_now(),
                "metadata": {
                    "file_path": source_file.file_path,
                    "relative_path": source_file.relative_path,
                    "file_name": source_file.file_name,
                    "extension": source_file.extension,
                    "course": source_file.course,
                    "category": source_file.category,
                    "size_bytes": source_file.size_bytes,
                    "modified_time_utc": source_file.modified_time_utc,
                    "llamaindex_metadata": safe_jsonable(original_metadata),
                },
            }

            rows.append(row)

        return rows, None

    except Exception as exc:
        error = {
            "reader": "llamaindex_unstructured_reader",
            "file_path": source_file.file_path,
            "relative_path": source_file.relative_path,
            "course": source_file.course,
            "category": source_file.category,
            "error_type": exc.__class__.__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
            "created_at_utc": utc_now(),
        }

        return [], error