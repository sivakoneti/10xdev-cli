---
id: SPC-012
type: spec
title: Priority tiers (P0/P1/P2)
status: complete
epic: EPC-007
created: 2026-08-25
updated: 2026-08-25
priority: P0
tickets:
  - id: SPC-012-T1
    title: priority field + set/new/list wiring
    status: done
  - id: SPC-012-T2
    title: priority-aware ordering in tenx next
    status: done
  - id: SPC-012-T3
    title: priority in context packet + priority-format rule
    status: done
  - id: SPC-012-T4
    title: README + smoke checks
    status: done
---

## Summary

Add an optional business priority tier (`P0`/`P1`/`P2`) to epics and specs so
a human can say "this matters most" and have `tenx next` surface it first.
The caller who benefits is any human steering a fleet of agents: today the
queue is ordered only by harness health, so an urgent feature cannot jump the
line.

## Context and scope

tenx's `next` loop orders by action type (fix errors > reconcile drift >
review > implement > spec out). That is correct for harness health but has no
notion of business urgency. Priority-tier systems (P0/P1/P2 buckets) are a
proven way to manage many agents. Scope: a settable, inheritable priority
field that refines ordering within the "do the work" buckets. Out of scope:
changing the harness-health-first ordering.

## Goals / non-goals

Goals:
- `tenx set <ID> priority P0` (validated, case-insensitive) and
  `tenx new ... --priority P0`.
- `tenx next` orders P0 ahead of P1/P2/unset within review/implement/spec
  buckets and shows the tier.
- Specs inherit their epic's priority when they have none.
- `tenx list` and the context packet expose priority.
- A `priority-format` warning for bad hand-edited values.

Non-goals:
- Letting priority override harness-health actions (errors/drift stay first).
- More than three tiers, numeric scores, or per-ticket priority.

## Design

`artifacts.py` gains `PRIORITIES`, an `Artifact.priority` property, and
`effective_priority(artifact, harness)` (spec falls back to its epic).
`cli.py` adds `priority` to `SETTABLE_FIELDS`, normalizes case before the
allowed-value check, and wires `--priority` into `tenx new` and a tier column
into `tenx list`. `nextup.py` tags each work action with its effective tier
and sorts by `(action_priority, business_rank)`. `context.py` emits the tier;
`rules.py` adds `priority-format`. Harness health stays primary because a
broken harness gives every agent wrong context — fix the machine, then build.

## Alternatives considered

Letting P0 jump above drift/errors was considered and rejected: drift is rare
and quick to fix, and a red harness poisons all downstream agent work. A
numeric score field was rejected as over-engineering for three buckets.

## Cross-cutting concerns

Backward compatible: priority is optional, unset means normal order, and no
existing artifact changes shape. Testing: smoke checks cover set/normalize/
reject, new --priority, list, next ordering, context, inheritance, and the
priority-format rule.

## Tickets

- SPC-012-T1 priority field + set/new/list wiring — done
- SPC-012-T2 priority-aware ordering in tenx next — done
- SPC-012-T3 priority in context packet + priority-format rule — done
- SPC-012-T4 README + smoke checks — done

## Validation

- `tenx set SPC-012 priority p0` → normalized to `P0`; `priority P9` exits 2.
- `tenx next` lists the P0 spec before the P1 spec in the same bucket.
- `tenx list spec` and `tenx context --json` show the tier.
- `tenx validate --list-rules` shows `priority-format` (30 rules total).
- `python3 tests/smoke_test.py` and `--module` both pass.

## Open questions

- None.
