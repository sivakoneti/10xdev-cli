---
id: SPC-002
type: spec
title: tenx scan — bootstrap a codebase map from any existing repo
status: complete
epic: EPC-002
created: 2026-08-24
updated: 2026-08-24
tickets:
  - id: SPC-002-T1
    title: scan.py walker + stack/marker detection
    status: done
  - id: SPC-002-T2
    title: tenx scan CLI with --json
    status: done
  - id: SPC-002-T3
    title: tenx scan --write DOC upsert + activity log
    status: done
  - id: SPC-002-T4
    title: smoke tests for scan
    status: done
---

## Summary

`tenx scan` walks the governed code repo and produces a codebase map:
stack markers, entry points, test setup, CI, existing agent instruction
files, and a top-level directory census. `tenx scan --write` turns that
into a DOC artifact so a fresh project goes from zero to briefed in one
command. This is the "works on any project" onboarding story.

## Architecture

New module `src/tenx/scan.py`, pure stdlib:

- `scan_tree(root, code_root) -> dict` — bounded walk (max depth 3 for
  census, full depth for marker files). Skip set: `.git`, `node_modules`,
  `.venv`, `venv`, `dist`, `build`, `__pycache__`, `.next`, `target`,
  `.tenx`. Honors nothing else (no .gitignore parsing in v1 — keep it
  simple and predictable).
- Stack detection by marker files: `pyproject.toml`/`setup.py` (python),
  `package.json` (node; read `name`, packageManager hint), `go.mod`,
  `Cargo.toml`, `pom.xml`/`build.gradle(.kts)`, `Gemfile`,
  `composer.json`, `requirements.txt`.
- Entry-point hints: files named main/index/app/cli at depth <= 2, plus
  `[project.scripts]` / `bin` keys when cheaply readable.
- Test/CI/agent-file detection: `tests|test|__tests__|spec` dirs,
  `pytest.ini`/`vitest`/`jest` config, `.github/workflows/*`, and any of
  the adapter instruction files (AGENTS.md, CLAUDE.md, GEMINI.md,
  .cursor/rules, .clinerules, .windsurfrules, copilot-instructions).
- `tenx scan` prints the human summary; `--json` prints the dict.
- `tenx scan --write` upserts `.tenx/docs/DOC-xxx-codebase-map.md`
  (found by tag `codebase-map`): regenerate body, bump `updated`,
  append a `progress` activity entry. Never clobbers a doc that has the
  tag but was renamed.

Contracts: no new dependencies; DOC id allocation reuses
`artifacts.next_id`; frontmatter written via `yamlite.dump_frontmatter`.
Convention CON-001 applies (ids, frontmatter discipline).

## Tickets

- SPC-002-T1 scan.py walker + stack/marker detection (pure, no writes)
- SPC-002-T2 `tenx scan` CLI with `--json`
- SPC-002-T3 `tenx scan --write` DOC upsert + activity log
- SPC-002-T4 smoke tests: scratch repo with known markers

## Validation

- `python3 tests/smoke_test.py` gains scan checks (detection of a python
  + node mixed scratch repo, --json shape, --write creates DOC-002 with
  tag, second --write updates not duplicates).
- Manual: `tenx scan` on the tenx repo itself reads sensibly.

## Open questions

- None.
