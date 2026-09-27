---
id: SPC-037
type: spec
title: "Capability catalog parity for configured dispatch and the delegation trigger"
status: draft
epic: EPC-027
priority: P2
created: 2026-09-27
updated: 2026-09-27
tickets:
  - id: SPC-037-T1
    title: "Teach the capability catalog about configured projection and the delegation trigger (FR-001)"
    status: todo
---

## Summary

`tenx capabilities` is the catalog an agent reads when it asks "what can this
harness do, and when". Since SPC-036 added proactive delegation triggers, a
`dispatch` config section, `--no-visual`, and `TENX_DISPATCH_VISUAL`, the
catalog is stale: it tells an agent that dispatch is a command to type, when
dispatch is now also something `tenx next` proposes and something a project
can configure. An agent that only reads the catalog cannot discover the new
behavior. This spec brings the catalog in line with the shipped surface.

## Context and scope

`src/tenx/capabilities.py` holds the catalog entries. The dispatch and swarm
entries (`capabilities.py:87-90`, `107-110`) still advertise only
`[--agent A] [--dry-run]` and `[--visual]`, and neither entry mentions that
`tenx next` surfaces the delegation command, that `dispatch.visual` in
`.tenx/config.yaml` makes projection the project default, or that
`--no-visual` overrides it. In scope: the catalog entries and their
`when`/`what` text. Out of scope: any change to dispatch behavior itself,
which landed in SPC-036.

## Goals / non-goals

Goals:
- An agent reading only `tenx capabilities` learns that delegation is
  surfaced automatically by `tenx next`, not only typed by hand.
- The catalog advertises the full flag surface that exists today, including
  the config section and the environment override.

Non-goals:
- Changing what `tenx dispatch` or `tenx swarm` do.
- Adding new capabilities beyond the SPC-036 surface.
- Rewriting the whole catalog or changing its group structure.

## Requirements

- FR-001: The capability catalog MUST advertise the full dispatch flag
  surface that exists, and MUST state that a `dispatch` section in
  `.tenx/config.yaml` plus `TENX_DISPATCH_VISUAL` can make visual projection
  the default, overridable per call with `--no-visual`.

## Success criteria

- SC-001: `tenx capabilities` output for `dispatch` and `swarm` lists
  `--no-visual` and mentions the `dispatch` config section, and
  `tenx capabilities --json` exposes the same text.

## Design

Edit the two entries in the `track` group of `COMMANDS` in
`src/tenx/capabilities.py`: extend `usage` to the real flag set and extend
`when` with the trigger and configuration facts. One-line-per-entry prose
only, matching the existing `{name, surface, group, usage, what, when}`
shape so the markdown and JSON renderers need no change. Applies CON-001
(follow the existing entry shape) and CON-002 (no new dependency).

## Alternatives considered

Adding a separate "delegation trigger" capability entry. Rejected: `tenx
next` is already a catalog entry, and duplicating dispatch across two
entries would leave the two to drift. One entry per command, complete text.

## Cross-cutting concerns

- **Backward compatibility:** `usage` and `when` are display strings; no
  machine consumer parses them, so extending the text is additive.
- **Testing:** a smoke check asserting the catalog mentions `--no-visual` and
  the config section in both markdown and JSON rendering.

## Tickets

- [ ] SPC-037-T1: Teach the capability catalog about configured projection and the delegation trigger (FR-001)

## Validation

- FR-001: Given `tenx capabilities`, When the `dispatch` and `swarm` entries
  render, Then both mention `--no-visual` and the `dispatch` config section,
  and `tenx capabilities --json` carries the same text.
- Suite: `python3 tests/smoke_test.py` and `python3 tests/smoke_test.py --module`
  both pass; `tenx validate` reports 0 errors.

## Open questions

- None.
