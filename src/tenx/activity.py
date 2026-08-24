"""Append-only activity log (JSONL). Agents write back here after work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifacts import now_iso
from .discovery import harness_root

LOG_RELPATH = Path("log") / "activity.jsonl"
TYPES = ("note", "progress", "decision", "blocker", "review", "session")


def log_path(project_root: Path) -> Path:
    return harness_root(project_root) / LOG_RELPATH


def append_entry(
    project_root: Path,
    message: str,
    entry_type: str = "note",
    ref: str | None = None,
    actor: str = "agent",
) -> dict[str, Any]:
    if entry_type not in TYPES:
        raise ValueError(f"type must be one of {TYPES}")
    entry = {
        "ts": now_iso(),
        "type": entry_type,
        "actor": actor,
        "message": message,
    }
    if ref:
        entry["ref"] = ref.upper()
    p = log_path(project_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_entries(project_root: Path, limit: int | None = None) -> list[dict[str, Any]]:
    p = log_path(project_root)
    if not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if limit is not None:
        out = out[-limit:]
    return out


def log_session(project_root: Path, throttle_minutes: int = 60,
                actor: str = "agent") -> bool:
    """Append a `session` entry unless one was written within the throttle.

    Returns True if an entry was appended, False if throttled. Keeps
    SessionStart noise out of the history while preserving an audit
    trail of when agents booted with context.
    """
    from datetime import datetime, timedelta

    entries = read_entries(project_root)
    if entries and throttle_minutes > 0:
        last_session = next((e for e in reversed(entries)
                             if e.get("type") == "session"), None)
        if last_session:
            try:
                ts = datetime.fromisoformat(str(last_session.get("ts", "")))
            except ValueError:
                ts = None
            if ts is not None:
                now = datetime.fromisoformat(now_iso())
                if now - ts < timedelta(minutes=throttle_minutes):
                    return False
    append_entry(project_root, "session-start context packet emitted",
                 entry_type="session", actor=actor)
    return True
