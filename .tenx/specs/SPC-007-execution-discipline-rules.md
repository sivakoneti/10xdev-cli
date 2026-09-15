---
id: SPC-007
type: spec
title: execution discipline rules
status: complete
epic: EPC-004
created: 2026-08-24
updated: 2026-08-24
tickets:
  - id: SPC-007-T1
    title: orphan-spec extension + spec-missing-sections
    status: done
  - id: SPC-007-T2
    title: ticket-id-prefix + ticket-title-missing
    status: done
  - id: SPC-007-T3
    title: archived-epic-active-specs
    status: done
  - id: SPC-007-T4
    title: smoke checks for SPC-007 rules
    status: done
---

## Summary

Rules that keep specs executable and tickets traceable. All report-only
(no auto-fix). Each rule honors rules.yaml disable/severity/params.

New/extended rules:

1. `orphan-spec` (extended): also fire when a spec is `in_progress`
   with zero tickets — you cannot execute a spec without tickets.
2. `spec-missing-sections` (warning): spec body lacks required
   headings. Default required: `## Summary`, `## Validation`.
   Param: `spec_sections` (comma list).
3. `ticket-id-prefix` (warning): ticket id must start with
   `<SPEC-ID>-T` (e.g. SPC-002-T1). This is a cross-feature invariant:
   GitHub sync markers `[SPC-xxx-Tn]` depend on it.
4. `ticket-title-missing` (info): ticket without a title.
5. `archived-epic-active-specs` (warning): epic archived but one or
   more of its specs are not archived.

## Tickets

- SPC-007-T1 orphan-spec extension + spec-missing-sections
- SPC-007-T2 ticket-id-prefix + ticket-title-missing
- SPC-007-T3 archived-epic-active-specs
- SPC-007-T4 smoke checks for all SPC-007 rules

## Validation

Smoke: seed each violation in a scratch harness, assert the finding
appears with correct rule id and severity; assert clean harness stays
clean. tenx's own repo must validate clean after the change.

## Open questions

- None.
