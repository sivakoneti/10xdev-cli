---
id: EPC-002
type: epic
title: tenx as the daily driver on real projects
status: in_progress
created: 2026-08-24
updated: 2026-08-24
---

## Goal

Make tenx the tool you reach for on every project, not just a demo:
onboarding an existing codebase takes one command, ticket state is visible
where the team already looks (GitHub Issues), and the session-start packet
stays inside a sane token budget while every agent session leaves a trace.

## Milestones

1. M1 — `tenx scan` drafts a codebase-map doc from any existing repo
   (SPC-002). New projects go from zero to briefed in one command.
2. M2 — spec tickets sync to GitHub Issues both ways (SPC-003). Work is
   visible to humans without opening the PM repo; the video's
   "tickets moved to the right column" moment, tracker-native.
3. M3 — context packets respect a token budget and every session-start
   injection is logged (SPC-004). Long-running projects stay cheap to
   boot and auditable.

## Out of scope (for now)

- Linear / other trackers (GitHub first; the sync layer stays pluggable).
- MCP server mode.
- Convention-body enforcement in validate.

## Done means

All three specs complete, smoke tests green, tenx dogfooding itself: this
epic's own tickets were tracked in GitHub Issues via `tenx sync`.
