---
id: EPC-018
type: epic
title: Subagent Ticket Dispatch — universal multi-harness worker delegation
status: complete
created: 2026-09-14
updated: '2026-09-14'
---

## Objective

Autonomous coding agents handling non-trivial projects quickly exhaust context windows and suffer from reasoning drift when executing multiple tickets sequentially in a single chat session. Engineers and supervisors need a reliable, harness-agnostic way to delegate individual tickets to isolated subagents while preserving 90%+ of supervisor context. This epic delivers universal subagent delegation in tenx—allowing agents running in Pi, Codex, Prime Agent, DSH/DSH Web, Grok, and Claude to format scoped ticket briefs, dispatch isolated headless workers in dedicated git worktrees, track ticket lifecycles, and enforce the tenx evidence gate before merging work.

## Key results

- KR1 — `tenx ticket-brief <SPEC> <TICKET>` generates an isolated, self-contained ticket execution brief (ticket description, acceptance criteria, conventions, and test targets) under 1,500 tokens, eliminating supervisor history contamination.
- KR2 — `tenx dispatch <SPEC> <TICKET> --agent <harness>` creates an isolated git worktree, executes headless workers across all supported adapters (`pi`, `codex`, `prime-agent`, `dsh`), captures structured stdout/stderr outcomes, and updates ticket status without external runtime dependencies (CON-002).
- KR3 — Universal subagent skill (`tenx-dispatch`) bundled and accessible across all adapters instructing supervisors when to delegate, monitor, and verify evidence.
- KR4 — Both smoke suites (`tests/smoke_test.py` and `tests/smoke_test.py --module`) pass with full coverage for ticket brief generation, dispatch worktree lifecycle, and adapter command formatting.

## Scope

- Scoped ticket brief generation CLI command and MCP tool (`tenx ticket-brief`).
- Worktree lifecycle manager in Python stdlib for isolated ticket execution.
- Headless execution runners for detected or specified agent harnesses (Codex, Prime Agent, Pi, Claude Code, Grok, DSH).
- Structured receipt reporting (branch, test evidence, validation status, error log).
- In-harness delegation guidance skill (`tenx-dispatch`).
- DSH Cordis preset update to expose ticket dispatching capabilities in DSH Web.

## Non-goals

- Building a new terminal multiplexer or proprietary GUI daemon (we reuse git worktrees and standard process spawning).
- Creating custom model inference endpoints or proprietary LLM API clients (we delegate to installed CLI agent binaries).
- Arbitrary untracked prompt execution (subagents are strictly tied to a tracked tenx spec ticket).

## Milestones

- [ ] M1 — Ticket brief generation and context slicing (`tenx ticket-brief` CLI + MCP tool).
- [ ] M2 — Headless worker dispatch and worktree management (`tenx dispatch` with adapter execution).
- [ ] M3 — Universal dispatch skill (`tenx-dispatch`) and DSH Cordis integration.
- [ ] M4 — Dogfooding validation on 10xdev-cli codebase and full test coverage.
