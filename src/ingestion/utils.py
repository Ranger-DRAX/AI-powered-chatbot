from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(*parts: Any) -> str:
    raw = "||".join(str(part) for part in parts)
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def safe_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): safe_jsonable(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [safe_jsonable(v) for v in value]

    if hasattr(value, "to_dict"):
        try:
            return safe_jsonable(value.to_dict())
        except Exception:
            pass

    if hasattr(value, "model_dump"):
        try:
            return safe_jsonable(value.model_dump())
        except Exception:
            pass

    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe_jsonable(data), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(safe_jsonable(row), ensure_ascii=False) + "\n")
            count += 1

    return count


def append_jsonl_line(handle, row: dict[str, Any]) -> None:
    handle.write(json.dumps(safe_jsonable(row), ensure_ascii=False) + "\n")


def file_modified_time(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()