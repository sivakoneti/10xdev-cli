"""Skill management: bundled markdown skills, one per artifact type + process."""

from __future__ import annotations

from pathlib import Path

from .templates import SKILLS


def list_skills() -> list[str]:
    return sorted(SKILLS)


def install_skills(target_dir: Path) -> list[Path]:
    """Write each skill as <target>/<name>/SKILL.md (Claude Code layout)."""
    written: list[Path] = []
    for name, body in sorted(SKILLS.items()):
        d = target_dir / name
        d.mkdir(parents=True, exist_ok=True)
        p = d / "SKILL.md"
        p.write_text(body.lstrip(), encoding="utf-8")
        written.append(p)
    return written
