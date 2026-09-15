"""Project root and harness discovery.

Two deployment layouts, both first-class:

1. Co-located (default): the harness lives at <project>/.tenx/ inside the
   code repo. One clone, atomic commits of code + context.

2. Standalone PM repo (the 10X layout): a dedicated git repo holds .tenx/
   and governs one or more code repos. Wiring:
   - the harness config names the code repo via `code_root:`
   - the code repo carries a `.tenxlink` pointer file back to the PM repo
   Hooks and AGENTS.md blocks install into the CODE repo, artifacts live
   in the PM repo.

Discovery priority: TENX_ROOT env > .tenx/ walking up > .tenxlink walking
up > .git walking up > cwd.
"""

from __future__ import annotations

import os
from pathlib import Path

HARNESS_DIR = ".tenx"
CONFIG_FILE = "config.yaml"
TENXLINK = ".tenxlink"


def _read_link(link_file: Path) -> Path | None:
    try:
        target = link_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not target or target.startswith("#"):
        return None
    p = Path(target).expanduser()
    if not p.is_absolute():
        p = (link_file.parent / p)
    p = p.resolve()
    return p if (p / HARNESS_DIR / CONFIG_FILE).is_file() else None


def find_project_root(start: Path | None = None) -> Path | None:
    """Locate the directory containing .tenx/ (the harness host dir)."""
    cur = (start or Path.cwd()).resolve()
    chain = [cur, *cur.parents]
    for cand in chain:
        if (cand / HARNESS_DIR / CONFIG_FILE).is_file() or (cand / HARNESS_DIR).is_dir():
            return cand
    for cand in chain:
        link = cand / TENXLINK
        if link.is_file():
            target = _read_link(link)
            if target is not None:
                return target
    for cand in chain:
        if (cand / ".git").exists():
            return cand
    return cur if cur.exists() else None


def harness_root(project_root: Path) -> Path:
    return project_root / HARNESS_DIR


def is_initialized(project_root: Path) -> bool:
    return (harness_root(project_root) / CONFIG_FILE).is_file()


def _load_config(project_root: Path) -> dict:
    from .yamlite import yamlite_load

    cfg_path = harness_root(project_root) / CONFIG_FILE
    if not cfg_path.is_file():
        return {}
    try:
        return yamlite_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def code_root(project_root: Path, config: dict | None = None) -> Path:
    """Where hooks/AGENTS.md land: config `code_root` or the harness host.

    For co-located harnesses this is the project root itself. For standalone
    PM repos it points at the governed code repo.
    """
    cfg = _load_config(project_root) if config is None else (config or {})
    cr = cfg.get("code_root")
    if not cr:
        return project_root
    p = Path(str(cr)).expanduser()
    if not p.is_absolute():
        p = (project_root / p)
    p = p.resolve()
    return p if p.is_dir() else project_root


def env_project_root() -> Path | None:
    """Explicit override: TENX_ROOT env var wins over discovery."""
    val = os.environ.get("TENX_ROOT")
    if val:
        p = Path(val).expanduser().resolve()
        if p.is_dir():
            return p
    return None
