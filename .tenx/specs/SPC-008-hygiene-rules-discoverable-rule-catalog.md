---
id: SPC-008
type: spec
title: hygiene rules + discoverable rule catalog
status: complete
epic: EPC-004
created: 2026-08-24
updated: 2026-08-24
tickets:
  - id: SPC-008-T1
    title: convention-empty-body + id-filename-mismatch
    status: done
  - id: SPC-008-T2
    title: config-code-root
    status: done
  - id: SPC-008-T3
    title: blocker-unresolved + log-progress-no-ref
    status: done
  - id: SPC-008-T4
    title: RULE_CATALOG + validate --list-rules
    status: done
  - id: SPC-008-T5
    title: README rule catalog + smoke checks
    status: done
---

## Summary

Hygiene rules plus a first-class rule catalog.

New rules:

1. `convention-empty-body` (warning): convention body (text after
   frontmatter, headings stripped) shorter than `min_convention_chars`
   (default 40). A convention with no substance cannot be followed.
2. `id-filename-mismatch` (warning): artifact filename does not start
   with its id. Manual renames break human navigation.
3. `config-code-root` (error): config declares a `code_root` but the
   path does not exist (discovery would silently fall back to the
   harness host).
4. `blocker-unresolved` (info): a `blocker` activity entry within
   `blocker_days` (default 14) with no later progress/decision entry
   carrying the same ref.
5. `log-progress-no-ref` (info): a `progress` activity entry with no
   ref — write-back discipline per the 10X process.

Catalog:

- `RULE_CATALOG: dict[str, tuple[severity, description]]` in rules.py
  covering every rule id (old + new). Single source of truth.
- `tenx validate --list-rules` prints the catalog (id, default
  severity, description) and exits 0 without linting. `--json`
  variant.

## Tickets

- SPC-008-T1 convention-empty-body + id-filename-mismatch
- SPC-008-T2 config-code-root
- SPC-008-T3 blocker-unresolved + log-progress-no-ref
- SPC-008-T4 RULE_CATALOG + tenx validate --list-rules
- SPC-008-T5 README rule catalog + smoke checks

## Validation

Smoke per rule as SPC-007; --list-rules output includes every rule id
that validate can emit; README table matches RULE_CATALOG.

## Open questions

- None.
