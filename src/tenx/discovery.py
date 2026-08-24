"""Project root and harness discovery."""

from __future__ import annotations

import os
from pathlib import Path

HARNESS_DIR = ".tenx"
CONFIG_FILE = "config.yaml"


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from start (default cwd) looking for .tenx/ or .git."""
    cur = (start or Path.cwd()).resolve()
    for cand in [cur, *cur.parents]:
        if (cand / HARNESS_DIR).is_dir():
            return cand
    # Fall back to git root so commands like `tenx init` know where to land.
    for cand in [cur, *cur.parents]:
        if (cand / ".git").exists():
            return cand
    return cur if cur.exists() else None


def harness_root(project_root: Path) -> Path:
    return project_root / HARNESS_DIR


def is_initialized(project_root: Path) -> bool:
    return (harness_root(project_root) / CONFIG_FILE).is_file()


def env_project_root() -> Path | None:
    """Explicit override: TENX_ROOT env var wins over discovery."""
    val = os.environ.get("TENX_ROOT")
    if val:
        p = Path(val).expanduser().resolve()
        if p.is_dir():
            return p
    return None
