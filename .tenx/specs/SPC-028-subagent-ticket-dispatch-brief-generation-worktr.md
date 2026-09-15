---
id: SPC-028
type: spec
title: Subagent Ticket Dispatch — brief generation, worktree runner, and universal skill
status: complete
epic: EPC-018
created: 2026-09-14
updated: 2026-09-14
tickets:
  - id: SPC-028-T1
    title: "[FR-001] Implement tenx ticket-brief CLI command and MCP tool"
    status: done
  - id: SPC-028-T2
    title: "[FR-002, FR-003, FR-004] Implement tenx dispatch runner with git worktree isolation and adapter execution"
    status: done
  - id: SPC-028-T3
    title: "[FR-005] Author universal tenx-dispatch skill and wire into agent presets"
    status: done
  - id: SPC-028-T4
    title: "[FR-001, FR-002, FR-004] Add comprehensive smoke test suite coverage and dogfood ticket dispatch"
    status: done
---

## Summary

This spec delivers an end-to-end subagent ticket delegation system in tenx. It enables any agent (Pi, Codex, Prime Agent, DSH/DSH Web, Grok, Claude) to extract a scoped, low-token ticket brief, spawn an isolated subagent worker in a git worktree, supervise execution, and enforce the tenx evidence gate before landing changes.

## Context and scope

When coding agents tackle complex multi-ticket epics, accumulating exploratory context, tool outputs, and test logs inflates the conversation transcript, leading to token exhaustion, degraded reasoning, and convention drift. While harnesses offer varying degrees of subagent support (or none, like Codex and Prime Agent), tenx can provide a universal mechanism: slicing ticket context cleanly into a self-contained brief, executing workers in git worktrees, and returning a structured receipt to the supervisor.

## Goals / non-goals

Goals:
- Generate a zero-bloat ticket brief (`tenx ticket-brief <SPEC> <TICKET>`) containing only the ticket goal, spec context, relevant conventions, and acceptance test commands.
- Provide a headless worktree dispatcher (`tenx dispatch <SPEC> <TICKET> [--agent <name>]`) using Python standard library only (CON-002).
- Support headless dispatch across key adapters: Codex (`codex exec`), Prime Agent (`prime run`), Pi (`pi -p`), Claude Code (`claude -p`), Grok (`grok --headless`), and fallback generic bash runner.
- Provide prompt generation for in-band harnesses like DSH Web (`@deepseek-ai/dsh-tool-subagent`).
- Author a universal skill (`tenx-dispatch`) guiding any agent on when and how to delegate tickets and verify evidence.
- Full compliance with zero runtime dependencies (CON-002) and write-back policies (CON-004).

Non-goals:
- Building a complex background GUI or terminal multiplexer daemon.
- Replacing the human landing gate; subagents produce worktree branches and receipts for supervisor and human review.

## Requirements

- FR-001: The system MUST provide `tenx ticket-brief <SPEC> <TICKET>` (and MCP tool `tenx_ticket_brief`) returning a markdown brief containing the ticket description, parent spec requirements, active conventions index, and definition-of-done commands.
- FR-002: The system MUST provide `tenx dispatch <SPEC> <TICKET> [--agent <name>] [--dry-run]` to create an isolated git worktree at `.tenx/worktrees/<TICKET>`, write the task brief, launch the worker agent, and collect the receipt.
- FR-003: The system MUST support adapter-specific launch command rendering for `codex`, `prime-agent`, `pi`, `claude`, `grok`, and `dsh`.
- FR-004: The system MUST enforce CON-002: zero external dependencies, implemented with Python 3.10+ standard library (`subprocess`, `shutil`, `pathlib`, etc.).
- FR-005: The system MUST ship a universal skill `tenx-dispatch` explaining the delegation lifecycle, context preservation, and evidence validation.

## Success criteria

- SC-001: `tenx ticket-brief` produces valid markdown for any existing spec ticket and errors cleanly if the spec or ticket does not exist.
- SC-002: `tenx dispatch --dry-run` displays the exact worktree path, command invocation, and ticket brief without modifying filesystem or git state.
- SC-003: `tests/smoke_test.py` passes both standard and `--module` modes with complete test assertions for brief generation and dispatch commands.
- SC-004: Running `tenx validate` passes with 0 errors and 0 warnings.

## Design

1. **`src/tenx/dispatch.py`**:
   - `build_ticket_brief(project_root, spec_id, ticket_id)`: reads the spec, extracts the ticket title/body, finds requirements referenced, gathers conventions, and outputs a clean markdown packet.
   - `resolve_agent_command(agent_id, worktree_dir, brief_path)`: renders the appropriate CLI invocation for the harness.
   - `dispatch_ticket(...)`: handles git worktree setup, execution, stdout/stderr capture, exit status handling, and receipt generation.
2. **CLI & MCP wiring**:
   - Register `ticket-brief` and `dispatch` subcommands in `cli.py`.
   - Register `tenx_ticket_brief` and `tenx_dispatch` in `mcp.py`.
   - Update `capabilities.py` catalog.
3. **Skill & Presets**:
   - Create `.claude/skills/tenx-dispatch/SKILL.md` (and native skills directory).
   - Update DSH Cordis preset and hook definitions if needed.

## Alternatives considered

- Relying solely on harness-specific tools (e.g. Pi's `pi-subagents` or Claude's `Agent`): Ruled out because Codex, Prime Agent, and standard terminal setups have no such tool.
- Launching long-running tmux daemons: Ruled out because it requires external dependencies (tmux/zellij) not present in every container or CI environment, violating CON-002 portability.

## Cross-cutting concerns

- **Security**: Worktree commands execute locally with current user privileges. Dry-run mode allows inspection prior to execution.
- **Portability (CON-002)**: Only standard library modules used. Git operations gracefully fail if git is missing or repo is dirty.
- **Testing**: Smoke test suite in `tests/smoke_test.py` validates both CLI and module invocations.

## Tickets

- `SPC-028-T1`: [FR-001] Implement `tenx ticket-brief` CLI command and MCP tool [in_progress]
- `SPC-028-T2`: [FR-002, FR-003, FR-004] Implement `tenx dispatch` runner with git worktree isolation and adapter execution [todo]
- `SPC-028-T3`: [FR-005] Author universal `tenx-dispatch` skill and wire into agent presets [todo]
- `SPC-028-T4`: [FR-001, FR-002, FR-004] Add comprehensive smoke test suite coverage and dogfood ticket dispatch [todo]

## Validation

- FR-001: Given a valid spec SPC-028 and ticket SPC-028-T1, When running `tenx ticket-brief SPC-028 SPC-028-T1`, Then a formatted Markdown brief is returned with ticket requirements and conventions.
- FR-002: Given `--dry-run`, When running `tenx dispatch SPC-028 SPC-028-T1 --dry-run`, Then the worktree path and runner command are printed without executing git operations.
- FR-003, FR-004: Run `python3 tests/smoke_test.py` and `python3 tests/smoke_test.py --module` to verify zero-regression pass across all tests.
