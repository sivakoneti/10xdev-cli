"""Context packets: the "benevolent prompt injection".

`tenx context --mode agent` prints everything an agent needs to start a
session like a senior engineer on the project: workspace identity, every
artifact and where to find it, recent activity, validation state, and the
operating protocol.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import __version__
from .activity import read_entries
from .discovery import code_root
from .artifacts import Harness, derived_status, load_harness
from .rules import RuleSet, validate

PROTOCOL = """## Operating protocol (always follow)

1. Before planning or coding, load the artifacts relevant to your task
   (`tenx show <ID>`), and read `.tenx/conventions/INDEX.md` plus every
   convention it lists. Conventions bind you.
2. If unsure what to do next, run `tenx next` and do the top item.
3. Keep ticket statuses in sync as you work:
   `tenx ticket <SPEC-ID> <TICKET-ID> <status>`.
4. After significant work, write back: `tenx log "what changed" --ref <ID>`.
5. Before ending a session run `tenx validate` and fix any drift you
   introduced. Never leave new errors behind.
6. Process facts live in `.tenx/` artifacts. Do not invent them; if a
   convention conflicts with a spec, stop and ask the human."""


def _status_counts(items: list) -> dict[str, int]:
    counts: dict[str, int] = {}
    for a in items:
        counts[a.status or "unknown"] = counts.get(a.status or "unknown", 0) + 1
    return counts


def _fmt_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{n} {k}" for k, n in sorted(counts.items()))


def build_context(project_root: Path, mode: str = "agent",
                  harness: Harness | None = None,
                  ruleset: RuleSet | None = None) -> dict[str, Any]:
    harness = harness or load_harness(project_root)
    ruleset = ruleset or validate(project_root, harness)
    cfg = harness.config or {}
    epics, specs = harness.by_type("epic"), harness.by_type("spec")
    cons, docs = harness.by_type("convention"), harness.by_type("doc")
    entries = read_entries(project_root, limit=10)

    data: dict[str, Any] = {
        "cli_version": __version__,
        "mode": mode,
        "project": cfg.get("project", project_root.name),
        "description": cfg.get("description", ""),
        "project_root": str(project_root),
        "harness_root": str(harness.root),
        "code_root": str(code_root(project_root, cfg)),
        "counts": {
            "epics": len(epics),
            "specs": len(specs),
            "conventions": len(cons),
            "docs": len(docs),
        },
        "status_counts": {
            "epics": _status_counts(epics),
            "specs": _status_counts(specs),
        },
        "epics": [
            {
                "id": e.id, "title": e.title, "status": e.status,
                "path": e.rel(project_root),
                "specs": [s.id for s in harness.specs_for_epic(e.id)],
            } for e in epics
        ],
        "specs": [
            {
                "id": s.id, "title": s.title, "status": s.status,
                "epic": s.meta.get("epic"),
                "derived_status": derived_status(s),
                "tickets_total": len(s.tickets),
                "tickets_done": sum(1 for t in s.tickets
                                    if str(t.get("status")) == "done"),
                "path": s.rel(project_root),
            } for s in specs
        ],
        "conventions": [
            {"id": c.id, "title": c.title, "status": c.status,
             "path": c.rel(project_root)} for c in cons
        ],
        "docs": [
            {"id": d.id, "title": d.title, "path": d.rel(project_root)}
            for d in docs
        ],
        "recent_activity": entries,
        "validation": {
            "errors": [f.to_dict() for f in ruleset.errors()],
            "warnings": [f.to_dict() for f in ruleset.warnings()],
            "info": [f.to_dict() for f in ruleset.infos()],
        },
    }
    return data


def render_markdown(project_root: Path, mode: str = "agent",
                    harness: Harness | None = None,
                    ruleset: RuleSet | None = None) -> str:
    data = build_context(project_root, mode, harness, ruleset)
    name = data["project"]
    lines: list[str] = []

    if mode == "operator":
        lines.append(f"# {name} — operator dashboard")
        if data["description"]:
            lines.append(f"\n{data['description']}")
        c = data["counts"]
        lines.append(
            f"\nArtifacts: {c['epics']} epics, {c['specs']} specs, "
            f"{c['conventions']} conventions, {c['docs']} docs "
            f"(tenx v{data['cli_version']})")
        lines.append(f"- spec statuses: {_fmt_counts(data['status_counts']['specs'])}")
        lines.append(f"- epic statuses: {_fmt_counts(data['status_counts']['epics'])}")
        v = data["validation"]
        if v["errors"]:
            lines.append(f"\n## Errors ({len(v['errors'])})")
            lines += [f"- {f['message']} ({f['rule']})" for f in v["errors"]]
        if v["warnings"]:
            lines.append(f"\n## Drift warnings ({len(v['warnings'])})")
            lines += [f"- {f['message']}" for f in v["warnings"]]
        if data["recent_activity"]:
            lines.append("\n## Recent activity")
            lines += [
                f"- {e.get('ts', '?')[:16]} [{e.get('type', '?')}] "
                f"{e.get('message', '')}" + (f" ({e['ref']})" if e.get("ref") else "")
                for e in data["recent_activity"][-5:]
            ]
        lines.append("\nRun `tenx next` for the highest-value action, "
                     "`tenx context --mode agent` for the full packet.")
        return "\n".join(lines) + "\n"

    # ---- agent mode: full packet ----
    lines.append(f"# TENX CONTEXT PACKET — {name}")
    if data["description"]:
        lines.append(f"\n{data['description']}")
    code_line = ""
    if data["code_root"] != data["project_root"]:
        code_line = f"- Code repo (governed): `{data['code_root']}`\n"
    lines.append(
        f"\n## Workspace\n"
        f"- Project root: `{data['project_root']}`\n"
        f"{code_line}"
        f"- Harness (context base): `{data['harness_root']}/`\n"
        f"- CLI: tenx v{data['cli_version']} — use it; it is agent-facing.\n"
        f"- Artifacts: {data['counts']['epics']} epics, "
        f"{data['counts']['specs']} specs, {data['counts']['conventions']} conventions, "
        f"{data['counts']['docs']} docs")

    if data["epics"]:
        lines.append("\n## Epics (what we are building)")
        for e in data["epics"]:
            spec_list = ", ".join(e["specs"]) if e["specs"] else "no specs yet"
            lines.append(f"- **{e['id']}** {e['title']} `[{e['status']}]` "
                         f"— `{e['path']}` (specs: {spec_list})")
    if data["specs"]:
        lines.append("\n## Specs (ticket-by-ticket plans)")
        for s in data["specs"]:
            drift = ""
            if s["derived_status"] and s["derived_status"] != s["status"]:
                drift = f" ⚠ derived={s['derived_status']}"
            lines.append(
                f"- **{s['id']}** {s['title']} `[{s['status']}]` epic={s['epic']} "
                f"tickets {s['tickets_done']}/{s['tickets_total']} done{drift} "
                f"— `{s['path']}`")
    if data["conventions"]:
        lines.append("\n## Conventions (MUST follow — read before coding)")
        lines.append(f"- Index: `{data['harness_root']}/conventions/INDEX.md`")
        for c in data["conventions"]:
            lines.append(f"- **{c['id']}** {c['title']} `[{c['status']}]` — `{c['path']}`")
    if data["docs"]:
        lines.append("\n## Docs")
        for d in data["docs"]:
            lines.append(f"- **{d['id']}** {d['title']} — `{d['path']}`")

    if data["recent_activity"]:
        lines.append("\n## Recent activity (latest first)")
        for e in reversed(data["recent_activity"]):
            ref = f" ({e['ref']})" if e.get("ref") else ""
            lines.append(f"- {e.get('ts', '?')[:16]} [{e.get('type', '?')}]{ref} "
                         f"{e.get('message', '')}")

    v = data["validation"]
    if v["errors"] or v["warnings"]:
        lines.append("\n## Validation state (fix what you can)")
        for f in v["errors"]:
            lines.append(f"- ERROR {f['message']}")
        for f in v["warnings"]:
            lines.append(f"- WARN  {f['message']}")
    else:
        lines.append("\n## Validation state\n- clean: no errors or drift warnings")

    lines.append("\n" + PROTOCOL)
    return "\n".join(lines) + "\n"
