---
id: SPC-033
type: spec
title: Swarm DAG Scheduling and Parallel Subagent Dispatch
status: complete
epic: EPC-023
created: 2026-09-15
updated: 2026-09-15
tickets:
  - id: SPC-033-T1
    title: "[FR-001, FR-002, FR-003] Implement DAG graph resolution, cycle detection, and wave partitioning"
    status: done
  - id: SPC-033-T2
    title: "[FR-004, FR-005] Implement swarm coordinator engine with wave dispatch and cascade reconciliation"
    status: done
  - id: SPC-033-T3
    title: "[FR-006] Expose CLI commands, MCP tools, and verify automated smoke tests"
    status: done
---

## Summary

Build DAG graph resolution, cycle detection, wave partitioning, and swarm orchestration for tenx spec tickets. Enables autonomous agents and developers to declare ticket dependencies (`depends_on`) and execute parallel subagent swarms via `tenx swarm` with automated wave progression and cascade reconciliation.

## Context and scope

With `tenx dispatch` (`EPC-018`, `EPC-019`, `EPC-020`) and `tenx reconcile` (`EPC-022`), subagents can be dispatched into isolated worktrees and visual multiplexers, and subsequently verified and merged back. However, orchestrating specs with interdependent tickets requires manual sequencing. By introducing dependency graphs into spec tickets, `tenx swarm` can partition tickets into topological execution waves, dispatch independent tickets in parallel, and advance waves as work completes.

## Goals / non-goals

Goals:
- Support `depends_on: [TICKET_ID, ...]` in spec ticket definitions.
- Build DAG dependency solver with circular dependency detection in standard library (`src/tenx/dag.py`).
- Implement swarm coordinator (`src/tenx/swarm.py`) for parallel wave dispatch, status tracking, and cascade reconciliation.
- Expose `tenx dag <SPEC_ID>` and `tenx swarm <SPEC_ID>` CLI commands and corresponding MCP tools (`tenx_dag`, `tenx_swarm`).
- Maintain zero runtime dependencies (`CON-002`).

Non-goals:
- Cross-spec ticket dependencies (dependencies must reside within the same spec).
- Dynamic re-scheduling of running agents based on mid-run failures (failures halt downstream wave progression).

## Requirements

- FR-001: The system MUST parse `depends_on` lists on spec tickets and construct an in-memory directed acyclic graph.
- FR-002: The system MUST detect cycles in ticket dependencies and raise descriptive validation errors.
- FR-003: The system MUST partition tickets into topological execution waves (waves 0, 1, 2, ...) where all dependencies of tickets in wave $N$ reside in waves $< N$.
- FR-004: The system MUST support `tenx dag <SPEC_ID> [--json]` to inspect dependency trees, execution waves, and ready tickets.
- FR-005: The system MUST support `tenx swarm <SPEC_ID> [--max-parallel N] [--dry-run] [--visual] [--agent A] [--model M] [--json]` to orchestrate wave-based execution and reconciliation.
- FR-006: The system MUST expose `tenx_dag` and `tenx_swarm` as MCP tools.

## Success criteria

- SC-001: Topological sort correctly identifies parallel waves and detects circular dependencies.
- SC-002: `tenx swarm --dry-run` outputs full execution wave plan with assigned harnesses and models.
- SC-003: Smoke test suite validates DAG solver, cycle detection, CLI subcommands, and MCP tool execution.

## Design

### Components

1. `src/tenx/dag.py`:
   - `TicketNode`: Dataclass containing ticket info and dependencies.
   - `build_spec_dag(spec: Artifact)`: Constructs dependency mapping from `tickets`.
   - `detect_cycles(nodes: dict[str, TicketNode])`: Tarjan's or Kahn's algorithm for cycle detection.
   - `compute_execution_waves(nodes: dict[str, TicketNode]) -> list[list[str]]`: Returns ordered lists of ticket IDs grouped into concurrent execution waves.

2. `src/tenx/swarm.py`:
   - `SwarmPlanner`: Prepares dispatch instructions for tickets in the active wave.
   - `execute_swarm_wave(project_root, spec_id, wave, options)`: Invokes `dispatch_subagent_ticket` for each ready ticket in parallel (or sequentially if `--max-parallel 1`).

3. `src/tenx/cli.py` & `src/tenx/mcp.py`:
   - CLI bindings for `dag` and `swarm`.
   - MCP tools `tenx_dag` and `tenx_swarm`.

## Alternatives considered

- **Ad-hoc ticket ordering**: Relying on the authored order in the spec file. Trade-off: Prevents safe concurrency when non-adjacent tickets are independent, and fails to prevent out-of-order execution when tickets are interdependent.
- **External DAG workflow engines (e.g. Airflow / Prefect)**: Ruled out to preserve zero runtime dependencies (`CON-002`) and ensure lightweight zero-setup operation.

## Cross-cutting concerns

- **Lock Safety**: Swarm mutating commands must acquire the project harness advisory lock.
- **Multiplexer Limits**: `--max-parallel` bounds simultaneous Herdr workspaces and tmux windows to prevent resource exhaustion.
- **Reconciliation Integrity**: Only reconcile into parent if subagent tests and `tenx validate` succeed.

## Validation

- `python3 tests/smoke_test.py`: Verify DAG wave computation, cycle rejection, dry-run output, and MCP tools.
- `tenx validate`: Zero errors and zero warnings.

## Tickets

- `SPC-033-T1`: Implement DAG graph resolution, cycle detection, and wave partitioning [FR-001, FR-002, FR-003] [in_progress]
- `SPC-033-T2`: Implement swarm coordinator engine with wave dispatch and cascade reconciliation [FR-004, FR-005] [todo]
- `SPC-033-T3`: Expose CLI commands, MCP tools, and verify automated smoke tests [FR-006, SC-001, SC-002, SC-003] [todo]
