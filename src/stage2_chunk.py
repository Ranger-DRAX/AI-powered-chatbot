import argparse
import hashlib
import json
import re
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SUPPORTED_TEXT_KEYS = ["text", "content", "page_content"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: Path) -> Iterable[Tuple[int, Dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except Exception as exc:
                yield line_no, {
                    "__json_error__": True,
                    "error": str(exc),
                    "raw_line_preview": line[:500],
                }


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> int:
    count = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def safe_get_text(record: Dict[str, Any]) -> str:
    """
    Supports multiple possible shapes:
    1. {"text": "...", "metadata": {...}}
    2. {"element": {"text": "...", "metadata": {...}}}
    3. {"page_content": "...", "metadata": {...}}
    """
    if isinstance(record.get("element"), dict):
        element = record["element"]
        for key in SUPPORTED_TEXT_KEYS:
            value = element.get(key)
            if isinstance(value, str) and value.strip():
                return value

    for key in SUPPORTED_TEXT_KEYS:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value

    return ""


def get_element_obj(record: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(record.get("element"), dict):
        return record["element"]
    return record


def get_metadata(record: Dict[str, Any]) -> Dict[str, Any]:
    element = get_element_obj(record)

    metadata = {}

    if isinstance(element.get("metadata"), dict):
        metadata.update(element["metadata"])

    if isinstance(record.get("metadata"), dict):
        metadata.update(record["metadata"])

    # Keep important top-level metadata if your Stage 1 added them.
    for key in [
        "file_path",
        "relative_path",
        "course",
        "course_code",
        "course_title",
        "category",
        "file_name",
        "file_type",
        "source_path",
    ]:
        if key in record and record[key] is not None:
            metadata[key] = record[key]

    return metadata


def normalize_path(value: Optional[str]) -> str:
    if not value:
        return ""
    return str(value).replace("\\", "/")


def infer_file_name(metadata: Dict[str, Any]) -> str:
    for key in ["file_name", "filename"]:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return Path(value).name

    for key in ["relative_path", "source_path", "file_path"]:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return Path(value).name

    return "unknown_file"


def infer_source_path(metadata: Dict[str, Any]) -> str:
    for key in ["relative_path", "source_path"]:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_path(value)

    value = metadata.get("file_path")
    if isinstance(value, str) and value.strip():
        return normalize_path(value)

    filename = infer_file_name(metadata)
    return filename


def infer_file_type(file_name: str, metadata: Dict[str, Any]) -> str:
    suffix = Path(file_name).suffix.lower().replace(".", "")
    if suffix:
        return suffix

    value = metadata.get("file_type") or metadata.get("filetype")
    if isinstance(value, str) and value.strip():
        value = value.lower()
        if "/" in value:
            return value.split("/")[-1]
        return value

    return "unknown"


def infer_course(metadata: Dict[str, Any], source_path: str) -> str:
    for key in ["course", "course_code"]:
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    parts = source_path.split("/")
    if parts:
        return parts[0]

    return "unknown_course"


def infer_category(metadata: Dict[str, Any], source_path: str) -> str:
    value = metadata.get("category")
    if isinstance(value, str) and value.strip():
        return value.strip()

    parts = source_path.split("/")
    if len(parts) >= 2:
        return parts[1]

    return "unknown_category"


def infer_element_type(record: Dict[str, Any]) -> str:
    element = get_element_obj(record)

    for key in ["type", "category", "element_type"]:
        value = element.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    value = record.get("element_type")
    if isinstance(value, str) and value.strip():
        return value.strip()

    return "Unknown"


def infer_page_number(metadata: Dict[str, Any]) -> Optional[int]:
    for key in ["page_number", "page", "page_index"]:
        value = metadata.get(key)
        if value is None:
            continue

        try:
            return int(value)
        except Exception:
            continue

    return None


def clean_text(text: str, preserve_code_spacing: bool = False) -> str:
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    lines = text.split("\n")

    if preserve_code_spacing:
        cleaned_lines = [line.rstrip() for line in lines]
    else:
        cleaned_lines = [re.sub(r"[ \t]+", " ", line).strip() for line in lines]

    text = "\n".join(cleaned_lines)

    # Remove too many blank lines.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def slugify(value: str, max_len: int = 80) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value)
    value = value.strip("_")
    if not value:
        value = "unknown"
    return value[:max_len]


def sha1_short(value: str, length: int = 10) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def split_long_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    """
    Splits a single very large text element into overlapping chunks.
    Tries to split on paragraph/sentence boundaries before hard-cutting.
    """
    text = text.strip()
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        window = text[start:end]

        if end < len(text):
            # Prefer paragraph break.
            cut = window.rfind("\n\n")
            if cut < int(chunk_size * 0.5):
                # Prefer sentence end.
                cut = max(window.rfind(". "), window.rfind("? "), window.rfind("! "))
            if cut >= int(chunk_size * 0.5):
                end = start + cut + 1
                window = text[start:end]

        window = window.strip()
        if window:
            chunks.append(window)

        if end >= len(text):
            break

        start = max(0, end - chunk_overlap)

    return chunks


def build_overlap_text(text: str, chunk_overlap: int) -> str:
    if chunk_overlap <= 0:
        return ""

    text = text.strip()
    if len(text) <= chunk_overlap:
        return text

    tail = text[-chunk_overlap:]

    # Avoid starting overlap in the middle of a word too badly.
    first_space = tail.find(" ")
    if first_space != -1 and first_space < len(tail) // 3:
        tail = tail[first_space + 1:]

    return tail.strip()


def create_document_id(course: str, category: str, source_path: str) -> str:
    file_stem = Path(source_path).stem
    path_hash = sha1_short(source_path, 10)
    return f"{slugify(course)}__{slugify(category)}__{slugify(file_stem)}__{path_hash}"


def make_chunk_id(document_id: str, chunk_index: int, text: str) -> str:
    text_hash = sha1_short(text, 8)
    return f"{document_id}__chunk_{chunk_index:05d}__{text_hash}"


def normalize_element_record(line_no: int, record: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    if record.get("__json_error__"):
        return None, {
            "line_no": line_no,
            "error_type": "JSONDecodeError",
            "error_message": record.get("error", "Invalid JSON"),
            "raw_line_preview": record.get("raw_line_preview", ""),
            "created_at_utc": utc_now(),
        }

    metadata = get_metadata(record)
    raw_text = safe_get_text(record)

    source_path = infer_source_path(metadata)
    file_name = infer_file_name(metadata)
    file_type = infer_file_type(file_name, metadata)
    course = infer_course(metadata, source_path)
    category = infer_category(metadata, source_path)
    element_type = infer_element_type(record)
    page_number = infer_page_number(metadata)

    preserve_code_spacing = file_type in {"py", "java", "js", "ts", "cpp", "c", "asm", "ipynb", "sql"}
    text = clean_text(raw_text, preserve_code_spacing=preserve_code_spacing)

    if not text:
        return None, None

    item = {
        "line_no": line_no,
        "text": text,
        "element_type": element_type,
        "page_number": page_number,
        "metadata": {
            "course": course,
            "category": category,
            "source_path": source_path,
            "file_name": file_name,
            "file_type": file_type,
            "page_number": page_number,
        },
    }

    # Keep selected useful fields from original metadata.
    for key in [
        "course_code",
        "course_title",
        "languages",
        "last_modified",
        "file_directory",
        "filename",
        "filetype",
        "url",
    ]:
        if key in metadata and metadata[key] is not None:
            item["metadata"][key] = metadata[key]

    return item, None


def should_start_new_section(element_type: str) -> bool:
    return element_type.lower() in {
        "title",
        "header",
        "sectionheader",
    }


def chunk_document(
    elements: List[Dict[str, Any]],
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_chars: int,
    metadata_prefix: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not elements:
        return [], {}

    first_meta = elements[0]["metadata"]
    course = first_meta.get("course", "unknown_course")
    category = first_meta.get("category", "unknown_category")
    source_path = first_meta.get("source_path", "unknown_source")
    file_name = first_meta.get("file_name", "unknown_file")
    file_type = first_meta.get("file_type", "unknown")

    document_id = create_document_id(course, category, source_path)

    chunks = []
    current_parts: List[str] = []
    current_pages: List[int] = []
    current_element_types: List[str] = []
    current_line_numbers: List[int] = []

    def current_text() -> str:
        return "\n\n".join(part for part in current_parts if part.strip()).strip()

    def flush(final: bool = False) -> None:
        nonlocal current_parts, current_pages, current_element_types, current_line_numbers

        text = current_text()

        if not text:
            current_parts = []
            current_pages = []
            current_element_types = []
            current_line_numbers = []
            return

        if len(text) < min_chunk_chars and not final and chunks:
            # Too small to be useful; keep accumulating unless final.
            return

        chunk_index = len(chunks) + 1

        page_numbers = [p for p in current_pages if isinstance(p, int)]
        page_start = min(page_numbers) if page_numbers else None
        page_end = max(page_numbers) if page_numbers else None

        final_text = text

        if metadata_prefix:
            prefix = (
                f"Course: {course}\n"
                f"Category: {category}\n"
                f"Source: {file_name}\n\n"
            )
            final_text = prefix + text

        chunk_id = make_chunk_id(document_id, chunk_index, final_text)

        chunk = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "text": final_text,
            "metadata": {
                "course": course,
                "category": category,
                "source_path": source_path,
                "file_name": file_name,
                "file_type": file_type,
                "chunk_index": chunk_index,
                "page_start": page_start,
                "page_end": page_end,
                "element_types": sorted(set(current_element_types)),
                "element_count": len(current_element_types),
                "source_line_start": min(current_line_numbers) if current_line_numbers else None,
                "source_line_end": max(current_line_numbers) if current_line_numbers else None,
                "char_count": len(final_text),
            },
        }

        chunks.append(chunk)

        overlap_text = build_overlap_text(text, chunk_overlap)

        if overlap_text and not final:
            current_parts = [overlap_text]
            current_pages = current_pages[-1:] if current_pages else []
            current_element_types = ["Overlap"]
            current_line_numbers = current_line_numbers[-1:] if current_line_numbers else []
        else:
            current_parts = []
            current_pages = []
            current_element_types = []
            current_line_numbers = []

    for element in elements:
        text = element["text"]
        element_type = element.get("element_type", "Unknown")
        page_number = element.get("page_number")
        line_no = element.get("line_no")

        # If one element itself is very large, split it first.
        long_parts = split_long_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        for part in long_parts:
            candidate_text = (current_text() + "\n\n" + part).strip() if current_parts else part.strip()

            # Start a new chunk before a heading if current chunk is already meaningful.
            if should_start_new_section(element_type) and len(current_text()) >= min_chunk_chars:
                flush(final=False)

            if len(candidate_text) > chunk_size and len(current_text()) >= min_chunk_chars:
                flush(final=False)

            current_parts.append(part)
            if isinstance(page_number, int):
                current_pages.append(page_number)
            current_element_types.append(element_type)
            if isinstance(line_no, int):
                current_line_numbers.append(line_no)

    flush(final=True)

    doc_report = {
        "document_id": document_id,
        "course": course,
        "category": category,
        "source_path": source_path,
        "file_name": file_name,
        "file_type": file_type,
        "elements": len(elements),
        "chunks": len(chunks),
        "created_at_utc": utc_now(),
    }

    return chunks, doc_report


def load_and_group_elements(
    input_file: Path,
    include_courses: List[str],
    exclude_courses: List[str],
) -> Tuple[OrderedDict, List[Dict[str, Any]], int]:
    grouped = OrderedDict()
    errors = []
    empty_text_records = 0

    include_set = set(include_courses)
    exclude_set = set(exclude_courses)

    for line_no, record in read_jsonl(input_file):
        item, error = normalize_element_record(line_no, record)

        if error:
            errors.append(error)
            continue

        if item is None:
            empty_text_records += 1
            continue

        course = item["metadata"].get("course", "unknown_course")

        if include_set and course not in include_set:
            continue

        if course in exclude_set:
            continue

        source_path = item["metadata"].get("source_path", "unknown_source")
        doc_key = source_path

        if doc_key not in grouped:
            grouped[doc_key] = []

        grouped[doc_key].append(item)

    return grouped, errors, empty_text_records


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2: Chunk unstructured elements into clean RAG chunks.")

    parser.add_argument(
        "--input-file",
        default=r"K:\Certificat course\AI-powered chatbot\storage\stage1\unstructured_elements.jsonl",
        help="Path to Stage 1 unstructured_elements.jsonl",
    )

    parser.add_argument(
        "--out-dir",
        default=r"K:\Certificat course\AI-powered chatbot\storage\stage2",
        help="Output directory for Stage 2 files",
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1200,
        help="Target maximum chunk size in characters.",
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=150,
        help="Character overlap between chunks.",
    )

    parser.add_argument(
        "--min-chunk-chars",
        type=int,
        default=120,
        help="Minimum useful chunk size.",
    )

    parser.add_argument(
        "--course",
        action="append",
        default=[],
        help="Only chunk selected course folder/course name. Can be used multiple times.",
    )

    parser.add_argument(
        "--exclude-course",
        action="append",
        default=[],
        help="Exclude selected course folder/course name. Can be used multiple times.",
    )

    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="For testing: only process first N documents.",
    )

    parser.add_argument(
        "--metadata-prefix",
        action="store_true",
        help="Add course/category/source text prefix inside every chunk text.",
    )

    args = parser.parse_args()

    input_file = Path(args.input_file)
    out_dir = Path(args.out_dir)

    chunks_file = out_dir / "chunks.jsonl"
    documents_report_file = out_dir / "documents_report.jsonl"
    errors_file = out_dir / "errors.jsonl"
    summary_file = out_dir / "summary.json"

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    print(f"[Stage 2] Input file: {input_file}")
    print(f"[Stage 2] Output directory: {out_dir}")
    print(f"[Stage 2] Chunk size: {args.chunk_size}")
    print(f"[Stage 2] Chunk overlap: {args.chunk_overlap}")

    grouped, errors, empty_text_records = load_and_group_elements(
        input_file=input_file,
        include_courses=args.course,
        exclude_courses=args.exclude_course,
    )

    doc_items = list(grouped.items())

    if args.max_docs is not None:
        doc_items = doc_items[: args.max_docs]

    print(f"[Stage 2] Documents discovered: {len(grouped)}")
    print(f"[Stage 2] Documents selected: {len(doc_items)}")
    print(f"[Stage 2] Empty text records skipped: {empty_text_records}")

    all_chunks: List[Dict[str, Any]] = []
    doc_reports: List[Dict[str, Any]] = []

    for doc_index, (doc_key, elements) in enumerate(doc_items, start=1):
        try:
            chunks, report = chunk_document(
                elements=elements,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                min_chunk_chars=args.min_chunk_chars,
                metadata_prefix=args.metadata_prefix,
            )

            all_chunks.extend(chunks)
            doc_reports.append(report)

            print(
                f"[Stage 2] {doc_index}/{len(doc_items)} | "
                f"{report.get('source_path')} | "
                f"elements={report.get('elements')} | chunks={report.get('chunks')}"
            )

        except Exception as exc:
            errors.append({
                "document_key": doc_key,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "created_at_utc": utc_now(),
            })

    out_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(chunks_file, all_chunks)
    write_jsonl(documents_report_file, doc_reports)
    write_jsonl(errors_file, errors)

    summary = {
        "stage": "stage_2_chunking",
        "created_at_utc": utc_now(),
        "input_file": str(input_file),
        "out_dir": str(out_dir),
        "chunk_size": args.chunk_size,
        "chunk_overlap": args.chunk_overlap,
        "min_chunk_chars": args.min_chunk_chars,
        "metadata_prefix": args.metadata_prefix,
        "courses_included": args.course,
        "courses_excluded": args.exclude_course,
        "documents_discovered": len(grouped),
        "documents_selected": len(doc_items),
        "chunks_created": len(all_chunks),
        "empty_text_records_skipped": empty_text_records,
        "errors": len(errors),
        "outputs": {
            "chunks": str(chunks_file),
            "documents_report": str(documents_report_file),
            "errors": str(errors_file),
            "summary": str(summary_file),
        },
    }

    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print("[Stage 2] Done.")
    print(f"[Stage 2] Chunks saved: {chunks_file}")
    print(f"[Stage 2] Documents report saved: {documents_report_file}")
    print(f"[Stage 2] Errors: {len(errors)}")
    print(f"[Stage 2] Summary saved: {summary_file}")


if __name__ == "__main__":
    main()