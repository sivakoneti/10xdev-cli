---
id: EPC-022
type: epic
title: Subagent Landing and Reconciliation Lifecycle
status: complete
priority: P0
created: 2026-09-15
updated: 2026-09-15
---

## Objective

Close the autonomous subagent execution loop by providing single-command verification, merging, ticket write-back, and multiplexer workspace teardown (`tenx merge` / `tenx reconcile` and `tenx abort`). Developers and autonomous meta-harnesses can delegate tickets into isolated visual worktrees and cleanly land completed work without manual git worktree surgery, ticket syncing friction, or dangling multiplexer sessions.

## Key results

- KR1 — Single command `tenx reconcile <ticket_id>` executes pre-landing validation (tests + `tenx validate`) in the worktree, merges the worktree branch into the active branch, marks the ticket done, logs activity evidence, and removes the worktree and projected Herdr/tmux session.
- KR2 — Discard command `tenx abort <ticket_id>` cleanly destroys the subagent worktree, drops the branch, and tears down the multiplexer session without polluting project state.
- KR3 — Pre-landing verification failure cleanly aborts merging with actionable diagnostics while preserving the worktree for inspection.
- KR4 — Zero external runtime dependencies maintained (`CON-002`) using Python standard library (`subprocess`, `json`, `pathlib`, `socket`).

## Scope

- Pre-landing test and validation execution within isolated worktrees.
- Semantic merge into current working branch with conflict detection.
- Automated ticket status update and activity log evidence write-back.
- Automated teardown of `.tenx/worktrees/<ticket_id>` and local git branch `tenx/<ticket_id>`.
- Automated closure of projected Herdr workspaces and tmux windows.
- Abort/discard command (`tenx abort`) for abandoning subagent sessions cleanly.
- CLI subcommands and MCP tool exposure (`tenx_reconcile`, `tenx_abort`).

## Non-goals

- Automatic AI resolution of complex 3-way merge conflicts (surfaced as actionable conflict warnings).
- Rewriting arbitrary git history or force-pushing to remote branches.

## Milestones

- [ ] M1 — Implement core verification, merge, write-back, and teardown engine in `src/tenx/reconcile.py`.
- [ ] M2 — Expose CLI subcommands (`tenx reconcile`, `tenx merge`, `tenx abort`) and MCP tool endpoints.
- [ ] M3 — Add comprehensive automated smoke tests and dogfood verification.

