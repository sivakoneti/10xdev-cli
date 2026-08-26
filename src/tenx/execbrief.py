"""Autonomous execution briefs — the `/execute project spec` equivalent.

`tenx exec <SPEC-ID>` prints a self-contained execution brief: a prompt you
hand to a coding agent (Claude Code, Codex, ...) to autonomously work a spec
ticket by ticket, with mandatory write-back to the harness.

Usage patterns:
    tenx exec SPC-001 | claude -p          # headless overnight run
    tenx exec SPC-001                      # paste into an interactive session
"""

from __future__ import annotations

from .artifacts import Harness
from .discovery import code_root

BRIEF_TEMPLATE = """# EXECUTION BRIEF — {spec_id}: {title}

You are executing a spec from the tenx context base. Work autonomously,
ticket by ticket, and write back every state change to the harness.

## Workspace
- Code repo (do the implementation here): `{code_root}`
- Context base (harness): `{harness_root}`
- Spec: `{spec_path}`
{epic_line}
## Read first (in this order)
1. The spec above — the ticket list is your work queue.
2. Referenced conventions under `{harness_root}/conventions/` — follow them.
3. The parent epic (if listed) — for intent and scope.

## Work loop (repeat per ticket, in order)
1. Implement the ticket in the code repo. Follow the spec and conventions.
2. Mark it done and record what happened:
   `tenx ticket {spec_id} <TICKET-ID> done`
   `tenx log "<one line: what changed>" --type progress --ref {spec_id}`
3. If a ticket is blocked, mark it `blocked` and log why; move to the next.

## When all tickets are done
1. Document the shipped work (docs-sync, enforced):
   `tenx changelog add "<what shipped>" --ref {spec_id}`
2. `tenx validate` — fix every error and warning you introduced.
3. `tenx converge {spec_id}` — if the spec uses FR-### requirements,
   converge must report CONVERGED: every requirement satisfied by a done
   ticket, no open [NEEDS CLARIFICATION] markers. Use
   `tenx converge {spec_id} --append` to create tickets for requirements
   nobody covered yet. Specs without FR-### markers report NO REQUIREMENTS
   and pass.
4. `tenx set {spec_id} status complete` — the evidence gate checks that
   every ticket is done, that work is logged/evidenced, and that the
   changelog has an entry. If it blocks, fix the reason it names; use
   `--force` only on explicit human instruction (it is audit-logged).
5. Commit the code repo, then commit the harness changes (they are the
   audit trail of what you did). The pre-commit gate re-runs validate and
   warns/blocks when staged code has no write-back behind it.

## Hard rules
- Never mark the spec complete while any ticket is not done — the
  validator derives spec status from tickets and will flag drift.
- Never skip the write-back: the activity log is how the next session
  (human or agent) knows what happened. Commits of unlogged code are
  flagged by the gate.
- If the spec is ambiguous, stop and record the question in the log
  instead of guessing silently.

Current ticket states:
{ticket_lines}
"""


def build_exec_brief(harness: Harness, spec, project_root) -> str:
    cfg = harness.config or {}
    cr = code_root(project_root, cfg)
    epic_line = ""
    if spec.meta.get("epic"):
        epic_line = f"- Parent epic: `{spec.meta['epic']}`\n"
    tickets = spec.tickets
    if tickets:
        ticket_lines = "\n".join(
            f"- {t.get('id', '?')}: {t.get('status', 'todo')}"
            + (f" — {t['title']}" if t.get("title") else "")
            for t in tickets)
    else:
        ticket_lines = "- (no tickets declared — add them with " \
                       "`tenx ticket <SPEC> <TICKET> todo` first)"
    return BRIEF_TEMPLATE.format(
        spec_id=spec.meta.get("id", "?"),
        title=spec.meta.get("title", ""),
        code_root=cr,
        harness_root=harness.root,
        spec_path=spec.path,
        epic_line=epic_line,
        ticket_lines=ticket_lines,
    )
