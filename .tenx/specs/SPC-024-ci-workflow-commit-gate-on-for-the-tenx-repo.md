---
id: SPC-024
type: spec
title: CI workflow + commit_gate on for the tenx repo
status: complete
epic: EPC-014
created: 2026-08-26
updated: 2026-08-26
tickets:
  - id: SPC-024-T1
    title: "GitHub Actions CI: smoke suite (both modes) + validate on push/PR, py 3.10/3.12/3.13"
    status: done
  - id: SPC-024-T2
    title: "flip commit_gate to on in this repo's config (keep warn default for new projects)"
    status: done
---

## Summary

What this spec builds and why, in two or three sentences. Name the user or
caller who benefits.

## Context and scope

Objective background: the landscape this is built in and what is in scope.
Keep it succinct; link deeper detail rather than restating it.

## Goals / non-goals

Goals:
- What this spec must achieve.

Non-goals:
- Things that could be goals but are explicitly not.

## Design

The approach and its key trade-offs: components, files touched, data flow,
contracts changed. Link the conventions (CON-xxx) that apply. Record WHY
this design wins given the goals, not just WHAT it is.

## Alternatives considered

Other designs that would have worked and the trade-off that ruled each out.
If the solution is obvious with no real trade-off, say so in one line.

## Cross-cutting concerns

Security, privacy, observability, testing, backward compatibility — how each
is affected and addressed. Delete any line that does not apply.

## Tickets

Move tickets through todo -> in_progress -> in_review -> done. Keep the
frontmatter `tickets:` list in sync with this section.

## Validation

Exact commands, tests, and manual checks that prove the spec complete — the
definition of done.

## Open questions

- None yet.
