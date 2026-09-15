---
id: SPC-025
type: spec
title: "Spec artifact discipline: structured specs, clarify markers, coverage, converge"
status: complete
epic: EPC-015
created: 2026-08-26
updated: 2026-08-26
tickets:
  - id: SPC-025-T1
    title: "Structured spec template: FR-### requirements, SC-### success criteria, clarify markers"
    status: done
  - id: SPC-025-T2
    title: "validate rule clarify-markers-open: no unresolved ambiguity once work starts"
    status: done
  - id: SPC-025-T3
    title: "coverage rules: every FR-### needs a ticket; every ticket needs a requirement"
    status: done
  - id: SPC-025-T4
    title: "tenx converge: deterministic spec-completion report + --append tickets"
    status: done
  - id: SPC-025-T5
    title: "docs + protocol integration: exec brief, HARNESS_README, DOC-001, changelog"
    status: done
---

## Summary

Adopt the four artifact-discipline ideas from github/spec-kit that survive
contact with tenx's mechanical-enforcement DNA: structured requirements in
specs, explicit ambiguity markers, requirement coverage checking, and a
converge step before completion. Agents and humans get specs that are
checkable instead of prose that is only hopeful. Source analysis:
`/tmp/speckit-review/COMPARISON.md`.

## Context and scope

spec-kit (github/spec-kit, v1.0.0) enforces spec quality at prompt level
only: templates tell the LLM what to write, nothing verifies it. tenx can
mechanically verify the same discipline, which is strictly stronger. This
spec adopts the artifact ideas and wires them into `tenx validate`,
`tenx converge`, and the evidence-gate flow.

In scope: spec template structure, two-to-three new validate rules, one new
command, docs/protocol updates, smoke coverage.

## Goals / non-goals

Goals:
- New specs carry numbered functional requirements (`FR-###`) and measurable
  success criteria (`SC-###`), plus acceptance scenarios in Validation.
- Ambiguity is explicit: `[NEEDS CLARIFICATION: question]` markers, and
  validate blocks starting/finishing work while markers remain.
- Coverage is checkable: every `FR-###` must be referenced by a ticket, and
  every ticket should map to a requirement.
- `tenx converge <SPC>` reports which requirements are satisfied (done
  tickets / evidence) and which are open, and can append missing tickets.
- All checks are deterministic, stdlib-only (CON-002), and backward
  compatible: existing specs without FR-### markers are untouched.

Non-goals:
- User-story prioritization (P1/P2/P3 stories): tenx specs are already work
  slices with tickets; stories belong at epic level if anywhere.
- LLM-driven semantic convergence: tenx has no model access; converge is
  deterministic FR/ticket/evidence mapping, and the agent does the semantic
  read using converge output as its checklist.
- Constitution ratification/amendment semantics for conventions (future epic).
- Reviewer-owned checklists as gate artifacts (future epic).
- Preset/extension/bundle ecosystem, YAML workflows (future epic if ever).

## Design

### T1 — Structured spec template (`src/tenx/templates.py`)

Extend `SPEC_BODY`, keeping every existing section (all current specs stay
valid). Insert two new sections after "Goals / non-goals":

- `## Requirements` — numbered `FR-###` lines, each one testable MUST.
  Template instructs: mark unknowns as
  `FR-###: ... [NEEDS CLARIFICATION: question]` instead of guessing.
- `## Success criteria` — numbered `SC-###` measurable outcomes.

`## Validation` gains guidance: acceptance scenarios as Given/When/Then
lines tied to FR ids. `_rule_spec_sections` is NOT changed for old specs;
new sections are enforced only via marker-driven rules below.

### T2 — Rule `clarify-markers-open` (`src/tenx/rules.py`)

Scan spec bodies for `[NEEDS CLARIFICATION`. Any marker in a spec whose
status is not `draft` -> error ("resolve or record the answer before work
continues"). Draft specs may carry markers freely. RULE_CATALOG entry;
count 35 -> 36 (+1 in T3 -> 37).

### T3 — Coverage rules (`src/tenx/rules.py`)

Marker-driven, so legacy specs are immune:

- `requirement-uncovered` (warning): an `FR-###` id appears in the spec body
  but in no ticket title of that spec. Tickets reference requirements by
  embedding the id, e.g. `"[FR-002] retry with backoff"`.
- `requirement-orphan` (info): a ticket title carries `[FR-###]` that does
  not exist in the spec body (typo / deleted requirement).

Only fire when the spec body contains at least one `FR-###` marker.

### T4 — `tenx converge` (`src/tenx/converge.py`, `src/tenx/cli.py`)

`tenx converge <SPC-ID> [--json] [--append]`:

1. Parse spec: FR ids, SC ids, tickets (id/title/status), evidence refs,
   activity-log entries referencing the spec.
2. Build the requirement inventory: each FR is satisfied when a ticket that
   references it is `done`, or evidence/log text references the FR id.
3. Report: per-FR status (satisfied / open / no-ticket), SC count, ticket
   state summary, converge verdict (CONVERGED when every FR satisfied and
   no open clarify markers).
4. `--append`: for every FR with no ticket, append a todo ticket
   `"[FR-###] <requirement text trimmed>"` to the spec frontmatter and body
   Tickets section. Append-only: never renumber, reorder, or delete existing
   tickets; byte-for-byte no-op when clean. Exit 1 if not converged
   (agent protocol: run before `tenx set <SPC> status complete`).
5. `--json` for agent consumption; register in capabilities catalog.

### T5 — Docs + protocol integration

- `HARNESS_README` (templates.py) + exec brief: add converge step to the
  completion flow ("run `tenx converge`, resolve gaps, then complete").
- DOC-001 rule count refresh; README validate-rule mention.
- Changelog entries per ticket via `tenx changelog add`.

## Alternatives considered

- Copy spec-kit's spec template wholesale (user stories, P1/P2/P3): rejected
  — tenx specs are technical work slices, not product PRDs; tickets are the
  unit of slicing. FR/SC + markers capture the value without the mismatch.
- Semantic converge via shelling out to an agent CLI: rejected — breaks
  CON-002 (zero deps) and determinism; deterministic mapping + agent read is
  the tenx-shaped answer.
- Enforce Requirements/Success-criteria sections on all specs: rejected —
  would error on 18 existing specs; marker-driven rules are opt-in by usage.

## Cross-cutting concerns

- Backward compatibility: all new rules marker-driven; old specs unaffected.
- Testing: smoke checks per ticket (CON-003), both modes.
- Zero deps: stdlib only (CON-002).

## Tickets

Move tickets through todo -> in_progress -> in_review -> done. Keep the
frontmatter `tickets:` list in sync with this section.

- SPC-025-T1 structured spec template
- SPC-025-T2 clarify-markers-open rule
- SPC-025-T3 coverage rules
- SPC-025-T4 tenx converge command
- SPC-025-T5 docs + protocol integration

## Validation

- `python3 tests/smoke_test.py` and `python3 tests/smoke_test.py --module`
  both green (CON-003).
- Sandbox: new spec from template contains FR/SC sections; validate errors
  on `[NEEDS CLARIFICATION]` in non-draft spec; coverage warning appears for
  uncovered FR and clears after ticket references it; `tenx converge`
  reports open FRs, `--append` adds tickets, second run is no-op and
  CONVERGED after tickets done.
- `tenx validate` clean in this repo after the change.

## Open questions

- None yet.
