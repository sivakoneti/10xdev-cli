"""Artifact model: structured markdown documents with parseable frontmatter.

Artifact types and ID prefixes (mirrors the 10X meta-harness pattern):

- epic       EPC-001   what we are building + milestones to get there
- spec       SPC-001   detailed technical plan, ticket by ticket
- convention CON-001   coding/process rules that keep agents on rails
- doc        DOC-001   architecture, decisions, external systems, anything
                       else an agent might need
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from .discovery import harness_root
from .yamlite import dump_frontmatter, load_frontmatter, split_frontmatter

TYPE_PREFIX = {
    "epic": "EPC",
    "spec": "SPC",
    "convention": "CON",
    "doc": "DOC",
}
PREFIX_TYPE = {v: k for k, v in TYPE_PREFIX.items()}
TYPE_DIRS = {
    "epic": "epics",
    "spec": "specs",
    "convention": "conventions",
    "doc": "docs",
}

STATUSES = ["draft", "in_progress", "in_review", "complete", "blocked", "archived"]
TICKET_STATUSES = ["todo", "in_progress", "in_review", "done"]

REQUIRED_FIELDS: dict[str, list[str]] = {
    "epic": ["id", "type", "title", "status", "created", "updated"],
    "spec": ["id", "type", "title", "status", "epic", "created", "updated"],
    "convention": ["id", "type", "title", "status", "created", "updated"],
    "doc": ["id", "type", "title", "created", "updated"],
}

ID_RE = re.compile(r"^(EPC|SPC|CON|DOC)-(\d{3})$")
# Non-anchored variant for finding ids inside running text (e.g. INDEX.md).
ID_FIND_RE = re.compile(r"\b(EPC|SPC|CON|DOC)-(\d{3})\b")


def today() -> str:
    return dt.date.today().isoformat()


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def slugify(title: str, maxlen: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:maxlen].rstrip("-") or "untitled"


@dataclass
class Artifact:
    path: Path
    meta: dict[str, Any]
    body: str
    parse_error: str | None = None

    @property
    def id(self) -> str:
        return str(self.meta.get("id", ""))

    @property
    def type(self) -> str:
        return str(self.meta.get("type", ""))

    @property
    def title(self) -> str:
        return str(self.meta.get("title", ""))

    @property
    def status(self) -> str:
        return str(self.meta.get("status", ""))

    @property
    def tickets(self) -> list[dict[str, Any]]:
        val = self.meta.get("tickets") or []
        return [t for t in val if isinstance(t, dict)]

    def rel(self, project_root: Path) -> str:
        try:
            return str(self.path.relative_to(project_root))
        except ValueError:
            return str(self.path)

    def render(self) -> str:
        return f"---\n{dump_frontmatter(self.meta)}\n---\n\n{self.body.lstrip()}"


@dataclass
class Harness:
    project_root: Path
    artifacts: list[Artifact] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    @property
    def root(self) -> Path:
        return harness_root(self.project_root)

    def by_type(self, atype: str) -> list[Artifact]:
        return sorted(
            (a for a in self.artifacts if a.type == atype),
            key=lambda a: a.id,
        )

    def get(self, artifact_id: str) -> Artifact | None:
        wanted = artifact_id.strip().upper()
        for a in self.artifacts:
            if a.id.upper() == wanted:
                return a
        return None

    def specs_for_epic(self, epic_id: str) -> list[Artifact]:
        return [s for s in self.by_type("spec") if str(s.meta.get("epic", "")).upper() == epic_id.upper()]


def load_artifact(path: Path) -> Artifact:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body, err = load_frontmatter(text)
    if meta is None:
        return Artifact(path=path, meta={}, body=body, parse_error=err)
    return Artifact(path=path, meta=meta, body=body, parse_error=None)


def load_harness(project_root: Path) -> Harness:
    from .yamlite import yamlite_load

    root = harness_root(project_root)
    harness = Harness(project_root=project_root)
    cfg_path = root / "config.yaml"
    if cfg_path.is_file():
        try:
            harness.config = yamlite_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            harness.config = {}
    if not root.is_dir():
        return harness
    for subdir in TYPE_DIRS.values():
        d = root / subdir
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            if p.name == "INDEX.md":
                continue
            harness.artifacts.append(load_artifact(p))
    return harness


def iter_artifact_files(project_root: Path) -> Iterator[Path]:
    root = harness_root(project_root)
    for subdir in TYPE_DIRS.values():
        d = root / subdir
        if d.is_dir():
            yield from sorted(d.glob("*.md"))


def next_id(harness: Harness, atype: str) -> str:
    prefix = TYPE_PREFIX[atype]
    highest = 0
    for a in harness.artifacts:
        m = ID_RE.match(a.id)
        if m and m.group(1) == prefix:
            highest = max(highest, int(m.group(2)))
    return f"{prefix}-{highest + 1:03d}"


def create_artifact(
    project_root: Path,
    atype: str,
    title: str,
    extra_meta: dict[str, Any] | None = None,
    body: str = "",
    artifact_id: str | None = None,
) -> Artifact:
    if atype not in TYPE_PREFIX:
        raise ValueError(f"unknown artifact type: {atype}")
    harness = load_harness(project_root)
    aid = artifact_id or next_id(harness, atype)
    dest_dir = harness_root(project_root) / TYPE_DIRS[atype]
    dest_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "id": aid,
        "type": atype,
        "title": title,
        "status": "draft",
    }
    if extra_meta:
        meta.update(extra_meta)
    meta.setdefault("created", today())
    meta["updated"] = today()
    path = dest_dir / f"{aid}-{slugify(title)}.md"
    if path.exists():
        raise FileExistsError(str(path))
    art = Artifact(path=path, meta=meta, body=body)
    path.write_text(art.render(), encoding="utf-8")
    return art


def update_meta(artifact: Artifact, updates: dict[str, Any]) -> None:
    artifact.meta.update(updates)
    artifact.meta["updated"] = today()
    artifact.path.write_text(artifact.render(), encoding="utf-8")


def derived_status(artifact: Artifact) -> str | None:
    """Derive a spec's status from its tickets (None if not derivable).

    - any ticket in_review  -> in_review
    - all tickets done      -> complete
    - any ticket in_progress-> in_progress (work underway)
    - otherwise             -> draft (planned, not started)
    """
    tickets = artifact.tickets
    if not tickets:
        return None
    statuses = [str(t.get("status", "todo")) for t in tickets]
    if any(s == "in_review" for s in statuses):
        return "in_review"
    if all(s == "done" for s in statuses):
        return "complete"
    if any(s in ("in_progress", "done") for s in statuses):
        return "in_progress"
    return "draft"
