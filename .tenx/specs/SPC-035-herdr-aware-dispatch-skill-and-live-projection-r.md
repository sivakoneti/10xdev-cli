---
id: SPC-035
type: spec
title: Herdr-aware dispatch skill and live projection reliability
status: complete
epic: EPC-025
created: 2026-09-25
updated: 2026-09-25
tickets:
  - id: SPC-035-T1
    title: "[FR-001, FR-005] Make tenx-dispatch require the global Herdr protocol"
    status: done
  - id: SPC-035-T2
    title: "[FR-002, FR-003] Verify Herdr agent startup and receipt handling"
    status: done
  - id: SPC-035-T3
    title: "[FR-004, FR-006] Harden lifecycle supervision and regression coverage"
    status: done
  - id: SPC-035-T4
    title: "[FR-001, FR-002, FR-003, FR-004, FR-005] Validate, document, and record evidence"
    status: done
---

## Summary

Supervisors currently receive a `tenx-dispatch` skill that documents visual Herdr dispatch but does not require loading the authoritative Herdr skill before controlling a session. The live Herdr path also treats optional launch commands as successful even when the agent is not started, and it uses an invalid pane-run fallback shape. This spec makes the dispatch process Herdr-aware and observable end to end.

## Context and scope

The current implementation in `src/tenx/dispatch.py` creates a Herdr workspace, parses its JSON, sends a command to the returned pane, and returns `dispatched` without checking that the pane accepted the command or that Herdr recognized the expected agent. The bundled skill in `src/tenx/templates.py` and `.claude/skills/tenx-dispatch/SKILL.md` omits the global Herdr protocol. This spec updates the skill contract and the Herdr launch path, with focused smoke tests. CON-002 remains binding: no runtime dependency is added.

## Goals / non-goals

Goals:
- Require supervisors to load and follow `skill://herdr` before Herdr control, including `HERDR_ENV=1` verification, CLI discovery, stable IDs, no-focus background work, and blocked-state inspection.
- Make the dispatch skill self-contained enough for agents to perform the complete Herdr sequence: create an isolated worker location, start the requested agent, prompt it, wait/read output, and report IDs.
- Detect and report Herdr workspace creation, agent startup, command submission, and JSON/CLI failures.
- Preserve headless and tmux behavior where it is correct.

Non-goals:
- Replacing `tenx dispatch` with direct ad-hoc Herdr commands in the supervisor.
- Automatically approving interactive agent dialogs or treating `idle` as completion without inspecting the receipt.
- Adding a new multiplexer protocol or a daemon.

## Requirements

- FR-001: The bundled `tenx-dispatch` skill MUST instruct supervisors to load the global Herdr skill before any Herdr-backed dispatch and MUST state the mandatory Herdr safety and lifecycle rules.
- FR-002: Herdr visual dispatch MUST use the installed Herdr CLI and returned workspace/pane IDs, and MUST report a failure when workspace creation or agent startup does not succeed.
- FR-003: Herdr visual dispatch MUST preserve the worker worktree as the pane cwd and MUST return stable workspace and pane identifiers in its receipt.
- FR-004: Herdr lifecycle supervision MUST use the documented settled states (`idle`, `done`, or `blocked`) and MUST not treat a missing target or an unparsed response as successful completion.
- FR-005: The CLI, MCP surface, bundled skill, installed skill, and changelog MUST describe the same Herdr dispatch behavior.
- FR-006: Regression tests MUST exercise skill content and mocked Herdr success/failure paths without requiring a live Herdr server.

## Success criteria

- SC-001: `tenx skills install` and a direct `tenx dispatch ... --visual --multiplexer herdr --dry-run` show Herdr-first guidance and a valid plan.
- SC-002: A mocked successful Herdr launch returns a receipt with workspace and pane IDs; mocked CLI/JSON/startup failures return non-success status with actionable stderr.
- SC-003: `python3 tests/smoke_test.py` and `python3 tests/smoke_test.py --module` pass.
- SC-004: `tenx validate` reports 0 errors and 0 warnings.

## Design

The dispatch skill will link to the global Herdr skill and include its non-negotiable operational contract: verify `HERDR_ENV=1`; learn syntax from `herdr --help` and relevant command groups; preserve caller context; use `--no-focus`; parse IDs from JSON; start agents in an available shell pane; prompt with `--wait`; inspect `blocked` before input; and read output before deciding. The skill will explicitly forbid running bare `herdr` for discovery and will distinguish workspace/tab/pane/agent primitives.

The Python path will add a small Herdr launch helper around the existing official CLI. It will validate the create response, invoke `herdr agent start` when the target pane is available, prompt the named agent, and return the resulting identifiers. Because direct `agent start` needs a recognized pane and the current projection creates a shell root pane, the helper will use Herdr's agent surface rather than blindly sending an agent executable as shell text. The helper will surface CLI stderr and non-JSON output. Existing generic projection planning remains for dry-runs and tmux; only the Herdr live path changes.

Lifecycle checks will remain in the multiplexer module but will use Herdr CLI/API state and expose failure instead of a bare boolean when the target cannot be inspected. This keeps the change scoped and preserves zero dependencies. CON-001, CON-002, CON-003, and CON-004 apply.

## Alternatives considered

- Keep direct `pane send-text`/`pane run` because it avoids agent identity setup. Rejected: it bypasses Herdr's readiness and lifecycle guarantees and currently reports success even when launch fails.
- Embed the entire Herdr skill in Python. Rejected: it duplicates a global runtime contract and will drift; the dispatch skill should link to and summarize it.
- Make Herdr launch asynchronous in the CLI. Rejected for this scope: the receipt must report whether startup succeeded before returning.

## Cross-cutting concerns

Security: never auto-answer blocked dialogs; use explicit user approval for those. Privacy: preserve the existing scoped brief and avoid copying full transcripts. Observability: return stable IDs and actionable command errors. Testing: use mocked subprocesses for deterministic unit-like smoke coverage plus a live, non-destructive Herdr smoke check. Backward compatibility: headless and tmux paths remain unchanged; Herdr launches now fail loudly.

## Tickets

Move tickets through todo -> in_progress -> in_review -> done. Keep the frontmatter `tickets:` list in sync with this section.

- `SPC-035-T1`: [FR-001, FR-005] Make `tenx-dispatch` skill require and summarize the global Herdr protocol across bundled and installed surfaces.
- `SPC-035-T2`: [FR-002, FR-003] Replace blind Herdr shell launch with verified Herdr agent startup and stable receipt handling.
- `SPC-035-T3`: [FR-004, FR-006] Harden lifecycle/error handling and add mocked Herdr regression coverage.
- `SPC-035-T4`: [FR-001, FR-002, FR-003, FR-004, FR-005] Run live and smoke validation, update the changelog, and record evidence.

## Validation

- `python3 tests/smoke_test.py` — all checks pass in installed-CLI mode.
- `python3 tests/smoke_test.py --module` — all checks pass in source-tree mode.
- Run a live `tenx dispatch <SPEC> <TICKET> --agent omp --visual --multiplexer herdr` in the active Herdr session with a disposable ticket/worktree; confirm the receipt includes workspace/pane/agent IDs and the agent becomes interactive-ready. Reconcile/abort the disposable worktree after inspection.
- `tenx validate` — reports 0 errors and 0 warnings.

## Open questions

- None.
