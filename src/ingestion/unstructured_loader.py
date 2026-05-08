from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from unstructured.partition.auto import partition

from .discover import SourceFile
from .utils import safe_jsonable, stable_id, utc_now


PLAIN_TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".rst",
    ".json",
    ".csv",
    ".tsv",
    ".xml",
    ".html",
    ".htm",
    ".org",
}


def _element_metadata_to_dict(element: Any) -> dict[str, Any]:
    metadata = getattr(element, "metadata", None)

    if metadata is None:
        return {}

    if hasattr(metadata, "to_dict"):
        try:
            return safe_jsonable(metadata.to_dict())
        except Exception:
            return {}

    return safe_jsonable(metadata)


def _element_type(element: Any) -> str:
    return (
        getattr(element, "category", None)
        or element.__class__.__name__
        or "UnknownElement"
    )


def _read_text_file(path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin-1"]

    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding, errors="replace")
        except UnicodeDecodeError:
            continue

    return path.read_text(encoding="utf-8", errors="replace")


def _split_plain_text(text: str, max_chars: int = 4000) -> list[str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    if not text:
        return []

    blocks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()

        if not paragraph:
            continue

        if len(paragraph) > max_chars:
            if current:
                blocks.append("\n\n".join(current).strip())
                current = []
                current_len = 0

            for i in range(0, len(paragraph), max_chars):
                chunk = paragraph[i : i + max_chars].strip()
                if chunk:
                    blocks.append(chunk)

            continue

        if current_len + len(paragraph) > max_chars and current:
            blocks.append("\n\n".join(current).strip())
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len += len(paragraph)

    if current:
        blocks.append("\n\n".join(current).strip())

    return blocks


def _parse_plain_text_file(source_file: SourceFile) -> list[dict[str, Any]]:
    file_path = Path(source_file.file_path)
    text = _read_text_file(file_path)
    blocks = _split_plain_text(text)

    rows: list[dict[str, Any]] = []

    for index, block in enumerate(blocks):
        row = {
            "id": stable_id(
                "plain_text",
                source_file.relative_path,
                index,
                block[:300],
            ),
            "source_reader": "plain_text_direct_reader",
            "text": block,
            "text_length": len(block),
            "element_index": index,
            "element_type": "PlainTextBlock",
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
            },
        }

        rows.append(row)

    return rows


def build_unstructured_kwargs(
    source_file: SourceFile,
    strategy: str = "fast",
    extract_pdf_images: bool = False,
) -> dict[str, Any]:
    file_path = Path(source_file.file_path)

    kwargs: dict[str, Any] = {
        "filename": str(file_path),
        "strategy": strategy,
    }

    if extract_pdf_images and file_path.suffix.lower() == ".pdf":
        image_dir = file_path.parents[1] / "images" if len(file_path.parents) > 1 else file_path.parent / "images"
        image_dir.mkdir(parents=True, exist_ok=True)

        kwargs.update(
            {
                "strategy": "hi_res",
                "extract_image_block_types": ["Image", "Table"],
                "extract_image_block_to_payload": False,
                "extract_image_block_output_dir": str(image_dir),
            }
        )

    return kwargs


def parse_file_with_unstructured(
    source_file: SourceFile,
    strategy: str = "fast",
    extract_pdf_images: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    try:
        if source_file.extension.lower() in PLAIN_TEXT_EXTENSIONS:
            return _parse_plain_text_file(source_file), None

        kwargs = build_unstructured_kwargs(
            source_file=source_file,
            strategy=strategy,
            extract_pdf_images=extract_pdf_images,
        )

        elements = partition(**kwargs)

        rows: list[dict[str, Any]] = []

        for index, element in enumerate(elements):
            text = str(element).strip()

            if not text:
                continue

            element_metadata = _element_metadata_to_dict(element)

            row = {
                "id": stable_id(
                    "unstructured",
                    source_file.relative_path,
                    index,
                    text[:300],
                ),
                "source_reader": "unstructured.partition.auto.partition",
                "text": text,
                "text_length": len(text),
                "element_index": index,
                "element_type": _element_type(element),
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
                    "unstructured_metadata": element_metadata,
                },
            }

            rows.append(row)

        return rows, None

    except Exception as exc:
        error = {
            "reader": "unstructured",
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