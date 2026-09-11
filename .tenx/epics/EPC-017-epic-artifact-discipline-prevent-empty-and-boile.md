---
id: EPC-017
type: epic
title: "Epic artifact discipline: prevent empty and boilerplate epics"
status: complete
created: 2026-09-11
updated: 2026-09-11
specs:
  - SPC-027
---

## Objective

Ensure all epic artifacts created in tenx-governed repositories contain genuine, meaningful objectives, scope, and key results rather than empty placeholder templates. AI coding agents frequently scaffold epics via `tenx new epic` and elaborate on child specs while leaving the parent epic file as raw template boilerplate. This epic introduces validation checks, required section auditing, boilerplate detection, and gate enforcement for epics.

## Key results

- KR1 — `tenx validate` detects unpopulated or boilerplate-only epic files with a new rule (`epic-missing-sections` / `epic-template-unfilled`).
- KR2 — An epic marked `in_review` or `complete` containing unfilled placeholder text or missing required sections triggers a validation error and blocks the evidence gate.
- KR3 — Existing and new test suites verify detection across empty, placeholder, and fully authored epics with 0 regressions in smoke tests.

## Scope

- Validation engine updates in `src/tenx/rules.py` checking epic bodies for required sections (`## Objective`) and boilerplate template placeholders.
- Evidence gate enforcement in `src/tenx/gate.py` preventing completion of unpopulated or boilerplate-only epics.
- Unit and smoke test coverage in `tests/smoke_test.py`.

## Non-goals

- Forcing heavy bureaucracy onto short/rapid epics; minimal well-formed objectives and key results or overviews suffice.
- Restricting human edits or requiring AI-generated text over human-authored text.

## Milestones

- [ ] M1 — Implement epic section and boilerplate validation rules in `src/tenx/rules.py`.
- [ ] M2 — Wire gate checks in `src/tenx/gate.py` to block completion of boilerplate epics.
- [ ] M3 — Add smoke test assertions and verify clean validation across the harness.
