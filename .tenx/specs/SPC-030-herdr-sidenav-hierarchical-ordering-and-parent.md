---
id: SPC-030
type: spec
title: Herdr Sidenav Hierarchical Ordering and Parent Commit Worktree Isolation
epic: EPC-020
status: complete
owner: human
created: 2026-09-15
tickets:
  - id: SPC-030-T1
    title: "Implement Herdr socket workspace move and parent commit branching [FR-001, FR-002]"
    status: done
  - id: SPC-030-T2
    title: "Add OMP and Prime Agent harness adapters with Bifrost model support [FR-003]"
    status: done
  - id: SPC-030-T3
    title: "Update CLI, MCP tool schemas, and smoke tests [FR-001, FR-002, FR-003]"
    status: done
updated: 2026-09-15
---

# SPC-030 — Herdr Sidenav Hierarchical Ordering and Parent Commit Worktree Isolation

## Summary

Implement hierarchical Herdr sidebar workspace placement via raw-socket `workspace.move` protocol and exact parent commit worktree branching (`git rev-parse HEAD`), ensuring subagents appear immediately under the parent workspace in Herdr navigation and run against the exact current codebase snapshot.

## Context and scope

Subagents dispatched with `--visual` in Herdr previously appended to the bottom of the workspace list, separating child agents from their parent project. Furthermore, subagent worktrees need to branch strictly from the parent session's current checkout (`HEAD`).

## Goals / non-goals

Goals:
- Check `$HERDR_SOCKET_PATH` and current workspace index.
- Use protocol 16 `workspace.move` to place newly created subagent workspaces immediately beneath the parent in Herdr's sidebar.
- Branch worktrees from `git rev-parse HEAD`.
- Add native command adapters for approved harnesses: `omp`, `pi`, `prime-agent`, `codex`.
- Support `--model` parameter for targeting Bifrost and Agent Anti-Gravity (`google-antigravity`) models.

Non-goals:
- External runtime dependencies (pure stdlib per `CON-002`).

## Requirements

- FR-001: Multiplexer layer MUST query Herdr Unix socket and reposition child workspaces below parent via `workspace.move`.
- FR-002: Worktree creation MUST branch from `git rev-parse HEAD`.
- FR-003: Dispatcher MUST support `omp`, `pi`, `prime-agent`, and `codex` command constructors with `--model` flag.

## Success criteria

- SC-001: Herdr workspaces for subagents are positioned directly after the parent workspace.
- SC-002: Tests verify worktree creation against current HEAD commit.
- SC-003: Automated smoke tests cover Herdr socket move helper and harness command builders.

## Tickets

- [ ] SPC-030-T1: Implement Herdr socket workspace move and parent commit branching in `src/tenx/multiplexers.py` and `src/tenx/dispatch.py` (FR-001, FR-002)
- [ ] SPC-030-T2: Add OMP and Prime Agent harness adapters with Bifrost model support (FR-003)
- [ ] SPC-030-T3: Update CLI, MCP tool schemas, and smoke tests (FR-001, FR-002, FR-003)

## Validation

- Automated smoke tests in `tests/smoke_test.py`.
- Herdr Unix domain socket workspace ordering verification (`workspace.move`).
- Parent commit worktree branch verification (`git rev-parse HEAD`).
- Bifrost live query and model fallback router verified.
- Memory distillation Gap Ledger multi-session graduation tested.
