---
id: SPC-029
type: spec
title: "Visual Multiplexer Subagent Dispatch: Herdr Workspace and Tmux Window Projection"
status: complete
epic: EPC-019
created: 2026-09-15
updated: 2026-09-15
tickets:
  - id: SPC-029-T1
    title: "Implement multiplexer detection and projection engine for Herdr and Tmux (FR-001, FR-002, FR-003)"
    status: done
  - id: SPC-029-T2
    title: "Wire --visual, --multiplexer, and --focus options into CLI and MCP tools (FR-004, FR-005)"
    status: done
  - id: SPC-029-T3
    title: Add smoke tests for visual multiplexer resolution and execution dry-run (FR-005)
    status: done
  - id: SPC-029-T4
    title: Update tenx-dispatch skill and docs with Herdr sidenav monitoring protocol (FR-006)
    status: done
---

## Summary

This spec implements visual multiplexer projection for `tenx dispatch`, enabling subagents to run visibly in Herdr workspaces/tabs (visible in Herdr's left sidebar) and tmux windows. Dispatched subagents maintain full context isolation via git worktrees, while operators can visually observe agent progress, inspect outputs, or interact in real-time.

## Context and scope

In `SPC-028`, `tenx dispatch` introduced ticket-level subagent delegation running headless child processes in background git worktrees. While ideal for automated batch execution, human operators working in interactive multiplexers like Herdr or tmux lose immediate visual awareness of subagent activity unless they inspect logs. Herdr is an agent-native workspace manager whose left sidebar displays active workspaces and tabs. By creating dedicated Herdr workspaces (`herdr workspace create --label <TICKET-ID> --cwd <worktree>`) or tabs for dispatched workers, subagents become immediately visible in Herdr's sidebar.

## Goals / non-goals

Goals:
- Auto-detect active multiplexers: Herdr (`HERDR_ENV=1` or `HERDR_SESSION`) and tmux (`TMUX`).
- Provide `--visual` flag to `tenx dispatch` to project the worker into a multiplexer workspace/window instead of pure headless background execution.
- Support `--multiplexer <auto|herdr|tmux|none>` flag to explicitly select or disable multiplexer projection.
- Allow non-focused spawning by default (`--no-focus`) so subagents do not disrupt the operator's active pane.
- Expose visual dispatch options via the `tenx_dispatch` MCP tool for supervisor agents.
- Maintain zero runtime dependencies (`CON-002`) using Python 3.10+ standard library.

Non-goals:
- Writing background socket servers or long-lived daemons.
- Emulating complex terminal protocol interactions beyond standard CLI wrappers.
- Replacing headless dispatch mode as the default behavior.

## Requirements

- FR-001: The system MUST detect active terminal multiplexers (`herdr`, `tmux`) from environment variables and CLI parameters.
- FR-002: When dispatching with visual projection under Herdr, the system MUST create an isolated Herdr workspace or tab labeled with the ticket ID and set its working directory to the isolated git worktree.
- FR-003: When dispatching with visual projection under tmux, the system MUST create an isolated tmux window named after the ticket ID rooted in the git worktree.
- FR-004: The CLI `tenx dispatch` and MCP tool `tenx_dispatch` MUST accept `--visual` (boolean), `--multiplexer` (string: `auto`, `herdr`, `tmux`, `none`), and `--focus` / `--no-focus` flags.
- FR-005: Dry-run dispatch (`tenx dispatch ... --dry-run`) MUST display the planned multiplexer projection commands alongside the agent command and worktree details.
- FR-006: The `tenx-dispatch` skill MUST instruct supervisor agents on when and how to use visual dispatch to let human operators monitor subagents in Herdr's sidenav.

## Success criteria

- SC-001: Running `tenx dispatch <SPEC> <TICKET> --agent pi --visual --dry-run` in an environment with `HERDR_ENV=1` prints the Herdr workspace creation plan with the worktree path and ticket label.
- SC-002: Running `tenx dispatch <SPEC> <TICKET> --agent pi --visual --dry-run` in an environment with `TMUX` prints the tmux window creation plan.
- SC-003: Passing `--multiplexer none` or omitting `--visual` defaults to direct headless execution.
- SC-004: All smoke tests pass in both CLI mode and source-tree mode (`python3 tests/smoke_test.py` and `python3 tests/smoke_test.py --module`).

## Design

### 1. Multiplexer Detection (`src/tenx/multiplexers.py`)
A pure Python module detecting:
- **Herdr**: checks `HERDR_ENV == "1"` or `HERDR_SESSION` or `shutil.which("herdr")`.
- **tmux**: checks `os.environ.get("TMUX")` or `shutil.which("tmux")`.

### 2. Projection Command Resolution
- For **Herdr Workspace**:
  ```bash
  herdr workspace create --cwd <worktree_dir> --label <ticket_id> [--no-focus]
  ```
  Followed by launching the agent inside the newly created workspace/pane:
  ```bash
  herdr pane run --workspace <wsid> "<agent-command>"
  ```
  Or a direct interactive launcher command inside the workspace.
- For **tmux Window**:
  ```bash
  tmux new-window -c <worktree_dir> -n <ticket_id> "<agent-command>"
  ```

### 3. Dispatch Integration (`src/tenx/dispatch.py`)
`dispatch_ticket` will support a `visual: bool = False` and `multiplexer: str = "auto"` parameter:
- When `visual=False`, behavior is unchanged (headless background process).
- When `visual=True`, resolves the multiplexer adapter and generates projection commands.
- Dry run will clearly display:
  ```
  Dispatch plan for SPC-028 / SPC-028-T1:
    worktree:    /path/.tenx/worktrees/SPC-028-T1
    branch:      tenx/SPC-028-T1
    multiplexer: herdr (session: default, visual workspace: SPC-028-T1)
    agent:       pi
    command:     herdr workspace create --cwd ...
  ```

## Alternatives considered

- **Subscribing to Herdr Unix Socket directly**:
  - *Trade-off*: Direct socket RPC requires managing socket lifecycle, JSON-RPC handshakes, and protocol versions. Invoking the official `herdr` CLI via `subprocess` is far more robust, forward-compatible across Herdr versions (0.7.x - 0.9.x), and adheres strictly to `CON-002`.

## Cross-cutting concerns

- **Backward Compatibility**: Headless dispatch remains the default unless `--visual` is explicitly passed or configured.
- **Zero Runtime Dependencies**: Standard library `os`, `shutil`, `subprocess` only.
- **Testing**: Automated smoke tests mock or simulate multiplexer environments without requiring a live Herdr or tmux daemon to run in headless CI.

## Tickets

Move tickets through todo -> in_progress -> in_review -> done. Keep the
frontmatter `tickets:` list in sync with this section.

- [x] SPC-029-T1: Implement multiplexer detection and projection engine for Herdr and Tmux (FR-001, FR-002, FR-003)
- [x] SPC-029-T2: Wire --visual, --multiplexer, and --focus options into CLI and MCP tools (FR-004, FR-005)
- [x] SPC-029-T3: Add smoke tests for visual multiplexer resolution and execution dry-run (FR-005, SC-001, SC-002)
- [x] SPC-029-T4: Update tenx-dispatch skill and docs with Herdr sidenav monitoring protocol (FR-006)

## Validation

- `python3 tests/smoke_test.py` passes all tests.
- `python3 tests/smoke_test.py --module` passes all tests.
- `tenx dispatch <SPEC> <TICKET> --agent pi --visual --dry-run` reflects Herdr workspace creation when simulated.
- `tenx validate` reports 0 errors and 0 warnings.
