"""tenx.converge - deterministic spec-completion convergence (SPC-025-T4).

Adapted from github/spec-kit's /speckit.converge idea, tenx-shaped: no model
access, stdlib only, deterministic. It maps a spec's numbered requirements
(FR-###) to its tickets and reports which requirements are satisfied, which
are open, and whether the spec is CONVERGED.

Semantics:
- An FR is *satisfied* when a ticket that references it (id in the ticket
  title, e.g. "[FR-001] ...") is done.
- An FR is *uncovered* when no ticket references it at all.
- Open [NEEDS CLARIFICATION] markers (outside code spans) block convergence.
- A spec with no FR-### markers reports NO REQUIREMENTS and is treated as
  converged (legacy specs are immune; the discipline is opt-in by usage).
- The semantic half ("does the code actually meet the requirement?") stays
  with the agent; this output is its checklist.

`--append` is append-only: it creates todo tickets for uncovered FRs and
never renumbers, rewrites, or deletes existing tickets.
"""
from __future__ import annotations

import re
from typing import Any

from .artifacts import Artifact, Harness
from .rules import clarify_markers_open, fr_ids_in, strip_code

_FR_LINE_RE = re.compile(
    r"^\s*[-*]?\s*\**\s*(FR-\d+)\s*\**\s*:?\s*(.*)$")
_SC_LINE_RE = re.compile(
    r"^\s*[-*]?\s*\**\s*(SC-\d+)\s*\**\s*:?\s*(.*)$")


def _requirements(spec: Artifact) -> list[dict[str, str]]:
    """FR ids with their requirement text, in body order."""
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in spec.body.splitlines():
        m = _FR_LINE_RE.match(line)
        if not m:
            continue
        fr = f"FR-{int(m.group(1)[3:]):03d}"
        if fr in seen:
            continue
        seen.add(fr)
        out.append({"id": fr, "text": m.group(2).strip()})
    return out


def _success_criteria(spec: Artifact) -> list[str]:
    out: list[str] = []
    for line in spec.body.splitlines():
        m = _SC_LINE_RE.match(line)
        if m:
            out.append(f"SC-{int(m.group(1)[3:]):03d}")
    return out


def converge(spec: Artifact, harness: Harness) -> dict[str, Any]:
    """Build the convergence report for one spec."""
    reqs = _requirements(spec)
    tickets = spec.tickets
    requirements: list[dict[str, Any]] = []
    uncovered: list[str] = []
    for r in reqs:
        fr = r["id"]
        refs = [t for t in tickets
                if fr in fr_ids_in(str(t.get("title", "")))]
        done = [t for t in refs if str(t.get("status", "")) == "done"]
        satisfied = bool(done)
        if not refs:
            uncovered.append(fr)
        requirements.append({
            "id": fr,
            "text": r["text"],
            "tickets": [str(t.get("id", "?")) for t in refs],
            "done_tickets": [str(t.get("id", "?")) for t in done],
            "satisfied": satisfied,
        })
    open_markers = clarify_markers_open(spec.body)
    has_reqs = bool(reqs)
    converged = (not has_reqs) or (
        open_markers == 0 and all(r["satisfied"] for r in requirements))
    if not has_reqs:
        verdict = "NO REQUIREMENTS"
    elif converged:
        verdict = "CONVERGED"
    else:
        verdict = "NOT CONVERGED"
    return {
        "spec": spec.id,
        "status": spec.status,
        "requirements": requirements,
        "success_criteria": _success_criteria(spec),
        "open_clarify_markers": open_markers,
        "uncovered": uncovered,
        "converged": converged,
        "verdict": verdict,
    }


def _next_ticket_num(spec: Artifact) -> int:
    n = 0
    pat = re.compile(re.escape(spec.id) + r"-T(\d+)")
    for t in spec.tickets:
        m = pat.search(str(t.get("id", "")))
        if m:
            n = max(n, int(m.group(1)))
    return n + 1


def _trim(text: str, limit: int = 60) -> str:
    text = re.sub(r"\[NEEDS CLARIFICATION[^\]]*\]", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "..."


def append_missing_tickets(spec: Artifact, report: dict[str, Any],
                           harness: Harness) -> list[str]:
    """Append a todo ticket per uncovered FR. Append-only; returns the ids
    created. Rewrites the artifact file (frontmatter + Tickets section)."""
    created: list[str] = []
    if not report["uncovered"]:
        return created
    by_id = {r["id"]: r for r in report["requirements"]}
    num = _next_ticket_num(spec)
    new_lines: list[str] = []
    for fr in report["uncovered"]:
        tid = f"{spec.id}-T{num}"
        num += 1
        title = f"[{fr}] {_trim(by_id[fr]['text']) or 'implement requirement'}"
        spec.meta.setdefault("tickets", []).append(
            {"id": tid, "title": title, "status": "todo"})
        created.append(tid)
        new_lines.append(f"- {tid} {title}")
    # insert into the body Tickets section (append at section end)
    lines = spec.body.splitlines()
    out: list[str] = []
    in_sec = False
    inserted = False
    for i, ln in enumerate(lines):
        if ln.startswith("## Tickets"):
            in_sec = True
            out.append(ln)
            continue
        if in_sec and not inserted and ln.startswith("## "):
            out.extend(new_lines)
            out.append("")
            inserted = True
            in_sec = False
        out.append(ln)
    if in_sec and not inserted:
        out.extend(new_lines)
        inserted = True
    if not inserted:  # no Tickets section: create one before Open questions
        out.extend(["", "## Tickets", ""] + new_lines)
    spec.body = "\n".join(out).rstrip() + "\n"
    spec.path.write_text(spec.render(), encoding="utf-8")
    return created
