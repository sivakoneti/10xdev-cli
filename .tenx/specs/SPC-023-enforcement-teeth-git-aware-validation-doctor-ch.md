---
id: SPC-023
type: spec
title: "Enforcement teeth: git-aware validation, doctor checks, blocked status, resync lifecycle"
status: complete
epic: EPC-013
tags:
  - enforcement
  - validate
  - doctor
priority: P0
created: 2026-08-26
updated: 2026-08-26
tickets:
  - id: SPC-023-T1
    title: "doctor: enforcement health checks (git gate, block freshness, mcp, skills)"
    status: done
  - id: SPC-023-T2
    title: validate rule commit-without-writeback (git log vs activity log)
    status: done
  - id: SPC-023-T3
    title: promote completion-drift rules to errors (close direct-edit bypass)
    status: done
  - id: SPC-023-T4
    title: pre-commit staged-change freshness gate (tenx gate commit-check)
    status: done
  - id: SPC-023-T5
    title: "blocked ticket status end-to-end (CLI, MCP, validate, watchdog)"
    status: done
  - id: SPC-023-T6
    title: ticket moves auto-logged to activity log
    status: done
  - id: SPC-023-T7
    title: audit trail for gate escapes (--force / gate block)
    status: done
  - id: SPC-023-T8
    title: "resync lifecycle: update refreshes agent surfaces + staleness rule"
    status: done
  - id: SPC-023-T9
    title: worktree + hook failure-mode hardening
    status: done
  - id: SPC-023-T10
    title: "docs/content refresh (DOC-001, README, skill order, exec brief, capabilities)"
    status: done
  - id: SPC-023-T11
    title: MCP mutating tools acquire harness_lock (parity with CLI main)
    status: done
  - id: SPC-023-T12
    title: "yamlite hardening: zero-indent lists, visible parse failures"
    status: done
  - id: SPC-023-T13
    title: changelog round-trip preserves heading-less entries and sub-bullets
    status: done
  - id: SPC-023-T14
    title: gate changelog check scans all sections; archive requires explicit approval
    status: done
  - id: SPC-023-T15
    title: capabilities catalog fixes + scan manual-additions note + doctor --json
    status: done
  - id: SPC-023-T16
    title: "watchdog: only flag unresolved blocker entries (mirror validate rule)"
    status: done
  - id: SPC-023-T17
    title: "scan: make census top-15 truncation visible in the codebase map"
    status: done
---

## Summary

Audit of 2026-08-26 (3 parallel auditors + inline verification, reports in
/tmp/tenx-review/) proved that skipping the tenx loop has zero observable
consequence: validate/gate/doctor/watchdog read only markdown + the JSONL
activity log, never git; the pre-commit gate (where installed) only runs
`tenx validate`, which cannot see code changes; and the agent-facing surface
rots silently because nothing re-syncs it after upgrades. This spec gives
the harness teeth and stops the rot. Beneficiary: any human whose agents
skip tickets/write-back/validate unless reminded.

## Context and scope

Findings being fixed (severity from the audit): pre-commit gate toothless
even when installed (CRITICAL); validate has no git awareness (CRITICAL);
CLAUDE.md/GEMINI.md stale-block rot with no detection (HIGH); `blocked`
ticket status advertised by 5 surfaces but rejected by the CLI (HIGH);
evidence gate bypassed by direct file edit and silent ticket moves (HIGH);
git gate bypasses via core.hooksPath/--no-verify/worktree-install (HIGH);
doctor presence-only (MEDIUM); no resync lifecycle (MEDIUM); DOC-001/README/
skill/exec-brief drift (MEDIUM). Scope: src/tenx code + shipped templates +
docs in this repo. Not in scope: server-side git hooks (needs a server),
releasing a new version (human decision).

## Goals / non-goals

Goals:
- A skipped write-back becomes observable: `tenx validate` flags recent
  code commits with no activity-log entry; the pre-commit gate can block
  commits of code with no logged work.
- `tenx doctor` reports enforcement rot (missing/stale git gate,
  core.hooksPath override, stale managed blocks, missing .mcp.json/skills)
  with exact fix commands.
- Direct file edit to `status: complete` fails validation (gate no longer
  CLI-only); ticket moves leave a trace; `--force` leaves an audit trail.
- The documented `blocked` ticket workflow works end-to-end.
- `tenx update` refreshes agent instruction files after a CLI upgrade;
  staleness is lintable. Worktree hook install works.
- Shipped docs/templates match reality (DOC-001, README MCP list, skill
  priority order, exec brief gate note, capabilities catalog).

Non-goals:
- Server-side enforcement, CI integration, or verifying evidence truth
  (gate stays presence-based).
- Cutting a release (changes land under [Unreleased]).

## Design

Git awareness enters through two narrow, fault-isolated seams (CON-002:
stdlib only — subprocess git calls, fail-open with a warning when git or
the repo is absent):

1. `rules.py` gains `_rule_commit_writeback` (rule `commit-without-writeback`,
   default warning, param `commit_window_hours`=4): for each git commit in
   the window that touches non-harness files, require an activity entry
   within ±window or a message/ref mentioning the commit hash. Retroactively
   catches untracked commits at the next validate/pre-commit run.
2. `gate.py` gains `commit_check(project_root)` invoked by a new CLI command
   `tenx gate commit-check` and by GIT_HOOK_SCRIPT after validate: if staged
   files include code paths (not only .tenx/, docs, changelog, agent
   instruction files) and no activity entry is newer than the previous
   commit, block with a "log your work" message. Config knob
   `commit_gate: on|warn|off` (default `warn` this release).
3. `RULE_CATALOG` severity changes: `derived-status-drift` (authored-complete
   branch) and `orphan-spec` (complete-with-no-tickets branch) warning→error,
   so hand-edited completions fail validate → fail the git gate.
4. `cmd_doctor` gains an "enforcement" section: git hook present/managed/
   fresh vs GIT_HOOK_SCRIPT, core.hooksPath set, managed-block freshness vs
   AGENT_MD_BLOCK for files that exist, .mcp.json, .claude/skills. Red lines
   print the exact fix command.
5. `blocked` added to TICKET_STATUSES + argparse choices; validate rule text
   already matches; watchdog already handles blocked.
6. `cmd_ticket` appends an activity entry (type progress, ref=spec) on every
   move. `cmd_set --force` and gate blocks append decision entries.
7. Resync: `tenx update` (after successful upgrade) and `tenx hook install`
   refresh managed blocks (install_md_block already replaces marker content);
   new validate rule `agent-surface-stale` (warning) compares on-disk managed
   blocks against the shipped template; `tenx init` default agent scope
   aligned to `all` for instruction files.
8. `hooks.py _find_git_dir` handles worktree `.git` pointer files
   (parse `gitdir:` → common dir); GIT_HOOK_SCRIPT gains a timeout wrapper
   and consistent fail-open warning.
9. Doc/template refresh per audit T2 list.

Why this wins: every fix turns a previously invisible skip into a finding,
warning, or blocked commit, using the existing rule/finding machinery — no
new dependencies, no new state files, fail-open where git is unavailable.

## Alternatives considered

- Block commits on ANY missing ticket move: too noisy for docs-only or
  exploratory work; the staged-code heuristic + warn-default keeps trust.
- Verify evidence truth (run tests in the gate): CON-003 already mandates
  smoke runs; duplicating that in the hook would make commits slow and
  flaky. Presence + retroactive detection is the right layer.
- A daemon/watcher for real-time enforcement: rejected — tenx is
  invoke-time tooling by design; pre-commit + validate is the natural seam.

## Cross-cutting concerns

- Backward compatibility: new rules default to warning; commit_gate defaults
  to `warn`; existing projects keep passing validate. Severity promotions
  (T3) can surface pre-existing hand-edited completions as errors — that is
  the intent; `rules.yaml` can downgrade per project.
- Testing: tests/smoke_test.py extended for every ticket (both modes per
  CON-003).
- Observability: every new enforcement action explains itself in the
  finding/message text with the fix command.

## Tickets

Move tickets through todo -> in_progress -> in_review -> done. Keep the
frontmatter `tickets:` list in sync with this section.

- SPC-023-T1 doctor enforcement health checks
- SPC-023-T2 commit-without-writeback rule
- SPC-023-T3 completion-drift severity promotion
- SPC-023-T4 staged-change freshness gate
- SPC-023-T5 blocked status end-to-end
- SPC-023-T6 ticket moves auto-logged
- SPC-023-T7 escape audit trail
- SPC-023-T8 resync lifecycle + staleness rule
- SPC-023-T9 worktree + hook hardening
- SPC-023-T10 docs/content refresh
- SPC-023-T11 MCP lock parity (worker1 finding 3)
- SPC-023-T12 yamlite hardening (worker1 finding 5)
- SPC-023-T13 changelog round-trip fidelity (worker1 finding 6)
- SPC-023-T14 gate all-sections changelog check + archive approval (worker1 finding 8)
- SPC-023-T15 capabilities/scan/doctor surface fixes (worker1 findings 7, 10)

## Validation

- `python3 tests/smoke_test.py` and `python3 tests/smoke_test.py --module`
  both green (CON-003).
- `tenx validate` 0 errors on this repo after changes.
- Sandbox proof: fresh repo, commit code with no log → gate warns/blocks
  per commit_gate setting; hand-edit status: complete → validate error.
- `tenx doctor` on a repo with the hook deleted prints a red fix line.

## Open questions

- None.
