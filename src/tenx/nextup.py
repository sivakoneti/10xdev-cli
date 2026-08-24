"""`tenx next` — derive the most important thing to work on next.

Priority order (the same loop a senior engineer would apply):

1. validation errors            -> fix the harness first
2. drift warnings               -> reconcile authored vs derived state
3. specs in_review              -> review and land them
4. active specs with open tickets -> implement next ticket
5. draft epics without specs    -> write specs
6. nothing queued               -> say so, suggest creating an epic
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import Harness, load_harness
from .rules import RuleSet, validate

TICKET_ORDER = {"in_progress": 0, "todo": 1, "in_review": 2, "done": 3}


def compute_next(project_root: Path, harness: Harness | None = None,
                 ruleset: RuleSet | None = None) -> list[dict[str, Any]]:
    harness = harness or load_harness(project_root)
    ruleset = ruleset or validate(project_root, harness)
    actions: list[dict[str, Any]] = []

    def add(priority: int, action: str, ref: str | None = None,
            path: str | None = None, detail: str = "") -> None:
        actions.append({"priority": priority, "action": action, "ref": ref,
                       "path": path, "detail": detail})

    for f in ruleset.errors():
        add(1, "fix validation error", f.artifact_id, f.path, f.message)
    for f in ruleset.warnings():
        add(2, "reconcile drift", f.artifact_id, f.path, f.message)

    for s in harness.by_type("spec"):
        if s.status == "in_review":
            add(3, "review spec and land or bounce it", s.id,
                s.rel(project_root), f"{s.title}")

    for e in harness.by_type("epic"):
        if e.status not in ("draft", "in_review", "in_progress"):
            continue
        specs = harness.specs_for_epic(e.id)
        active = [s for s in specs if s.status in ("draft", "in_progress", "in_review")]
        if not specs:
            add(5, f"write specs for epic {e.id}", e.id, e.rel(project_root),
                e.title)
            continue
        for s in active:
            open_tickets = [t for t in s.tickets
                           if str(t.get("status")) in ("todo", "in_progress")]
            open_tickets.sort(key=lambda t: TICKET_ORDER.get(
                str(t.get("status")), 9))
            if not open_tickets and s.status == "draft":
                add(4, f"break spec {s.id} into tickets", s.id,
                    s.rel(project_root), s.title)
                continue
            for t in open_tickets:
                add(4, f"implement ticket {t.get('id')} of {s.id}", s.id,
                    s.rel(project_root),
                    f"[{t.get('status')}] {t.get('title', '')}")

    if not actions:
        add(6, "no queued work — create an epic", None, None,
            'tenx new epic "What we are building next"')
    actions.sort(key=lambda a: a["priority"])
    return actions


def render_next(project_root: Path) -> str:
    actions = compute_next(project_root)
    lines = ["# tenx next — prioritized work queue", ""]
    top_prio = actions[0]["priority"]
    for i, a in enumerate(actions[:15], 1):
        marker = "→ " if a["priority"] == top_prio else "  "
        ref = f" [{a['ref']}]" if a.get("ref") else ""
        detail = f" — {a['detail']}" if a.get("detail") else ""
        lines.append(f"{marker}{i}. {a['action']}{ref}{detail}")
        if a.get("path"):
            lines.append(f"      file: {a['path']}")
    if len(actions) > 15:
        lines.append(f"\n… and {len(actions) - 15} more items "
                     "(tenx next --json for the full list)")
    return "\n".join(lines) + "\n"
