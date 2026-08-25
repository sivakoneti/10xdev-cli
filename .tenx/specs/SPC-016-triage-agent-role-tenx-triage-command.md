---
id: SPC-016
type: spec
title: Triage agent role + tenx triage command
status: complete
epic: EPC-008
priority: P0
created: 2026-08-25
updated: 2026-08-25
tickets:
  - id: SPC-016-T1
    title: triage.py compute+render over watchdog
    status: done
  - id: SPC-016-T2
    title: cmd_triage + parser + MCP tool
    status: done
  - id: SPC-016-T3
    title: tenx-triage agent-role skill + README + smoke
    status: done
---

## Summary

Add a triage layer over `tenx watchdog`: `tenx triage` classifies the current
attention items into act-now / watch / healthy, picks the single most
important human escalation, and prints a short report a person can act on.
`--json` serves machines. It is exposed as a CLI command, an MCP tool
(`tenx_triage`), and an installable `tenx-triage` agent-role skill so any
runtime can run a "Triage Officer" loop. The beneficiary is a human overseeing
a fleet of agents who wants one ranked answer to "what needs me?".

## Context and scope

SPC-013 shipped `tenx watchdog` (ranked items + handling verdicts). Triage is
the opinionated step above it: group, escalate, and phrase it for a human.
Scope is read-only reporting; triage never mutates harness state.

## Goals / non-goals

Goals:
- `tenx triage` -> act-now / watch / healthy + one escalation, human + `--json`.
- MCP tool `tenx_triage`; installable `tenx-triage` agent-role skill.
- Offline-safe (builds on watchdog, which is read-only).

Non-goals:
- Auto-fixing or mutating anything; scheduling/cron (the skill describes the
  loop, the runtime schedules it).

## Design

New `src/tenx/triage.py`: `compute_triage(...)` calls `compute_watchdog`,
splits items (critical, or high+unattended/stalled -> act-now; rest -> watch),
counts healthy in-progress, and selects the top act-now item needing a human
decision as `escalation`. `render_triage` formats the report. `cmd_triage` +
parser (`--json`, `--window`, `--top`), MCP tool, and a `tenx-triage` skill
persona + loop. This wins because it reuses watchdog entirely and adds only a
thin opinionated layer.

## Alternatives considered

- Only enhance watchdog output: rejected — a dedicated command + agent role is
  the demonstrable "wow" and gives machines a stable contract.
- Have triage auto-apply fixes: rejected — read-only keeps it safe to run 24/7.

## Cross-cutting concerns

- Read-only and offline-safe; no new storage. Adding an MCP tool requires
  updating the smoke "mcp lists N tools" count.

## Tickets

- SPC-016-T1 triage.py compute+render over watchdog
- SPC-016-T2 cmd_triage + parser + MCP tool
- SPC-016-T3 tenx-triage agent-role skill + README + smoke

## Validation

- `tenx triage` prints act-now/watch/healthy + an escalation line; `--json`
  returns typed keys.
- MCP `tools/list` includes `tenx_triage`; `tenx skills install` writes a
  `tenx-triage` skill describing the loop.
- Offline smoke checks pass; full suite green.

## Open questions

- None.
