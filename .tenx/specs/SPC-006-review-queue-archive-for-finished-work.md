---
id: SPC-006
type: spec
title: review queue + archive for finished work
status: draft
epic: EPC-003
created: 2026-08-24
updated: 2026-08-24
tickets:
  - id: SPC-006-T1
    title: tenx review + --json
    status: todo
  - id: SPC-006-T2
    title: tenx archive with open-ticket guard
    status: todo
  - id: SPC-006-T3
    title: smoke checks for review/archive
    status: todo
---

## Summary

Two small daily-loop commands: `tenx review` lists everything awaiting
review (specs in_review + tickets in_review, with days-in-state), and
`tenx archive <EPC-ID>` retires a finished epic and its specs.

## Architecture

- `tenx review [--json]`: scans specs for status in_review and tickets
  with status in_review; prints spec id, title, days since `updated`,
  and the in_review tickets inside each. Empty queue prints a clean
  "nothing awaits review" line. No new state; read-only.
- `tenx archive <EPC-ID> [--yes]`: sets the epic status to `archived`
  and every spec of that epic to `archived`, logs a `decision`
  activity entry. Refuses if any spec has open tickets (todo /
  in_progress / in_review) unless `--yes`. `archived` is already in
  the status vocabulary, so validate needs no change; `tenx next`
  already ignores non-queued statuses.

## Tickets

- SPC-006-T1 tenx review (+ --json)
- SPC-006-T2 tenx archive with open-ticket guard
- SPC-006-T3 smoke checks for both

## Validation

- Smoke: seed an in_review spec + ticket, assert review lists them;
  archive refuses with open tickets, succeeds with --yes, validate
  stays clean.

## Open questions

- None.
