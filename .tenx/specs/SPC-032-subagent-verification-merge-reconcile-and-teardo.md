---
id: SPC-032
type: spec
title: "Subagent Verification, Merge Reconcile, and Teardown Engine"
status: complete
epic: EPC-022
priority: P0
created: 2026-09-15
updated: 2026-09-15
tickets:
  - id: SPC-032-T1
    title: "Implement core worktree verification, git merge, ticket update, and teardown in tenx.reconcile [FR-001, FR-002, FR-003, FR-004]"
    status: done
  - id: SPC-032-T2
    title: "Expose tenx reconcile, tenx merge, and tenx abort in CLI and MCP tools [FR-001, FR-004, FR-005]"
    status: done
  - id: SPC-032-T3
    title: "Add comprehensive automated smoke tests and dogfood verification [FR-001, FR-002, FR-003, FR-004, FR-005]"
    status: done
---

## Summary

Build an automated landing and reconciliation engine (`tenx reconcile` / `tenx merge` and `tenx abort`) that verifies subagent work inside its isolated worktree, merges changes back to the active branch, updates the corresponding ticket to `done`, writes back activity log evidence, and cleans up both the git worktree and any projected multiplexer sessions (Herdr or tmux).

## Context and scope

Currently, after dispatching a subagent via `tenx dispatch`, reconciling completed work requires multiple manual steps: inspecting worktree status, running test suites, merging git branches, pruning worktrees, deleting branches, updating ticket statuses, writing activity logs, and closing Herdr/tmux workspaces. This engine automates the entire lifecycle into a single atomic operation.

## Goals / non-goals

Goals:
- Single-command subagent reconciliation: `tenx reconcile <ticket_id>` (alias: `tenx merge <ticket_id>`).
- Pre-landing verification: run tests and `tenx validate` in the subagent worktree before initiating a merge.
- Automated cleanup: tear down git worktrees, delete subagent branches, and close projected Herdr workspaces / tmux windows.
- Atomic write-back: update ticket in spec to `done` and record verified landing evidence in activity log.
- Clean abort: `tenx abort <ticket_id>` to discard and tear down worktree/sessions cleanly without merging.

Non-goals:
- AI-driven auto-resolution of non-trivial 3-way merge conflicts.
- Force pushing or remote repository synchronization.

## Requirements

- FR-001: The system MUST locate the subagent worktree `.tenx/worktrees/<ticket_id>` and verify branch status.
- FR-002: The system MUST run pre-landing verification (`tenx validate` and automated tests if present) inside the worktree before allowing merge; if verification fails, merge MUST be aborted with diagnostic output.
- FR-003: The system MUST merge the subagent branch into the parent working branch, handling clean merges and cleanly reporting conflicts.
- FR-004: The system MUST cleanly teardown the git worktree, remove the subagent branch, and close associated Herdr workspaces or tmux windows.
- FR-005: The system MUST provide an abort command (`tenx abort <ticket_id>`) that tears down the worktree and multiplexer session without merging.

## Success criteria

- SC-001: `tenx reconcile <ticket_id>` cleanly verifies, merges, updates ticket status to `done`, logs evidence, and removes the worktree.
- SC-002: `tenx abort <ticket_id>` cleans up worktree and multiplexer sessions cleanly.
- SC-003: Pre-landing verification failure halts the merge and leaves the worktree intact for developer inspection.
- SC-004: Zero external runtime dependencies (`CON-002`) using standard library only.
- SC-005: 100% of smoke tests pass and `tenx validate` reports 0 errors.

## Design

- `src/tenx/reconcile.py`: Contains `reconcile_subagent_ticket(...)` and `abort_subagent_ticket(...)`.
  - Locates `.tenx/worktrees/<ticket_id>`.
  - Runs pre-landing checks (`PYTHONPATH=src python3 -m tenx.cli validate`, tests).
  - Performs `git merge tenx/<ticket_id>`.
  - Closes multiplexer sessions (Herdr via socket RPC or CLI `herdr workspace close`, tmux via `tmux kill-window`).
  - Prunes worktree via `git worktree remove --force` and drops branch via `git branch -d` or `-D`.
  - Updates spec ticket status and appends `activity.jsonl` entry.
- CLI exposure in `src/tenx/cli.py` (`reconcile`, `merge`, `abort`).
- MCP tool exposure in `src/tenx/mcp.py` (`tenx_reconcile`, `tenx_abort`).

## Alternatives considered

- Requiring manual git merges: High friction and error prone.
- Blind merge without pre-landing verification: Can pollute master branch with unvalidated subagent code.

## Cross-cutting concerns

- Concurrency: Ensure git index locks and harness locks are respected.
- Workspace cleanup safety: Ensure parent workspace is never closed.

## Validation

- Automated smoke tests testing reconcile success, verification failure blocking, abort cleanup, and MCP tool invocations.
- `tenx validate` passes with 0 errors.

## Open questions

- None.
