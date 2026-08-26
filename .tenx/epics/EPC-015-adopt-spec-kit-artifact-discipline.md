---
id: EPC-015
type: epic
title: Adopt spec-kit artifact discipline
status: complete
created: 2026-08-26
updated: 2026-08-26
---

## Objective

Make tenx specs checkable instead of hopeful. github/spec-kit showed that
structured artifacts (numbered requirements, explicit ambiguity markers,
coverage tables, converge loops) measurably raise spec quality — but it can
only ask the LLM nicely. tenx already verifies process mechanically; this
epic extends that verification into the content of specs themselves, so
agents produce requirements that can be covered, converged, and proven.

## Key results

- KR1 — New specs created via `tenx new spec` carry FR-###/SC-### structure
  and clarify-marker guidance by default.
- KR2 — `tenx validate` mechanically rejects non-draft specs that still
  contain unresolved `[NEEDS CLARIFICATION]` markers.
- KR3 — Requirement coverage is reported: every FR-### maps to a ticket and
  vice versa; `tenx converge` gives a deterministic converged/not-converged
  verdict per spec.

## Scope

- Spec template structure, clarify + coverage validate rules, `tenx converge`
  command, docs/protocol integration (SPC-025).

## Non-goals

- Constitution ratification semantics, reviewer-owned checklists,
  extension/preset ecosystem, YAML workflows — tracked as future ideas in
  /tmp/speckit-review/COMPARISON.md, not this epic.

## Milestones

- [x] M1 — comparative analysis of github/spec-kit (done: /tmp/speckit-review/COMPARISON.md)
- [x] M2 — SPC-025 shipped (template + rules + converge + docs)
