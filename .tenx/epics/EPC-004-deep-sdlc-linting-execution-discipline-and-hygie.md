---
id: EPC-004
type: epic
title: deep SDLC linting — execution discipline and hygiene rules
status: in_progress
created: 2026-08-24
updated: 2026-08-24
---

## Goal

Move toward the video's "hundreds of rules" direction: tenx validate
should catch process drift before it compounds. This epic adds rules
that enforce execution discipline (specs must be executable, tickets
must be traceable) and hygiene (conventions must have substance,
config must be coherent, write-back must be disciplined), plus a
discoverable rule catalog so agents can learn what gets linted.

## Milestones

1. M1 — execution discipline rules live (SPC-007).
2. M2 — hygiene rules + `tenx validate --list-rules` catalog (SPC-008).

## Out of scope

- Conventions as executable rule definitions (future epic).
- Auto-fix for the new rules (report-only for now; --fix stays
  convention-index-only).

## Done means

Rule count roughly doubles, every new rule has a smoke check, the
catalog is printable, README documents the full catalog, and tenx's
own harness validates clean under the new rules.
