---
id: EPC-007
type: epic
title: "Operational control loop — priority, watchdog, landing discipline"
status: complete
created: 2026-08-25
updated: 2026-08-25
priority: P0
---

## Objective

A solo founder or small team running many AI agents needs to steer them, not
just feed them tasks. Today tenx tells an agent what to build next, but gives
the human no way to say "this is the most important thing" (priority), no
quick answer to "what needs my attention and is it being handled?" (watchdog),
and no shared rulebook for landing work without infinite review loops
(landing discipline). This epic adds that operational control loop so a human
can manage a fleet of agents the way a senior eng manager would.

## Key results

- KR1 — A human can set `P0/P1/P2` on any epic/spec and `tenx next` surfaces
  the higher tier first within the work buckets (verified by smoke check).
- KR2 — `tenx watchdog` ranks the top attention items and reports a handling
  verdict for each (being worked on / unattended / stalled / waiting).
- KR3 — The bundled review and process skills teach a bounded 2-cycle fix
  loop, an evidence gate, and a human landing gate (locked by smoke checks).

## Scope

- Priority tiers: field, set/new/list/next/context wiring, validation rule.
- Watchdog: read-only digest command, MCP tool, protocol step.
- Landing discipline: skill-text guidance in tenx-review and tenx-process.

## Non-goals

- Letting priority override harness-health actions (errors/drift stay first).
- Auto-fixing, auto-assigning owners, or external notifications in watchdog.
- Mechanically enforcing the landing loop in code (it is judgment, taught as
  guidance).

## Milestones

- [x] M1 — Priority tiers live (SPC-012).
- [x] M2 — Watchdog digest live (SPC-013).
- [x] M3 — Landing discipline in skills (SPC-014).
