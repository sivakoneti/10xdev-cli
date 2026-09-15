---
id: SPC-018
type: spec
title: "Docs-sync: changelog command + drift rules"
status: complete
epic: EPC-010
created: 2026-08-25
updated: 2026-08-25
tickets:
  - id: SPC-018-T1
    title: changelog.py module + tenx changelog command (show/add/release)
    status: done
  - id: SPC-018-T2
    title: seed CHANGELOG.md on tenx init / --bootstrap
    status: done
  - id: SPC-018-T3
    title: docs-drift validation rules in RULE_CATALOG
    status: done
  - id: SPC-018-T4
    title: evidence-gate changelog requirement
    status: done
  - id: SPC-018-T5
    title: MCP tool + tenx-docs-sync skill + process-skill step
    status: done
  - id: SPC-018-T6
    title: README/DOC-001 docs + smoke checks
    status: done
---

## Summary

Adds a first-class changelog + docs-drift system so documentation stays in
sync with shipped work. A human or agent runs `tenx changelog add` when they
finish something and `tenx changelog release` when they cut a version; the
validation engine and evidence gate then make a missing/stale changelog a
visible defect. The caller who benefits is anyone reading the project's docs —
they now match reality.

## Context and scope

Research (see memory: tenx docs-sync research) shows drift happens because
code has an enforced merge path while doc updates are a separate manual step
(Augment Code); the fix is to fold the doc update into the enforced path.
Docs-as-code says to lint docs like code in CI (Netlify/Fern); Keep a
Changelog 1.1 defines the file shape and the `[Unreleased]` workflow. tenx
already has a validation engine and an evidence gate, so docs-sync becomes a
validated, gated concern rather than a hope. In scope: the changelog command +
module, init seeding, drift rules, evidence-gate hook, MCP/skill/docs/smoke.

## Goals / non-goals

Goals:
- Keep-a-Changelog-format CHANGELOG.md managed by `tenx changelog`.
- Validation rules that flag missing/malformed changelog and completed work
  with no changelog entry.
- Evidence gate requires a changelog entry before spec/epic completion.
- Every `tenx init` project starts with a seeded CHANGELOG.md.

Non-goals:
- Generic README derived-section regeneration (follow-up epic).
- Prose/style grammar linting.
- Auto-rewriting docs from code diffs.

## Design

New `src/tenx/changelog.py`:
- `changelog_path(root)` → `<root>/CHANGELOG.md`.
- `parse_changelog(text)` → ordered sections; each has a label
  (`Unreleased` or a version) plus `Added/Changed/Deprecated/Removed/Fixed/
  Security` entry lists.
- `seed_changelog(root)` → idempotently create the Keep-a-Changelog header +
  empty `[Unreleased]`.
- `add_entry(root, message, type, ref)` → append under `[Unreleased]/<Type>`.
- `release(root, version)` → rename `[Unreleased]` to `[<version>] - <date>`,
  open a fresh `[Unreleased]`.
- `latest_released_version(root)` / `unreleased_entries(root)` helpers.

`tenx changelog` CLI (in `cli.py`): `show` (default, `--json`), `add "<msg>"
[--type T] [--ref ID]`, `release <version>`. Mutating subcommands take the
project lock (already in `MUTATING_COMMANDS` via `changelog`).

Validation (`rules.py`): `_rule_changelog` adds
`changelog-missing` (warning), `changelog-format` (warning),
`changelog-unreleased-empty` (info), `changelog-version-drift` (info); all
registered in `RULE_CATALOG`.

Evidence gate (`gate.py` `check_evidence_gate`): completing a spec/epic also
requires a `[Unreleased]` changelog entry referencing the artifact. A spec
needs its own id referenced; an epic is satisfied by an entry referencing it
or any of its specs (aggregate work documented via its specs). Skipped when
the project has no CHANGELOG.md (backward compatible).

Follows CON-002 (zero runtime deps) and CON-003 (test/release workflow).
Wins because it reuses the existing lock, validation, and gate machinery
instead of adding a parallel docs system.

## Alternatives considered

- Auto-generate changelog from git log: rejected — Keep a Changelog explicitly
  warns git-log dumps are noise; curated entries are the point.
- A generic README managed-block engine this release: deferred — larger
  surface; changelog gives the biggest sync win first.
- External changelog SaaS: rejected — adds a dependency and breaks the
  zero-dep, offline-tolerant convention.

## Cross-cutting concerns

- Backward compatibility: existing projects without CHANGELOG.md only get a
  warning, never an error; `tenx init` is idempotent.
- Concurrency: changelog mutations run under the existing project lock.
- Testing: new smoke checks for seed/add/release and each drift rule.
- Observability: `tenx changelog --json` for machine consumers.

## Tickets

- [ ] SPC-018-T1 — changelog.py module + tenx changelog command (show/add/release)
- [ ] SPC-018-T2 — seed CHANGELOG.md on tenx init / --bootstrap
- [ ] SPC-018-T3 — docs-drift validation rules in RULE_CATALOG
- [ ] SPC-018-T4 — evidence-gate changelog requirement
- [ ] SPC-018-T5 — MCP tool + tenx-docs-sync skill + process-skill step
- [ ] SPC-018-T6 — README/DOC-001 docs + smoke checks

## Validation

- `tenx changelog add "x" --type added` then `tenx changelog` shows it under
  `[Unreleased]/Added`.
- `tenx changelog release v9.9.9` stamps a dated `[v9.9.9]` and reopens
  `[Unreleased]`.
- `tenx validate` on a project with no CHANGELOG.md reports
  `changelog-missing`; with completed work and empty Unreleased reports
  `changelog-unreleased-empty`.
- `tenx set <ID> status complete` is blocked (without `--force`) when no
  `[Unreleased]` changelog entry references the artifact (an epic is
  satisfied via its specs).
- `python3 tests/smoke_test.py` and `--module` both green.

## Open questions

- None yet.
