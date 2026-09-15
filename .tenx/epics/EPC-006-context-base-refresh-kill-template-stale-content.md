---
id: EPC-006
type: epic
title: Context base refresh — kill template/stale content
status: complete
created: 2026-08-25
updated: 2026-08-25
specs:
  - SPC-010
  - SPC-011
---

## Objective

Eliminate obsolete, unpopulated boilerplate and template drift across the tenx harness context base. Refresh architecture documentation, codify project conventions, and upgrade bundled artifact templates to reflect top-tier engineering planning practices (Amazon Working Backwards, Google Design Docs, and Pragmatic RFCs).

## Key results

- KR1 — DOC-001 refreshed with full module architecture, current command surface, and smoke test coverage.
- KR2 — Core repo conventions codified into dedicated CON artifacts (zero runtime dependencies, smoke test workflow, write-back policy).
- KR3 — Artifact templates in `src/tenx/templates.py` and bundled skills updated with structured OKR/RFC/Design-doc sections.

## Scope

- Harness documentation refresh in `.tenx/docs/DOC-001-architecture-overview.md`.
- Conventions codified in `.tenx/conventions/`.
- Template and skill definitions upgraded in `src/tenx/templates.py`.

## Non-goals

- Altering the core runtime execution engine of tenx.
- Breaking backward compatibility with existing frontmatter YAML schema.

## Milestones

- [x] M1 — Audit context base and refresh DOC-001 and CON artifacts (SPC-010).
- [x] M2 — Upgrade artifact authoring templates and skills for epics, specs, and docs (SPC-011).
