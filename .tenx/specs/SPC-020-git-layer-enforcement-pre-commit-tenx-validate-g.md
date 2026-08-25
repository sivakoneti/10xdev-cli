---
id: SPC-020
type: spec
title: Git-layer enforcement — pre-commit tenx validate gate
status: in_progress
epic: EPC-011
created: 2026-08-25
updated: 2026-08-25
tickets:
  - id: SPC-020-T1
    title: tenx hook install --git writes .git/hooks/pre-commit
    status: done
  - id: SPC-020-T2
    title: "pre-commit runs tenx validate, blocks on errors only"
    status: done
  - id: SPC-020-T3
    title: init auto-installs the git hook when .git exists
    status: done
  - id: SPC-020-T4
    title: "smoke: hook installed, executable, blocks on error"
    status: done
---

## Summary

Add the one enforcement layer that works on EVERY harness identically: a git
pre-commit hook. Every agent on every harness must commit through git to land
work, so a pre-commit hook that runs `tenx validate` and blocks on errors is
enforced below the agent — non-bypassable (short of `git commit --no-verify`)
and harness-agnostic. This is the universal backstop that turns "the agent
chose to skip tenx" into "the commit is rejected."

## Context and scope

Instruction files and personas raise voluntary compliance but a confused or
pressured model can still deviate. The git layer cannot be skipped by the
agent's discretion. This spec adds `tenx hook install --git` and wires it into
`tenx init` when a git repo is present.

## Goals / non-goals

Goal: pre-commit hook runs `tenx validate`, blocks the commit on ERRORS only
(warnings/info pass), prints the offending rules, and is bypassable via the
standard `git commit --no-verify`. Non-goal: a server-side/CI gate (follow-up).

## Design

- `hooks.py`: `install_git_hook(root)` writes `.git/hooks/pre-commit`
  (chmod +x) that runs `tenx validate` and exits non-zero if the error count
  is > 0. Idempotent; managed marker so re-init refreshes it.
- `cli.py`: `tenx hook install --git` flag; `cmd_init` calls it when
  `.git/` exists (unless `--no-hooks`).
- The hook resolves the `tenx` binary defensively (PATH, then `python -m`).

## Alternatives considered

pre-push instead of pre-commit (rejected: later feedback). Block on warnings
(rejected: too noisy, would frustrate and get bypassed). CI-only gate
(rejected for now: doesn't stop the local commit; kept as follow-up).

## Validation

- `tenx hook install --git` creates an executable `.git/hooks/pre-commit`.
- With a clean project the hook exits 0; with an induced error it exits non-0.
- `tenx init` in a git repo installs the hook automatically.
