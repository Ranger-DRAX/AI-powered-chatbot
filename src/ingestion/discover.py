from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .settings import EXCLUDED_DIR_NAMES, SUPPORTED_EXTENSIONS
from .utils import file_modified_time


@dataclass(frozen=True)
class SourceFile:
    file_path: str
    relative_path: str
    file_name: str
    extension: str
    course: str
    category: str
    size_bytes: int
    modified_time_utc: str


def infer_course_and_category(raw_root: Path, file_path: Path) -> tuple[str, str]:
    relative_parts = file_path.relative_to(raw_root).parts

    course = relative_parts[0] if len(relative_parts) >= 1 else "unknown_course"
    category = relative_parts[1] if len(relative_parts) >= 2 else "root"

    return course, category


def discover_files(
    raw_root: Path,
    supported_extensions: set[str] | None = None,
    excluded_dir_names: set[str] | None = None,
    exclude_courses: set[str] | None = None,
    max_files: int | None = None,
) -> list[SourceFile]:
    raw_root = raw_root.resolve()

    if not raw_root.exists():
        raise FileNotFoundError(f"Raw directory not found: {raw_root}")

    supported_extensions = supported_extensions or SUPPORTED_EXTENSIONS
    excluded_dir_names = excluded_dir_names or EXCLUDED_DIR_NAMES
    exclude_courses = exclude_courses or set()

    discovered: list[SourceFile] = []

    for current_root, dirs, files in os.walk(raw_root):
        current_path = Path(current_root)

        # Skip excluded directories.
        dirs[:] = [d for d in dirs if d not in excluded_dir_names]

        # Skip excluded top-level course folders.
        if current_path == raw_root:
            dirs[:] = [d for d in dirs if d not in exclude_courses]

        for file_name in files:
            path = current_path / file_name
            extension = path.suffix.lower()

            if extension not in supported_extensions:
                continue

            try:
                course, category = infer_course_and_category(raw_root, path)
                stat = path.stat()

                discovered.append(
                    SourceFile(
                        file_path=str(path),
                        relative_path=str(path.relative_to(raw_root)),
                        file_name=path.name,
                        extension=extension,
                        course=course,
                        category=category,
                        size_bytes=stat.st_size,
                        modified_time_utc=file_modified_time(path),
                    )
                )

                if max_files is not None and len(discovered) >= max_files:
                    return discovered

            except OSError:
                continue

    return discovered


def source_file_to_dict(source_file: SourceFile) -> dict:
    return asdict(source_file)