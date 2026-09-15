"""tenx.changelog - Keep-a-Changelog discipline for the harness.

Documentation drifts because code changes have an enforced merge path while
doc updates are a separate manual step. This module folds the changelog update
into the path: `tenx changelog add` when you finish something, `tenx changelog
release` when you cut a version. The file follows Keep a Changelog 1.1:

  * an entry for every version, grouped by type
    (Added/Changed/Deprecated/Removed/Fixed/Security)
  * latest version first, each with its release date
  * an `[Unreleased]` section kept at the top and moved into a version at
    release time

Stdlib only (CON-002 zero runtime deps).
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

CHANGELOG_NAME = "CHANGELOG.md"

# Keep a Changelog change types, in canonical order.
TYPES: tuple[str, ...] = ("Added", "Changed", "Deprecated",
                          "Removed", "Fixed", "Security")

HEADER = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
"""

_SECTION_RE = re.compile(r"^##\s+\[(?P<label>[^\]]+)\](?:\s*-\s*(?P<date>.+))?\s*$")
_TYPE_RE = re.compile(r"^###\s+(?P<type>[A-Za-z]+)\s*$")
_ENTRY_RE = re.compile(r"^[-*]\s+(?P<text>.+?)\s*$")


@dataclass
class ChangelogSection:
    label: str                       # "Unreleased" or a version like "0.16.0"
    date: str | None = None
    entries: dict[str, list[str]] = field(default_factory=dict)

    @property
    def is_unreleased(self) -> bool:
        return self.label.strip().lower() == "unreleased"

    def count(self) -> int:
        return sum(len(v) for v in self.entries.values())


def changelog_path(project_root: Path) -> Path:
    return Path(project_root) / CHANGELOG_NAME


def parse_changelog(text: str) -> tuple[str, list[ChangelogSection]]:
    """Split text into (preamble, ordered sections). Tolerant of oddities."""
    preamble_lines: list[str] = []
    sections: list[ChangelogSection] = []
    cur: ChangelogSection | None = None
    cur_type: str | None = None
    for line in text.splitlines():
        m = _SECTION_RE.match(line)
        if m:
            cur = ChangelogSection(label=m.group("label").strip(),
                                   date=(m.group("date") or "").strip() or None)
            sections.append(cur)
            cur_type = None
            continue
        if cur is None:
            preamble_lines.append(line)
            continue
        mt = _TYPE_RE.match(line)
        if mt:
            typ = mt.group("type").strip()
            # normalize to canonical type when it matches (case-insensitive)
            for t in TYPES:
                if t.lower() == typ.lower():
                    typ = t
                    break
            cur_type = typ
            cur.entries.setdefault(typ, [])
            continue
        me = _ENTRY_RE.match(line)
        if me and cur_type:
            cur.entries.setdefault(cur_type, []).append(me.group("text"))
            continue
        # SPC-023-T13: round-trip preservation. Lines we do not model are
        # kept verbatim under the "" bucket instead of being dropped:
        #  * bullet entries appearing before any `### Type` heading
        #  * indented sub-bullets/continuations (attached to the last entry)
        #  * prose lines inside a section
        if line.startswith((" ", "\t")):
            bucket = cur.entries.get(cur_type or "") or []
            if bucket:
                bucket[-1] = bucket[-1] + "\n" + line
                cur.entries[cur_type or ""] = bucket
                continue
        if line.strip():
            cur.entries.setdefault("", []).append(line.rstrip())
    return "\n".join(preamble_lines).rstrip("\n"), sections


def render(preamble: str, sections: list[ChangelogSection]) -> str:
    out: list[str] = []
    if preamble.strip():
        out.append(preamble.rstrip("\n"))
        out.append("")
    for sec in sections:
        head = f"## [{sec.label}]"
        if sec.date:
            head += f" - {sec.date}"
        out.append(head)
        out.append("")
        # SPC-023-T13: verbatim lines first (heading-less entries, prose),
        # then types in canonical order, then any unknown types.
        raw = sec.entries.get("") or []
        if raw:
            out.extend(raw)
            out.append("")
        ordered = [t for t in TYPES if t in sec.entries]
        ordered += [t for t in sec.entries if t not in TYPES and t != ""]
        for t in ordered:
            msgs = sec.entries.get(t) or []
            if not msgs:
                continue
            out.append(f"### {t}")
            for m in msgs:
                # entries may carry indented sub-lines verbatim
                first, *rest = m.split("\n")
                out.append(f"- {first}")
                out.extend(rest)
            out.append("")
    text = "\n".join(out).rstrip("\n") + "\n"
    return text


def seed_changelog(project_root: Path) -> bool:
    """Create CHANGELOG.md if absent. Returns True when created."""
    p = changelog_path(project_root)
    if p.exists():
        return False
    p.write_text(HEADER, encoding="utf-8")
    return True


def _load(project_root: Path) -> tuple[str, list[ChangelogSection]]:
    p = changelog_path(project_root)
    if not p.exists():
        seed_changelog(project_root)
    return parse_changelog(p.read_text(encoding="utf-8"))


def _save(project_root: Path, preamble: str,
          sections: list[ChangelogSection]) -> None:
    from .locking import atomic_write_text
    atomic_write_text(changelog_path(project_root), render(preamble, sections))


def _ensure_unreleased(sections: list[ChangelogSection]) -> ChangelogSection:
    for s in sections:
        if s.is_unreleased:
            return s
    ur = ChangelogSection(label="Unreleased")
    sections.insert(0, ur)
    return ur


def add_entry(project_root: Path, message: str, type: str = "Added",
              ref: str | None = None) -> ChangelogSection:
    """Append one entry under [Unreleased]/<type>. Returns the section."""
    typ = type.strip().capitalize() if type else "Added"
    if typ.lower() not in [t.lower() for t in TYPES]:
        typ = "Added"
    else:
        for t in TYPES:
            if t.lower() == typ.lower():
                typ = t
                break
    text = message.strip()
    if ref:
        ref = ref.strip().upper()
        if not text.endswith(")") or ref not in text:
            text = f"{text} ({ref})"
    preamble, sections = _load(project_root)
    ur = _ensure_unreleased(sections)
    ur.entries.setdefault(typ, []).append(text)
    _save(project_root, preamble, sections)
    return ur


def release(project_root: Path, version: str) -> ChangelogSection:
    """Stamp [Unreleased] into [<version>] - <today>; open a fresh Unreleased.

    Returns the newly stamped section. Raises ValueError if there is no
    Unreleased section or it has no entries.
    """
    version = version.strip()
    if not version:
        raise ValueError("release version must not be empty")
    preamble, sections = _load(project_root)
    ur = next((s for s in sections if s.is_unreleased), None)
    if ur is None:
        raise ValueError("no [Unreleased] section to release")
    if ur.count() == 0:
        raise ValueError("[Unreleased] has no entries; add changes first "
                         "(tenx changelog add ...)")
    ur.label = version
    ur.date = dt.date.today().isoformat()
    # open a fresh Unreleased above it
    idx = sections.index(ur)
    sections.insert(idx, ChangelogSection(label="Unreleased"))
    _save(project_root, preamble, sections)
    return ur


def unreleased_entries(project_root: Path) -> int:
    p = changelog_path(project_root)
    if not p.exists():
        return 0
    _, sections = parse_changelog(p.read_text(encoding="utf-8"))
    for s in sections:
        if s.is_unreleased:
            return s.count()
    return 0


def latest_released_date(project_root: Path) -> str | None:
    """Return the date of the most recent released section, or None."""
    p = changelog_path(project_root)
    if not p.exists():
        return None
    _, sections = parse_changelog(p.read_text(encoding="utf-8"))
    for s in sections:
        if not s.is_unreleased and s.date:
            return s.date
    return None


def latest_released_version(project_root: Path) -> str | None:
    """Return the most recent released version label (no leading v), or None."""
    p = changelog_path(project_root)
    if not p.exists():
        return None
    _, sections = parse_changelog(p.read_text(encoding="utf-8"))
    for s in sections:
        if not s.is_unreleased:
            return s.label.lstrip("vV").strip()
    return None


def to_dict(project_root: Path) -> dict[str, Any]:
    p = changelog_path(project_root)
    if not p.exists():
        return {"exists": False, "unreleased": 0,
                "latest_version": None, "sections": []}
    _, sections = parse_changelog(p.read_text(encoding="utf-8"))
    return {
        "exists": True,
        "unreleased": unreleased_entries(project_root),
        "latest_version": latest_released_version(project_root),
        "sections": [
            {"label": s.label, "date": s.date, "entries": s.count(),
             "unreleased": s.is_unreleased}
            for s in sections
        ],
    }
