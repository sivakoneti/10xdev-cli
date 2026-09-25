"""Persistent state for dispatched subagent lifecycle resources."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def dispatch_dir(project_root: Path) -> Path:
    return project_root / ".tenx" / "dispatch"


def receipt_path(project_root: Path, ticket_id: str) -> Path:
    return dispatch_dir(project_root) / ticket_id / "receipt.json"


def brief_path(project_root: Path, ticket_id: str) -> Path:
    return dispatch_dir(project_root) / ticket_id / "TICKET_BRIEF.md"


def write_receipt(project_root: Path, ticket_id: str, receipt: dict[str, Any]) -> Path:
    path = receipt_path(project_root, ticket_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def read_receipt(project_root: Path, ticket_id: str) -> dict[str, Any]:
    path = receipt_path(project_root, ticket_id)
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def clear_receipt(project_root: Path, ticket_id: str) -> None:
    path = receipt_path(project_root, ticket_id)
    if not path.exists():
        return
    for child in sorted(path.parent.iterdir(), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    path.parent.rmdir()
