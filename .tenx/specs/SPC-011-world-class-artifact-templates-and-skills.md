---
id: SPC-011
type: spec
title: World-class artifact templates and skills
status: complete
epic: EPC-006
created: 2026-08-25
updated: 2026-08-25
tickets:
  - id: SPC-011-T1
    title: upgrade spec/epic/doc body templates
    status: done
  - id: SPC-011-T2
    title: upgrade authoring skills to match
    status: done
  - id: SPC-011-T3
    title: smoke checks for template + skill structure
    status: done
---

## Summary

Upgrade tenx's artifact templates and authoring skills to encode how top
engineering orgs actually plan work, so every project tenx bootstraps starts
with world-class structure. Researched primary sources: Google design docs
(Malte Ubl), cross-company RFC structures (Pragmatic Engineer), Google SRE
blameless postmortems, Amazon working-backwards PR/FAQ, and OKRs.

## Context and scope

tenx seeds every new project with epic/spec/convention/doc templates and
bundled authoring skills. Before this change they were thin placeholders.
In scope: the four body templates in templates.py and the matching skills.
Out of scope: validation rule changes (spec still only requires
## Summary + ## Validation, so existing artifacts are unaffected).

## Goals / non-goals

Goals:
- Spec template follows the design-doc shape: context/scope, goals/non-goals,
  design with trade-offs, alternatives considered, cross-cutting concerns.
- Epic template follows OKRs (objective + measurable key results) and
  working-backwards framing (start from the user).
- Doc template offers ADR and blameless-postmortem shapes.
- Authoring skills teach the same structures.

Non-goals:
- Not adding new required-section validation rules (avoids flagging existing
  artifacts).
- Not changing the convention template (already best-practice).

## Design

Edited templates.py body templates (EPIC_BODY, SPEC_BODY, DOC_BODY) and the
tenx-write-epic / tenx-write-spec / tenx-write-doc / tenx-process skills.
Kept ## Summary and ## Validation in the spec so the existing
spec-missing-sections rule stays satisfied. Record WHY: trade-off capture and
alternatives are the highest-leverage parts of a design doc, so they are
first-class sections, not optional.

## Alternatives considered

- Add required-section rules for the new sections: rejected — would flag every
  pre-existing spec and create noise without adding safety.
- Put the guidance only in skills, not templates: rejected — templates are the
  default shape every agent sees; skills alone would be skipped.

## Cross-cutting concerns

Testing: +15 smoke checks assert the new sections render and the skills teach
them. Backward compatibility: existing artifacts untouched; only new artifacts
get the richer shape.

## Tickets

- SPC-011-T1 upgrade spec/epic/doc body templates — done
- SPC-011-T2 upgrade authoring skills to match — done
- SPC-011-T3 smoke checks for template + skill structure — done

## Validation

python3 tests/smoke_test.py (and --module) — all green; fresh-project
`tenx validate` clean on the new templates.

## Open questions

- None yet.
