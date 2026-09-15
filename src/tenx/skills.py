"""Skill management: bundled markdown skills, one per artifact type + process."""

from __future__ import annotations

from pathlib import Path

from .templates import SKILLS
from .locking import atomic_write_text


def list_skills() -> list[str]:
    return sorted(SKILLS)


def install_skills(target_dir: Path) -> list[Path]:
    """Write each skill as <target>/<name>/SKILL.md (Claude Code layout)."""
    written: list[Path] = []
    for name, body in sorted(SKILLS.items()):
        d = target_dir / name
        d.mkdir(parents=True, exist_ok=True)
        p = d / "SKILL.md"
        atomic_write_text(p, body.lstrip())
        written.append(p)
    return written
