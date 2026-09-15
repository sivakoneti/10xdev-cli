---
id: EPC-024
type: epic
title: Reactive Swarm Coordination and Zero-Latency Agent Supervision
status: complete
priority: P1
created: 2026-09-15
updated: 2026-09-15
---

## Objective

Deliver reactive, zero-latency subagent lifecycle supervision across `tenx swarm` and `tenx dispatch`. Rather than relying on arbitrary sleep polling or thread blocking, the swarm orchestrator leverages native multiplexer event streams (`herdr pane wait-output`, Herdr JSON-RPC daemon state, tmux status hooks, and process monitors) to instantly detect when a subagent transitions from `working` to `idle` or `done`. This enables instant cascade reconciliation and automatic progression to subsequent DAG execution waves without wasted polling delay.

## Key results

- **KR1**: Swarm execution engine (`src/tenx/swarm.py`) monitors dispatched subagents reactively without blind polling or CPU churn.
- **KR2**: Multiplexer module (`src/tenx/multiplexers.py`) exposes unified `wait_for_pane_completion()` supporting Herdr PTY regex wait triggers (`herdr pane wait-output`), JSON-RPC agent status queries, and tmux exit detection.
- **KR3**: `tenx swarm <SPEC_ID> --auto-reconcile` automatically waits for wave subagents to settle, verifies and merges them into main, and immediately proceeds to the next wave.
- **KR4**: 100% test coverage in automated smoke tests and 0 `tenx validate` errors.

## Scope

- Reactive multiplexer waiting abstraction in `src/tenx/multiplexers.py`.
- Wave-level subagent synchronization loop in `src/tenx/swarm.py`.
- Automated smoke test coverage in `tests/smoke_test.py`.

## Non-goals

- Replacing the harness's internal agent execution loop.
- Cross-machine distributed swarm coordination.

## Milestones

- [x] M1: Implement `wait_for_pane_completion()` and multiplexer agent status queries in `src/tenx/multiplexers.py`.
- [x] M2: Wire reactive wave synchronization and multi-wave automatic reconciliation loop into `src/tenx/swarm.py`.
- [x] M3: Validate end-to-end multi-ticket swarm execution in automated smoke test suite.
