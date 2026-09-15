---
id: SPC-010
type: spec
title: Context base refresh
status: complete
epic: EPC-006
created: 2026-08-25
updated: 2026-08-25
tickets:
  - id: SPC-010-T1
    title: refresh DOC-001 to current architecture
    status: done
  - id: SPC-010-T2
    title: codify real conventions (CON-002..004)
    status: done
  - id: SPC-010-T3
    title: fill EPC-001 + SPC-001 template bodies
    status: done
  - id: SPC-010-T4
    title: refresh tenx-review skill + smoke check
    status: done
---

## Summary

Audit found template/stale content in the context base itself: DOC-001
misses 6 modules added since v0.5 and quotes a 21-check smoke suite (now
~105); CON-001 is still the seeded boilerplate while the project's real
conventions (zero-deps, smoke-before-commit, release procedure, commit
policy) live only in session memory; EPC-001 and SPC-001 bodies are still
authoring templates; the tenx-review skill predates `tenx review` /
`tenx archive`. An agent onboarding from the context base alone would get
a wrong picture of the codebase and no binding conventions. This spec
refreshes all of it.

## Validation

- DOC-001 lists every module in src/tenx/ and current workflows.
- Conventions codify the actual working rules (CON-002..CON-004).
- EPC-001/SPC-001 bodies describe what was actually delivered.
- tenx-review skill references the review/archive commands.
- tenx validate clean; INDEX.md in sync.
