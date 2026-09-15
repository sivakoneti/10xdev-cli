---
id: EPC-013
type: epic
title: Enforcement teeth + agent-surface consistency — make skipping the loop detectable
status: complete
tags:
  - enforcement
  - agent-surface
priority: P0
created: 2026-08-26
updated: 2026-08-26
specs:
  - SPC-023
---

## Objective

Transform tenx from an advisory guidance framework into an enforceable SDLC engine. Ensure agents cannot bypass the governed loop, skip ticket tracking, or leave broken drift behind by adding git-aware validation, doctor health checks, blocked ticket states, and write-back enforcement.

## Key results

- KR1 — Git pre-commit enforcement (`tenx gate commit-check`) verifies that staged code files have an activity write-back.
- KR2 — `tenx doctor` provides a single diagnostic audit of environment, hooks, and harness health.
- KR3 — `blocked` status added to artifact and ticket lifecycles with watchdog surfacing.
- KR4 — 100% pass across smoke tests and clean validation.

## Scope

- Git index inspection and timestamp checking in `src/tenx/gate.py`.
- Health diagnostics and fix recommendations in `src/tenx/cli.py` (`cmd_doctor`).
- Advisory locking across CLI and MCP surfaces to prevent concurrent agent race conditions.

## Non-goals

- Blocking non-code operational tasks or emergency human overrides.
- Replacing external CI pipelines.

## Milestones

- [x] M1 — Git-aware commit check and write-back enforcement (SPC-023).
- [x] M2 — Tenx doctor command and health checks (SPC-023).
- [x] M3 — Per-project advisory file locking for fleet safety (SPC-023).
