---
id: EPC-010
type: epic
title: Docs-sync — changelog discipline + drift detection
status: complete
created: 2026-08-25
updated: 2026-08-25
---

## Objective

Every project using tenx ships features faster than its docs can keep up, so
READMEs, changelogs, and architecture notes silently drift from the code. The
user — a human operator or a fresh agent session — then reads stale docs and
makes wrong decisions. This epic makes documentation sync an enforced,
automated property of the harness instead of a manual chore, so the people and
agents relying on the context base always read what the project actually does.

## Key results

- KR1 — `tenx changelog add/release` maintains a Keep-a-Changelog file with
  one command; cutting a release stamps `[Unreleased]` into a dated version.
- KR2 — `tenx validate` flags docs drift: missing/malformed changelog, and
  completed work with no changelog entry (`changelog-unreleased-empty`).
- KR3 — the evidence gate refuses to mark a spec/epic complete when shipped
  work has no changelog entry (overridable with `--force`).
- KR4 — `tenx init`/`--bootstrap` seed a CHANGELOG.md, so every new project
  starts with the discipline in place.
- KR5 — 10xdev dogfoods the system: a real backfilled CHANGELOG.md, and the
  v0.16.0 release is cut with `tenx changelog release`.

## Scope

- A `tenx changelog` command (show / add / release) backed by a new
  `src/tenx/changelog.py` module.
- Docs-drift validation rules added to `RULE_CATALOG` + a `_rule_changelog`.
- Changelog seeding on `tenx init` / `--bootstrap`.
- Evidence-gate integration: require a changelog entry as completion evidence.
- MCP tool + bundled `tenx-docs-sync` skill + process-skill step.
- README/DOC-001 documentation + smoke checks.

## Non-goals

- A generic README derived-section regeneration engine (rule table / command
  reference auto-generated from source of truth) — that is a follow-up epic.
- Prose/style linting (Vale/TextLint-style grammar checks).
- Auto-editing docs from code diffs (self-updating docs agents) — tenx will
  surface drift and let an agent draft the fix, not rewrite prose itself.
- Publishing changelogs to external channels (webhooks, release-note SaaS).

## Milestones

- [x] M1 — changelog module + `tenx changelog` command + init seeding
- [ ] M2 — docs-drift validation rules in RULE_CATALOG
- [ ] M3 — evidence-gate changelog requirement
- [ ] M4 — MCP tool + skill + docs + smoke checks
- [ ] M5 — dogfood: backfill 10xdev CHANGELOG, cut v0.16.0 with it
