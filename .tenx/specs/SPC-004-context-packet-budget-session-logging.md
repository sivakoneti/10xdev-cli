---
id: SPC-004
type: spec
title: context packet budget + session logging
status: draft
epic: EPC-002
created: 2026-08-24
updated: 2026-08-24
tickets:
  - id: SPC-004-T1
    title: apply_budget pure function
    status: todo
  - id: SPC-004-T2
    title: --budget flag on context/hook emit
    status: todo
  - id: SPC-004-T3
    title: throttled session logging on hook emit
    status: todo
---

## Summary

Keep the session-start packet cheap on large projects and make every
injection auditable: `--budget N` truncates the packet deterministically,
and `tenx hook emit` records a throttled `session` activity entry so the
history shows when agents actually woke up with context.

## Architecture

- `context.py`: section priority order (fixed): identity/config ->
  next-up -> conventions index -> artifact summaries -> recent activity.
  `apply_budget(packet_sections, budget_chars)` keeps sections whole
  while they fit; the first section that overflows is cut with a
  `... [truncated: over budget, run tenx show <ID> for full text]`
  marker; later sections are dropped entirely and listed by name in a
  trailing `omitted:` note. Default budget: none (current behavior);
  `--budget` is opt-in. Agent-mode default stays unbounded so existing
  hooks don't change behavior.
- `activity.py`: `log_session(harness, source)` appends
  `{type: session, summary: "session-start packet emitted"}` with a
  throttle: skip if the most recent `session` entry is < 60 min old.
  `tenx hook emit` calls it; `--no-log` opts out. `tenx context` does
  NOT log (only the hook path does).
- validate: `log-quiet` rule counts session entries as activity (they
  are real activity).

## Tickets

- SPC-004-T1 apply_budget pure function + unit checks in smoke
- SPC-004-T2 `--budget` flag on context/hook emit
- SPC-004-T3 throttled session logging on hook emit (+ --no-log)

## Validation

- Smoke: budget=500 packet shorter than budget+marker overhead and ends
  with omitted note; two hook emits within a minute produce one session
  entry; `tenx history` shows it.

## Open questions

- None.
