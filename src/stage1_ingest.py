from __future__ import annotations

import argparse
from pathlib import Path

from tqdm import tqdm

from .ingestion.discover import discover_files, source_file_to_dict
from .ingestion.llamaindex_loader import parse_file_with_llamaindex_unstructured_reader
from .ingestion.settings import DEFAULT_OUT_DIR, DEFAULT_RAW_DIR
from .ingestion.unstructured_loader import parse_file_with_unstructured
from .ingestion.utils import append_jsonl_line, utc_now, write_json, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 1 file ingestion using Unstructured.io and LlamaIndex readers."
    )

    parser.add_argument(
        "--raw-dir",
        type=str,
        default=str(DEFAULT_RAW_DIR),
        help="Path to the raw course directory.",
    )

    parser.add_argument(
        "--out-dir",
        type=str,
        default=str(DEFAULT_OUT_DIR),
        help="Output directory for Stage 1 JSONL files.",
    )

    parser.add_argument(
        "--mode",
        choices=["unstructured", "llamaindex", "both"],
        default="both",
        help="Which ingestion reader to run.",
    )

    parser.add_argument(
        "--strategy",
        choices=["auto", "fast", "hi_res", "ocr_only"],
        default="fast",
        help="Unstructured parsing strategy.",
    )

    parser.add_argument(
        "--exclude-course",
        action="append",
        default=[],
        help="Course folder name to exclude. Can be used multiple times.",
    )

    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Limit number of files for testing.",
    )

    parser.add_argument(
        "--extract-pdf-images",
        action="store_true",
        help="Extract image/table blocks from PDFs into each course images folder. Uses hi_res.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    raw_dir = Path(args.raw_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[Stage 1] Raw directory: {raw_dir}")
    print(f"[Stage 1] Output directory: {out_dir}")
    print(f"[Stage 1] Mode: {args.mode}")
    print(f"[Stage 1] Strategy: {args.strategy}")

    source_files = discover_files(
        raw_root=raw_dir,
        exclude_courses=set(args.exclude_course),
        max_files=args.max_files,
    )

    manifest_path = out_dir / "manifest.jsonl"
    write_jsonl(manifest_path, [source_file_to_dict(f) for f in source_files])

    print(f"[Stage 1] Discovered files: {len(source_files)}")
    print(f"[Stage 1] Manifest saved: {manifest_path}")

    errors_path = out_dir / "errors.jsonl"

    unstructured_count = 0
    llamaindex_count = 0
    error_count = 0

    if errors_path.exists():
        errors_path.unlink()

    if args.mode in {"unstructured", "both"}:
        unstructured_output_path = out_dir / "unstructured_elements.jsonl"

        with unstructured_output_path.open("w", encoding="utf-8") as out_f, errors_path.open(
            "a", encoding="utf-8"
        ) as err_f:
            for source_file in tqdm(source_files, desc="Unstructured ingestion"):
                print(f"\nProcessing: {source_file.file_name}")
                rows, error = parse_file_with_unstructured(
                    source_file=source_file,
                    strategy=args.strategy,
                    extract_pdf_images=args.extract_pdf_images,
                )

                for row in rows:
                    append_jsonl_line(out_f, row)
                    unstructured_count += 1

                if error is not None:
                    append_jsonl_line(err_f, error)
                    error_count += 1

        print(f"[Stage 1] Unstructured output saved: {unstructured_output_path}")

    if args.mode in {"llamaindex", "both"}:
        llamaindex_output_path = out_dir / "llamaindex_documents.jsonl"

        with llamaindex_output_path.open("w", encoding="utf-8") as out_f, errors_path.open(
            "a", encoding="utf-8"
        ) as err_f:
            for source_file in tqdm(source_files, desc="LlamaIndex ingestion"):
                rows, error = parse_file_with_llamaindex_unstructured_reader(
                    source_file=source_file,
                    strategy=args.strategy,
                    split_documents=True,
                )

                for row in rows:
                    append_jsonl_line(out_f, row)
                    llamaindex_count += 1

                if error is not None:
                    append_jsonl_line(err_f, error)
                    error_count += 1

        print(f"[Stage 1] LlamaIndex output saved: {llamaindex_output_path}")

    summary = {
        "stage": "stage_1_file_ingestion",
        "created_at_utc": utc_now(),
        "raw_dir": str(raw_dir),
        "out_dir": str(out_dir),
        "mode": args.mode,
        "strategy": args.strategy,
        "excluded_courses": args.exclude_course,
        "files_discovered": len(source_files),
        "unstructured_elements": unstructured_count,
        "llamaindex_documents": llamaindex_count,
        "errors": error_count,
        "outputs": {
            "manifest": str(manifest_path),
            "unstructured_elements": str(out_dir / "unstructured_elements.jsonl"),
            "llamaindex_documents": str(out_dir / "llamaindex_documents.jsonl"),
            "errors": str(errors_path),
            "summary": str(out_dir / "summary.json"),
        },
    }

    summary_path = out_dir / "summary.json"
    write_json(summary_path, summary)

    print("[Stage 1] Done.")
    print(f"[Stage 1] Summary saved: {summary_path}")
    print(f"[Stage 1] Errors: {error_count}")


if __name__ == "__main__":
    main()