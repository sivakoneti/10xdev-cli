---
id: EPC-023
type: epic
title: Swarm and DAG Subagent Dispatch
status: complete
created: 2026-09-15
updated: 2026-09-15
---

## Objective

Autonomous coding agents executing complex software engineering epics encounter specs with multiple tickets that possess inter-ticket dependency constraints. Currently, an operator or agent must dispatch tickets sequentially or manually calculate which tickets are safe to execute concurrently. This epic delivers `tenx swarm`: an automated DAG-based scheduler and parallel dispatcher that calculates the topological execution order from ticket dependency definitions, executes ready tickets concurrently across isolated worktrees and visual multiplexer projections, and reconciles finished tickets before unblocking downstream dependent tickets.

## Key results

- **KR1**: Spec tickets support dependency specifications (`depends_on: [TICKET_ID]`) parsed and topologically sorted with circular dependency detection and error reporting.
- **KR2**: Single command `tenx swarm <SPEC_ID>` schedules, dispatches, and tracks wave-based concurrent execution of independent tickets across supported harnesses (`pi`, `omp`, `prime-agent`, `codex`) and multiplexers (`herdr`, `tmux`).
- **KR3**: Automated wave progression: when all tickets in an execution wave complete and reconcile, dependent tickets in subsequent waves are automatically dispatched without operator intervention.
- **KR4**: 100% test coverage with automated DAG verification in smoke tests and 0 `tenx validate` errors.

## Scope

- Dependency declaration format in spec ticket frontmatter (`depends_on: [...]`).
- DAG construction, cycle detection, and topological wave partitioning algorithms in Python standard library (`src/tenx/dag.py`).
- Swarm orchestration coordinator (`src/tenx/swarm.py`): orchestrating wave dispatches, status polling, and cascade reconciliation via `reconcile_subagent_ticket()`.
- CLI commands: `tenx swarm <SPEC_ID> [--dry-run] [--max-parallel N] [--visual] [--agent AGENT] [--model MODEL] [--json]` and `tenx dag <SPEC_ID> [--json]`.
- MCP tools: `tenx_swarm` and `tenx_dag`.

## Non-goals

- Dynamic runtime re-planning of DAG tickets during active subagent execution (DAG is declared statically in the spec).
- Distributed multi-host swarm execution (all swarms run on the local host machine using local worktrees and multiplexers).
- Arbitrary non-tenx task swarms (only tenx spec tickets are scheduled).

## Milestones

- [x] M1: Ticket dependency graph data model, DAG topological sorting, and cycle detection (`src/tenx/dag.py`).
- [x] M2: Swarm execution engine coordinating wave dispatch, polling, and cascade reconciliation (`src/tenx/swarm.py`).
- [x] M3: CLI subcommands (`tenx swarm`, `tenx dag`), MCP tools (`tenx_swarm`, `tenx_dag`), and automated smoke test validation.
