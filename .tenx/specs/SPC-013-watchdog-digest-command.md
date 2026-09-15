---
id: SPC-013
type: spec
title: Watchdog digest command
status: complete
epic: EPC-007
created: 2026-08-25
updated: 2026-08-25
priority: P1
tickets:
  - id: SPC-013-T1
    title: watchdog module (compute + render)
    status: done
  - id: SPC-013-T2
    title: tenx watchdog CLI command + flags
    status: done
  - id: SPC-013-T3
    title: MCP tool + operating-protocol mention
    status: done
  - id: SPC-013-T4
    title: README + smoke checks
    status: done
---

## Summary

Add `tenx watchdog`, a pulse-check digest that scans the whole harness and
surfaces the top few things needing attention, each cross-referenced with
recent activity to answer the question that actually matters: is this being
handled? The caller who benefits is a human running many agents who cannot
read every artifact — they get a ranked triage list instead of raw state.

## Context and scope

Modeled on the "Watchdog" playbook for managing fleets of agents: surface the
top problems and, for each, say whether it is fixed / being fixed / unattended.
tenx already has the raw signals (validation, drift, statuses, activity log)
but nothing that combines them into "what needs my eyes". Scope: a read-only
digest command + MCP tool. Out of scope: auto-fixing anything.

## Goals / non-goals

Goals:
- Rank attention items by severity: critical (validation errors), high
  (drift, blocked specs/tickets, open blockers), medium (in_review waiting,
  in_progress gone quiet).
- For each item report a handling verdict (being worked on / unattended /
  stalled / gone quiet / waiting on review) using recent activity.
- `--json` for machines, `--window N` and `--top N` knobs.
- MCP tool `tenx_watchdog` and an operating-protocol step.

Non-goals:
- Mutating the harness, auto-assigning owners, or notifying externally.

## Design

New `watchdog.py`: `compute_watchdog()` gathers signals from `validate()` and
the activity log, maps each artifact ref to its most-recent activity within a
window (default 7 days), and emits ranked items; `render_watchdog()` prints
the human digest. `cli.py` adds `cmd_watchdog` + subparser; `mcp.py`
registers `tenx_watchdog`; `context.py` protocol tells agents to run it.
Read-only by construction — it never writes.

## Alternatives considered

Reusing `tenx status` was considered but rejected: status is a state dump,
not a triage ranking with handling verdicts. A separate command keeps the
self-correcting `next` loop and the human-facing watchdog distinct.

## Cross-cutting concerns

Read-only and offline-safe (no network). Testing: smoke checks cover clean
run, JSON shape, blocked/in_review/quiet detection, handling verdicts, and
MCP registration.

## Tickets

- SPC-013-T1 watchdog module (compute + render) — done
- SPC-013-T2 tenx watchdog CLI command + flags — done
- SPC-013-T3 MCP tool + operating-protocol mention — done
- SPC-013-T4 README + smoke checks — done

## Validation

- `tenx watchdog` on a clean project reports nothing needs attention.
- On a seeded project it flags a blocked P0 spec (high), an in_review spec
  (medium), and a quiet in_progress spec, each with a handling verdict.
- `tenx watchdog --json` returns `items`/`counts`/`window_days`.
- `python3 tests/smoke_test.py` and `--module` both pass.

## Open questions

- None.
