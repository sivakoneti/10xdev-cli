"""`tenx next` — derive the most important thing to work on next.

Priority order (the same loop a senior engineer would apply):

1. validation errors            -> fix the harness first
2. drift warnings               -> reconcile authored vs derived state
3. specs in_review              -> review and land them
4. active specs with ready work -> name the isolated-worker command
5. active specs with open tickets -> implement the next ticket in band
6. draft epics without specs    -> write specs
7. nothing queued               -> say so, suggest creating an epic

Bucket 4 is a routing decision, not work: an isolated worker preserves the
supervisor's context, so the exact command is surfaced next to the in-band
alternative instead of being left for the reader to discover.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import Harness, effective_priority, load_harness
from .dag import build_spec_dag
from .rules import RuleSet, validate

TICKET_ORDER = {"in_progress": 0, "todo": 1, "in_review": 2, "done": 3}

# Business priority tiers refine ordering WITHIN the "do the work" buckets
# (review / delegate / implement / write-specs). Harness health (errors,
# drift) always comes first regardless of priority — fix the machine, then build.
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}
UNSET_RANK = 3


def _rank(prio: str) -> int:
    return PRIORITY_RANK.get(prio, UNSET_RANK)


def ready_tickets(spec) -> list[tuple[str, str]]:
    """Open, dependency-satisfied tickets as (ticket_id, status), in work order.

    Falls back to plain status filtering when the spec's dependency graph is
    unusable, so a malformed `depends_on` can never hide ready work.
    """
    try:
        dag = build_spec_dag(spec)
        pairs = [(tid, node.status) for tid, node in dag.nodes.items()
                 if dag.is_ticket_ready(tid)]
    except Exception:
        pairs = [(str(t.get("id")), str(t.get("status")))
                 for t in (spec.tickets or [])
                 if t.get("id") and str(t.get("status")) in ("todo", "in_progress")]
    return sorted(pairs, key=lambda p: (TICKET_ORDER.get(p[1], 9), p[0]))


def compute_next(project_root: Path, harness: Harness | None = None,
                 ruleset: RuleSet | None = None) -> list[dict[str, Any]]:
    harness = harness or load_harness(project_root)
    ruleset = ruleset or validate(project_root, harness)
    actions: list[dict[str, Any]] = []

    def add(priority: int, action: str, ref: str | None = None,
            path: str | None = None, detail: str = "",
            biz: str = "") -> None:
        actions.append({"priority": priority, "action": action, "ref": ref,
                       "path": path, "detail": detail, "biz": biz,
                       "biz_rank": _rank(biz)})

    for f in ruleset.errors():
        add(1, "fix validation error", f.artifact_id, f.path, f.message)
    for f in ruleset.warnings():
        add(2, "reconcile drift", f.artifact_id, f.path, f.message)

    for s in harness.by_type("spec"):
        if s.status == "in_review":
            add(3, "review spec and land or bounce it", s.id,
                s.rel(project_root), f"{s.title}",
                biz=effective_priority(s, harness))

    for s in harness.by_type("spec"):
        if s.status not in ("draft", "in_progress"):
            continue
        ready = ready_tickets(s)
        if not ready:
            continue
        biz = effective_priority(s, harness)
        first = ready[0][0]
        detail = f"tenx dispatch {s.id} {first} --visual"
        if len(ready) > 1:
            detail += (f"  (or tenx swarm {s.id} --visual"
                       f" for {len(ready)} parallel workers)")
        add(4, f"delegate ready ticket {first} of {s.id} to an isolated worker",
            s.id, s.rel(project_root), detail, biz=biz)

    for e in harness.by_type("epic"):
        if e.status not in ("draft", "in_review", "in_progress"):
            continue
        specs = harness.specs_for_epic(e.id)
        active = [s for s in specs if s.status in ("draft", "in_progress", "in_review")]
        if not specs:
            add(6, f"write specs for epic {e.id}", e.id, e.rel(project_root),
                e.title, biz=e.priority)
            continue
        for s in active:
            biz = effective_priority(s, harness)
            open_tickets = [t for t in s.tickets
                           if str(t.get("status")) in ("todo", "in_progress")]
            open_tickets.sort(key=lambda t: TICKET_ORDER.get(
                str(t.get("status")), 9))
            if not open_tickets and s.status == "draft":
                add(5, f"break spec {s.id} into tickets", s.id,
                    s.rel(project_root), s.title, biz=biz)
                continue
            for t in open_tickets:
                add(5, f"implement ticket {t.get('id')} of {s.id}", s.id,
                    s.rel(project_root),
                    f"[{t.get('status')}] {t.get('title', '')}", biz=biz)

    if not actions:
        add(7, "no queued work — create an epic", None, None,
            'tenx new epic "What we are building next"')
    # Primary: action type (fix harness first). Secondary: business
    # priority so P0 work floats above P1/P2/unset within the same bucket.
    actions.sort(key=lambda a: (a["priority"], a["biz_rank"]))
    return actions


def render_next(project_root: Path) -> str:
    actions = compute_next(project_root)
    lines = ["# tenx next — prioritized work queue", ""]
    top_prio = actions[0]["priority"]
    for i, a in enumerate(actions[:15], 1):
        marker = "→ " if a["priority"] == top_prio else "  "
        ref = f" [{a['ref']}]" if a.get("ref") else ""
        biz = f" {a['biz']}" if a.get("biz") else ""
        detail = f" — {a['detail']}" if a.get("detail") else ""
        lines.append(f"{marker}{i}.{biz} {a['action']}{ref}{detail}")
        if a.get("path"):
            lines.append(f"      file: {a['path']}")
    if len(actions) > 15:
        lines.append(f"\n… and {len(actions) - 15} more items "
                     "(tenx next --json for the full list)")
    return "\n".join(lines) + "\n"
