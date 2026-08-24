---
id: DOC-001
type: doc
title: Architecture overview
status: draft
created: '2026-08-24'
updated: '2026-08-24'
---

## Purpose

Orientation for any agent (or human) working on tenx itself. Read this before
touching `src/tenx/`.

## Components

    src/tenx/
      cli.py         argparse entry point; one cmd_* function per subcommand
      discovery.py   project root discovery (.tenx/ -> .git -> cwd; TENX_ROOT wins)
      artifacts.py   artifact model: frontmatter parse, load/create/update, derived status
      yamlite.py     zero-dep YAML-subset parser/writer (PyYAML used when importable)
      templates.py   artifact body templates + bundled skill texts
      rules.py       validation engine (linting for the SDLC) + convention index rebuild
      context.py     context packet builder (operator/agent modes, md/json render)
      nextup.py      prioritized work-queue derivation for `tenx next`
      activity.py    append-only JSONL activity log
      hooks.py       SessionStart hook install (claude settings.json) + managed md blocks
      skills.py      skill installation (.claude/skills/<name>/SKILL.md layout)

## Key invariants

- Zero runtime dependencies. Python 3.10+ stdlib only; PyYAML is an optional
  accelerator. Never add a hard dependency without a spec.
- All read commands support --json. The CLI is dual-facing: humans get
  markdown, agents get markdown or JSON.
- Artifact ids are PREFIX-NNN (EPC/SPC/CON/DOC), unique per harness.
- Derived state never writes itself: `tenx validate` reports drift between
  authored status and ticket-derived status; humans/agents reconcile it.
- Hook installs must stay idempotent (managed blocks between tenx:begin/end).

## How to run/test

    uv tool install --editable . --force   # installs tenx + 10x executables
    python3 tests/smoke_test.py            # 21-check end-to-end smoke test
    python3 tests/smoke_test.py --module   # same, against src/ without install

## Design origin

Implements the meta-harness / context-as-code pattern described by the 10X
team (Alex Lieberman, Dan) on the David Ondrej podcast (Aug 2026):
https://www.youtube.com/watch?v=QBfXiWvM0qc
