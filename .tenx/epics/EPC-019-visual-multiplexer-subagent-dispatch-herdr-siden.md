---
id: EPC-019
type: epic
title: "Visual Multiplexer Subagent Dispatch: Herdr Sidenav & Multiplexer Backends"
status: complete
created: 2026-09-15
updated: 2026-09-15
---

## Objective

Enable operators and agent supervisors to visually observe and interact with dispatched subagents directly in their terminal multiplexer sidebar and tab navigation (specifically Herdr workspaces/tabs, with support for tmux windows). When running inside Herdr or tmux, `tenx dispatch` can optionally or automatically project the subagent task into an isolated multiplexer workspace or window labeled with the ticket ID, allowing live inspection and terminal interaction while preserving context-isolated token savings and automated evidence gates.

## Key results

- **KR1**: When dispatched with `--visual` or `--multiplexer herdr` inside a Herdr session, a new Herdr workspace or tab labeled `<TICKET-ID>` is created pointing directly to the worktree cwd, visibly listed in Herdr's left sidebar navigation.
- **KR2**: When Herdr is detected via environment (`HERDR_ENV=1` / `HERDR_SESSION`), `tenx dispatch --dry-run` reports the planned visual Herdr command/workspace projection alongside the isolated worktree.
- **KR3**: Dispatched visual sessions support tmux window creation when inside tmux (`$TMUX` present), giving identical visible multiplexer isolation on classic terminal multiplexers.
- **KR4**: 100% adherence to zero-runtime-dependencies (`CON-002`) using Python standard library `subprocess` and CLI tool detection (`herdr`, `tmux`).
- **KR5**: Full automated smoke test coverage verifying dry-run plans, multiplexer resolution, and CLI flag bindings without regressions.

## Scope

- Detection of active terminal multiplexers (`herdr`, `tmux`) from environment variables (`HERDR_ENV`, `HERDR_SESSION`, `TMUX`) or explicit CLI flags (`--multiplexer <name>`, `--visual`).
- Visual projection for Herdr: creating workspace/tab (`herdr workspace create --cwd <worktree> --label <ticket-id> --no-focus` or `herdr tab create`) and executing the interactive/monitored subagent.
- Visual projection for tmux: creating window (`tmux new-window -c <worktree> -n <ticket-id> ...`).
- CLI interface additions to `tenx dispatch` (`--visual`, `--multiplexer`, `--no-focus`).
- MCP tool parameter updates in `tenx_dispatch` to expose visual/multiplexer dispatch options.
- Updates to `tenx-dispatch` skill documentation explaining how to monitor visual subagents in Herdr's sidenav.

## Non-goals

- Re-implementing Firstmate's internal complex state-machine or bash scripts; tenx remains a clean Python 3.10+ meta-harness.
- Supporting non-standard or proprietary GUI terminal multiplexers beyond Herdr and tmux (e.g. cmux/zellij remain future considerations).
- Removing or altering the default headless background dispatch engine (`--headless` remains default unless `--visual` is specified or configured).

## Milestones

- [ ] M1: Architecture and Spec `SPC-029` authored and approved covering visual multiplexer dispatch requirements.
- [ ] M2: Multiplexer adapter engine (`src/tenx/multiplexer.py` or extension in `src/tenx/dispatch.py`) supporting Herdr workspace/tab creation and tmux window creation.
- [ ] M3: CLI and MCP integration for `--visual` and `--multiplexer [herdr|tmux|auto|none]`.
- [ ] M4: Smoke test coverage, documentation updates, and validation passes with zero errors.
