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
from .artifacts import Harness, derived_status, effective_priority, load_harness
from .rules import RuleSet, validate

PROTOCOL = """## Operating protocol (always follow)

1. The tenx CLI self-updates. At session start run `tenx update --check`;
   if it reports a newer version, tell the human and suggest
   `tenx update` to install it. Never block on this — offline is fine.
2. Before planning or coding, load the artifacts relevant to your task
   (`tenx show <ID>`), and read `.tenx/conventions/INDEX.md` plus every
   convention it lists. Conventions bind you.
3. If unsure what to do next, run `tenx next` and do the top item. To
   spot blocked or stalled work, run `tenx watchdog` — it ranks what needs
   attention and says whether each item is being handled.
4. Keep ticket statuses in sync as you work:
   `tenx ticket <SPEC-ID> <TICKET-ID> <status>`.
5. After significant work, write back: `tenx log "what changed" --ref <ID>`.
   When you ship a behavior change, also note it in the changelog (docs-sync):
   `tenx changelog add "what changed" --ref <ID>` — the evidence gate requires
   a changelog entry before a spec/epic can be marked complete.
6. Before ending a session run `tenx validate` and fix any drift you
   introduced. Never leave new errors behind.
7. Process facts live in `.tenx/` artifacts. Do not invent them; if a
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
                "priority": e.priority,
                "path": e.rel(project_root),
                "specs": [s.id for s in harness.specs_for_epic(e.id)],
            } for e in epics
        ],
        "specs": [
            {
                "id": s.id, "title": s.title, "status": s.status,
                "priority": effective_priority(s, harness),
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


TRUNCATE_MARKER = "... [truncated: over budget — run `tenx show <ID>` for full text]"


def apply_budget(sections: list[tuple[str, str]],
                 budget: int) -> tuple[list[tuple[str, str]], list[str]]:
    """Keep priority-ordered sections whole while they fit in `budget`.

    The first section that overflows is cut with TRUNCATE_MARKER; all
    later sections are dropped and their names returned as `omitted`.
    Pure function: no I/O.
    """
    if budget <= 0:
        return [], [name for name, _ in sections]
    kept: list[tuple[str, str]] = []
    omitted: list[str] = []
    used = 0
    cut = False
    for name, text in sections:
        cost = len(text) + 1  # + newline
        if cut:
            omitted.append(name)
            continue
        if used + cost <= budget:
            kept.append((name, text))
            used += cost
        else:
            room = budget - used - len(TRUNCATE_MARKER) - 1
            if room > 80:  # only cut if a useful fragment fits
                kept.append((name, text[:room] + "\n" + TRUNCATE_MARKER))
                used = budget
            else:
                omitted.append(name)
            cut = True
    return kept, omitted


def render_markdown(project_root: Path, mode: str = "agent",
                    harness: Harness | None = None,
                    ruleset: RuleSet | None = None,
                    budget: int | None = None) -> str:
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
    header = f"# TENX CONTEXT PACKET — {name}"
    if data["description"]:
        header += f"\n\n{data['description']}"

    code_line = ""
    if data["code_root"] != data["project_root"]:
        code_line = f"- Code repo (governed): `{data['code_root']}`\n"
    workspace = (
        f"\n## Workspace\n"
        f"- Project root: `{data['project_root']}`\n"
        f"{code_line}"
        f"- Harness (context base): `{data['harness_root']}/`\n"
        f"- CLI: tenx v{data['cli_version']} — agent-facing and "
        f"self-updating; run `tenx update --check` to see if a newer "
        f"version exists.\n"
        f"- Artifacts: {data['counts']['epics']} epics, "
        f"{data['counts']['specs']} specs, {data['counts']['conventions']} conventions, "
        f"{data['counts']['docs']} docs")

    v = data["validation"]
    if v["errors"] or v["warnings"]:
        validation = "\n## Validation state (fix what you can)"
        for f in v["errors"]:
            validation += f"\n- ERROR {f['message']}"
        for f in v["warnings"]:
            validation += f"\n- WARN  {f['message']}"
    else:
        validation = "\n## Validation state\n- clean: no errors or drift warnings"

    conventions = ""
    if data["conventions"]:
        conventions = "\n## Conventions (MUST follow — read before coding)"
        conventions += f"\n- Index: `{data['harness_root']}/conventions/INDEX.md`"
        for c in data["conventions"]:
            conventions += (f"\n- **{c['id']}** {c['title']} "
                            f"`[{c['status']}]` — `{c['path']}`")

    epics_sec = ""
    if data["epics"]:
        epics_sec = "\n## Epics (what we are building)"
        for e in data["epics"]:
            spec_list = ", ".join(e["specs"]) if e["specs"] else "no specs yet"
            epics_sec += (f"\n- **{e['id']}** {e['title']} `[{e['status']}]` "
                          f"— `{e['path']}` (specs: {spec_list})")

    specs_sec = ""
    if data["specs"]:
        specs_sec = "\n## Specs (ticket-by-ticket plans)"
        for s in data["specs"]:
            drift = ""
            if s["derived_status"] and s["derived_status"] != s["status"]:
                drift = f" ⚠ derived={s['derived_status']}"
            specs_sec += (
                f"\n- **{s['id']}** {s['title']} `[{s['status']}]` epic={s['epic']} "
                f"tickets {s['tickets_done']}/{s['tickets_total']} done{drift} "
                f"— `{s['path']}`")

    docs_sec = ""
    if data["docs"]:
        docs_sec = "\n## Docs"
        for d in data["docs"]:
            docs_sec += f"\n- **{d['id']}** {d['title']} — `{d['path']}`"

    activity = ""
    if data["recent_activity"]:
        activity = "\n## Recent activity (latest first)"
        for e in reversed(data["recent_activity"]):
            ref = f" ({e['ref']})" if e.get("ref") else ""
            activity += (f"\n- {e.get('ts', '?')[:16]} [{e.get('type', '?')}]{ref} "
                         f"{e.get('message', '')}")

    # priority order per SPC-004: identity/config -> validation ->
    # conventions -> artifact summaries (epics, specs, docs) -> activity
    sections = [
        ("workspace", workspace),
        ("validation", validation),
        ("conventions", conventions),
        ("epics", epics_sec),
        ("specs", specs_sec),
        ("docs", docs_sec),
        ("recent-activity", activity),
    ]
    sections = [(n, t) for n, t in sections if t]

    omitted_note = ""
    if budget is not None:
        # header + protocol are protected; budget covers the sections
        reserved = len(header) + len(PROTOCOL) + 4
        sections, omitted = apply_budget(sections,
                                         max(0, budget - reserved))
        if omitted:
            omitted_note = ("\n\n[packet budget] omitted sections: "
                            + ", ".join(omitted)
                            + " — raise --budget or run `tenx show <ID>`")

    lines = [header]
    lines += [text for _, text in sections]
    if omitted_note:
        lines.append(omitted_note)
    lines.append("\n" + PROTOCOL)
    return "\n".join(lines) + "\n"
