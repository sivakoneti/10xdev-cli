---
id: SPC-034
type: spec
title: Reactive Subagent Wait and Event-Driven Swarm Progression
status: complete
epic: EPC-024
created: 2026-09-15
updated: 2026-09-15
priority: P1
tickets:
  - id: SPC-034-T1
    title: "[FR-001, FR-002] Implement wait_for_subagent_completion and multiplexer status queries"
    status: done
  - id: SPC-034-T2
    title: "[FR-003, FR-004] Implement reactive multi-wave swarm synchronization and auto-reconciliation loop"
    status: done
    depends_on:
      - SPC-034-T1
  - id: SPC-034-T3
    title: "[FR-005, SC-001, SC-002] Automated smoke tests and dogfood validation"
    status: done
    depends_on:
      - SPC-034-T2
---

## Summary

This specification implements reactive, event-driven waiting for subagents dispatched across terminal multiplexers (`herdr`, `tmux`) and headless processes. It eliminates blind sleep loops and enables `tenx swarm` to autonomously progress through multi-wave DAG dependency graphs with zero-latency cascade reconciliation.

## Context and scope

`tenx dispatch` supports visual multiplexer projection into Herdr workspaces and tmux windows, and `tenx swarm` partitions spec tickets into topological dependency waves. However, the swarm coordinator previously lacked an event-driven synchronization primitive to wait until all workers in a wave complete before attempting reconciliation or launching the next wave. This spec provides that missing layer.

## Goals / non-goals

Goals:
- Unified `wait_for_subagent_completion()` in `src/tenx/multiplexers.py` supporting Herdr VT stream matchers (`herdr pane wait-output`), JSON-RPC agent status queries (`agent_status == 'idle' | 'done'`), tmux pane check, and subprocess waiting.
- Event-driven wave progression in `src/tenx/swarm.py` that waits for all tickets in Wave $N$ to settle, verifies and reconciles them into the parent branch, and immediately dispatches Wave $N+1$.
- Bounded timeouts with graceful failure reporting and zero residue worktree cleanup.

Non-goals:
- Polling terminal screens via optical character recognition or screen scraping.
- Changing git branch isolation discipline.

## Requirements

- FR-001: The system MUST provide `wait_for_subagent_completion()` supporting Herdr PTY wait triggers (`herdr pane wait-output`) and JSON-RPC status checks.
- FR-002: The system MUST support tmux window exit detection and headless process wait.
- FR-003: `execute_spec_swarm` MUST support waiting for the current wave's dispatched workers to finish before progressing to the next wave when `auto_reconcile=True`.
- FR-004: If any subagent in a wave fails verification or times out, subsequent dependent waves MUST be aborted or skipped with a detailed status summary.
- FR-005: 100% automated test coverage in `tests/smoke_test.py` and 0 `tenx validate` errors.

## Success criteria

- SC-001: `tenx swarm` can execute a multi-wave spec autonomously, waiting reactively for wave completion and automatically reconciling each wave without manual polling.
- SC-002: Automated smoke tests pass cleanly in both standard and hermetic modes.

## Design

- In `src/tenx/multiplexers.py`, implement `wait_for_subagent_completion(multiplexer, target_id, timeout_sec)`. For Herdr, it executes `herdr pane wait-output <pane_id> --regex "..." --timeout <ms>` and checks `herdr pane get <pane_id>` for `agent_status in ("idle", "done")`.
- In `src/tenx/dispatch.py`, return `pane_id` or `window_id` in the dispatch result payload so the caller can wait on it.
- In `src/tenx/swarm.py`, loop through DAG waves sequentially: in each wave, dispatch ready tickets in parallel up to `max_parallel`, wait reactively for their completion, auto-reconcile, and advance to the next wave.

## Tickets

- [x] SPC-034-T1: [FR-001, FR-002] Implement wait_for_subagent_completion and multiplexer status queries
- [ ] SPC-034-T2: [FR-003, FR-004] Implement reactive multi-wave swarm synchronization and auto-reconciliation loop (depends: SPC-034-T1)
- [ ] SPC-034-T3: [FR-005, SC-001, SC-002] Automated smoke tests and dogfood validation (depends: SPC-034-T2)

## Validation

- `python3 tests/smoke_test.py`
- `PYTHONPATH=src python3 tests/smoke_test.py --module`
- `tenx validate`

definition of done. Where practical, phrase acceptance scenarios as
Given/When/Then lines tied to requirement ids, e.g.
`FR-001: Given <state>, When <action>, Then <observable outcome>`.

## Open questions

- None yet.
