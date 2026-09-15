---
id: DOC-001
type: doc
title: Architecture overview
status: complete
created: 2026-08-24
updated: 2026-08-25
---

## Purpose

Orientation for any agent (or human) working on tenx itself. Read this before
touching `src/tenx/`.

## Components

    src/tenx/
      __init__.py    package docstring + __version__ (bump WITH pyproject.toml)
      __main__.py    `python -m tenx` entry
      cli.py         argparse entry point; one cmd_* function per subcommand
      discovery.py   project root discovery (.tenx/ -> .git -> cwd; TENX_ROOT
                     wins); .tenxlink for standalone PM repos; code_root()
      artifacts.py   artifact model: frontmatter parse, load/create/update,
                     derived status from tickets
      yamlite.py     zero-dep YAML-subset parser/writer (PyYAML used when
                     importable)
      templates.py   artifact body templates, config/harness-README templates,
                     bundled skill texts
      rules.py       validation engine: RULE_CATALOG (38 rules) + _rule_*
                     functions + convention index rebuild; `tenx validate
                     --list-rules` prints the catalog; git-aware rules
                     (commit-without-writeback, agent-surface-stale);
                     spec-discipline rules (clarify-markers-open,
                     requirement-uncovered, requirement-orphan)
      context.py     context packet builder (operator/agent modes, md/json,
                     --budget truncation) + the operating PROTOCOL text
      nextup.py      prioritized work-queue derivation for `tenx next`
      watchdog.py    `tenx watchdog`: ranked attention items + are-they-handled
                     verdicts from recent activity
      triage.py      `tenx triage`: act-now/watch/healthy classification + the
                     single top human escalation
      gate.py        enforced evidence gate (clean validate + done tickets +
                     linked evidence + changelog entry across all sections)
                     on spec/epic -> complete, plus commit_check: the
                     staged-change freshness gate behind `tenx gate
                     commit-check` (commit_gate: on|warn|off)
      activity.py    append-only JSONL activity log + throttled session entries
      execbrief.py   `tenx exec` autonomous execution brief builder
      adapters.py    data-driven adapter registry (~29 agent harnesses:
                     instruction files, hook kind, binary detection) +
                     agent aliases (dsh->deepseek-harness, agy, prime)
      hooks.py       hook/skill install engines: claude settings.json hook,
                     managed md blocks (tenx:begin/end, hardened HARD-RULES
                     mandate), cursor/cline/kiro managed files, bootstrap
                     snippet, DSH agent-preset generator (persona-mandated
                     tenx loop), find_stale_surfaces (drift detector shared
                     by doctor + validate), and the git pre-commit gate
                     (runs `tenx validate` + `tenx gate commit-check`,
                     timeout-wrapped and fail-open on tenx failure;
                     worktree-aware: installs into the common hooks dir)
      skills.py      skill installation (.claude/skills/<name>/SKILL.md layout)
      scan.py        `tenx scan`: stack/test/CI/agent-file census of the code
                     repo; --write upserts a codebase-map DOC
      sync.py        `tenx sync push|pull`: spec tickets <-> GitHub Issues
                     ([SPC-xxx-Tn] markers, label, token chain incl.
                     ~/.git-credentials)
      mcp.py         `tenx mcp`: stdio MCP JSON-RPC server exposing 15 tools;
                     mutating tools take the same harness lock as the CLI;
                     `tenx mcp install` writes managed .mcp.json
      capabilities.py capability catalog (every command/tool + when-to-use)
                     behind `tenx capabilities`, the tenx_capabilities MCP
                     tool, and a context-packet pointer
      update.py      `tenx update [--check]`: self-update (GitHub Releases API
                     -> branch pyproject.toml fallback; offline-tolerant;
                     uv/pipx upgrade detection)
      changelog.py   `tenx changelog`: Keep-a-Changelog CHANGELOG.md discipline
                     (show/add/release) + docs-drift helpers for the rules/gate
      converge.py    `tenx converge`: deterministic spec-completion convergence
                     (FR-### requirements vs tickets; --append adds missing
                     tickets; append-only, no-op when clean)
      locking.py     per-project advisory lock (.tenx/.lock) + atomic_write_text;
                     serializes mutating commands so concurrent agents are safe

## Key invariants

- Zero runtime dependencies. Python 3.10+ stdlib only; PyYAML is an optional
  accelerator. Never add a hard dependency without a spec (CON-002).
- All read commands support --json. The CLI is dual-facing: humans get
  markdown, agents get markdown or JSON.
- Artifact ids are PREFIX-NNN (EPC/SPC/CON/DOC), unique per harness; the
  filename must start with the id.
- Derived state never writes itself: `tenx validate` reports drift between
  authored status and ticket-derived status; humans/agents reconcile it.
- Hook installs stay idempotent (managed blocks between tenx:begin/end).
- Nothing printed on stdout except command output: MCP speaks JSON-RPC on
  stdout, and --json output must stay parseable. Notices go to stderr.
- Network-touching commands (sync, update) fail clean with a message and a
  non-traceback exit; an update CHECK never fails a session (exits 0).

## How to run/test

    uv tool install --force .              # installs tenx + 10x executables
    python3 tests/smoke_test.py            # ~177-check end-to-end smoke suite
    python3 tests/smoke_test.py --module   # same, against src/ without install
    tenx validate                          # lint the harness itself

Run the smoke suite (both modes) before every commit (CON-003).

## Release & update workflow

1. Bump version in BOTH `pyproject.toml` and `src/tenx/__init__.py`.
2. Run the smoke suite; `tenx validate`.
3. Commit, `git push`, tag `vX.Y.Z`, push the tag.
4. Create the GitHub Release for the tag (releases API is the primary
   update channel; branch pyproject.toml is the fallback).
5. `tenx sync push` to mirror new tickets/issues.
6. `uv tool install --force .` locally.

Existing installs discover all of this via `tenx update --check`, which
agents are instructed to run at session start (operating protocol step 1).

## Design origin

Implements the meta-harness / context-as-code pattern described by the 10X
team on modern agentic workflows:
https://www.youtube.com/watch?v=QBfXiWvM0qc
