---
id: SPC-027
type: spec
title: Validate epic body completeness and prevent unpopulated boilerplate in epics
status: complete
epic: EPC-017
owner: sivakoneti
created: 2026-09-11
updated: 2026-09-11
tickets:
  - id: SPC-027-T1
    title: "[FR-001,FR-002] Implement epic body and template validation rules in src/tenx/rules.py"
    status: done
  - id: SPC-027-T2
    title: "[FR-003] Enforce epic completeness in evidence gate src/tenx/gate.py"
    status: done
  - id: SPC-027-T3
    title: "[FR-004] Backfill EPC-013 and EPC-014 bodies in 10xdev-cli"
    status: done
  - id: SPC-027-T4
    title: "[SC-001,SC-002] Add unit and smoke test coverage for epic validation and gates in tests/smoke_test.py"
    status: done
  - id: SPC-027-T5
    title: "[SC-003] Verify test suites pass, docs sync, and tenx validate clean"
    status: done
---

## Summary

When agents scaffold epics using `tenx new epic`, the epic file is seeded with template boilerplate (`## Objective`, `One paragraph: the outcome...`, `KR1 —`, `M1 —`). Agents routinely flesh out child specs and complete work, but forget to author the epic body. This spec adds validation rules and evidence gate checks requiring epics to be populated with real content before entering review or completion.

## Context and scope

- `tenx validate` currently verifies spec sections (`_rule_spec_sections`), convention bodies (`_rule_convention_body`), and clarify markers (`_rule_clarify_markers`), but performs no content or section checks on epic bodies.
- The evidence gate (`check_evidence_gate` in `src/tenx/gate.py`) enforces ticket completion on specs, but does not verify that an epic being completed has an authored body.
- This creates situations where projects have fully completed epics that contain only the original unedited template boilerplate.

## Goals / non-goals

Goals:
- Add `_rule_epic_body` in `src/tenx/rules.py` checking:
  1. `epic-missing-sections`: Required sections (`## Objective` or `## Overview`) must be present.
  2. `epic-template-unfilled`: Unfilled template boilerplate markers (e.g. `"One paragraph: the outcome this epic delivers"`, `"- KR1 —"`, `"- [ ] M1 —"`) are flagged.
  3. Emit a warning during `draft`/`in_progress`, and an error if status is `in_review` or `complete`.
- Add epic body check in `src/tenx/gate.py` (`check_evidence_gate`) so an epic with template boilerplate or empty body cannot be marked `complete` without `--force`.
- Provide end-to-end smoke test coverage.

Non-goals:
- Imposing strict stylistic or word-count minimums beyond detecting raw templates or empty bodies.
- Regulating external project docs outside `.tenx/epics/`.

## Requirements

- FR-001: The system MUST check epic bodies in `tenx validate` for required sections (`## Objective` or `## Overview`) and emit `epic-missing-sections`.
- FR-002: The system MUST check epic bodies in `tenx validate` for default template boilerplate strings (`One paragraph: the outcome this epic delivers`, `reduce p95 latency to <200ms`, `KR1 —`, `M1 —`) and emit `epic-template-unfilled`. In `in_review` or `complete` status, this MUST be an `error`; in `draft` or `in_progress`, it MUST be a `warning`.
- FR-003: The evidence gate (`src/tenx/gate.py`) MUST block transition of an epic to `complete` if the epic body is missing or contains unfilled boilerplate markers, unless bypassed with `--force`.
- FR-004: All existing epics within `10xdev-cli` MUST satisfy the new epic validation rules.

## Success criteria

- SC-001: Running `tenx validate` on an epic with default boilerplate produces `epic-template-unfilled`.
- SC-002: Running `tenx set <EPIC-ID> status complete` is blocked by the evidence gate when the epic contains boilerplate.
- SC-003: All smoke tests (`tests/smoke_test.py`) pass in both CLI and `--module` modes.
- SC-004: `tenx validate` passes with 0 errors across the harness.

## Design

1. In `src/tenx/rules.py`:
   - Add rules `epic-missing-sections` and `epic-template-unfilled` to `RULE_CATALOG`.
   - Implement `_rule_epic_body(harness: Harness, rs: RuleSet)`.
   - Inspect each epic: check presence of `## Objective` or `## Overview`.
   - Inspect epic body for known template substrings from `EPIC_BODY`.
   - If found, assign severity: `error` if `e.status in ("in_review", "complete")` else `warning`.
2. In `src/tenx/gate.py`:
   - In `check_evidence_gate`, if `art.type == "epic"`, verify that the epic has no `epic-template-unfilled` or `epic-missing-sections` findings.
3. In `tests/smoke_test.py`:
   - Add smoke assertions for creating an epic, validating it in draft (warning), attempting complete (gate blocked / error), filling it in, and verifying clean validation.

## Tickets

- SPC-027-T1: Implement epic body and template validation rules in `src/tenx/rules.py`
- SPC-027-T2: Enforce epic completeness in evidence gate `src/tenx/gate.py`
- SPC-027-T3: Backfill EPC-013 and EPC-014 bodies in 10xdev-cli
- SPC-027-T4: Add unit and smoke test coverage for epic validation and gates in `tests/smoke_test.py`
- SPC-027-T5: Verify test suites pass, docs sync, and tenx validate clean

## Validation

- FR-001/SC-001: Create test epic with default template; verify `tenx validate` emits warning/error.
- FR-002/FR-003/SC-002: Attempt `tenx set <EPIC-ID> status complete` on boilerplate epic; verify evidence gate blocks with clear message.
- FR-004/SC-003/SC-004: Run `python3 tests/smoke_test.py` and `python3 tests/smoke_test.py --module`; verify 100% pass and `tenx validate` clean.
