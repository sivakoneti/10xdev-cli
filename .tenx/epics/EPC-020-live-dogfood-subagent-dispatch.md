---
id: EPC-020
type: epic
title: Next-Gen Subagent Dispatch, Sidenav Ordering & Multi-Harness Bifrost Routing
status: complete
lead: human
created: 2026-09-15
updated: 2026-09-15
---

# EPC-020 — Next-Gen Subagent Dispatch, Sidenav Ordering & Multi-Harness Bifrost Routing

## Objective

Elevate `tenx dispatch` beyond external tools (Firstmate, Backpass) by providing:
1. Native hierarchical Herdr sidebar ordering via Unix socket `workspace.move` directly beneath the parent workspace.
2. Parent-commit git worktree branch isolation (`git rev-parse HEAD`).
3. Multi-harness support for approved engines (`omp`, `pi`, `prime-agent`, `codex`).
4. Intelligent model routing for Bifrost AI Gateway (`google-antigravity` frontier and flash models, free failover rules).
5. Closed-loop agent memory distillation and convention alignment.

## Key results

- KR1 — Herdr sidebar renders subagent workspaces positioned immediately underneath their parent workspace via protocol-16 `workspace.move`.
- KR2 — Git worktrees branch from exact parent commit (`git rev-parse HEAD`), ensuring accurate baseline isolation.
- KR3 — Subagent dispatcher natively supports `omp`, `pi`, `prime-agent`, and `codex` with appropriate flags and Bifrost models.
- KR4 — Zero runtime dependencies (`CON-002`) and 100% smoke test pass rate.

## Scope

- Core multiplexer enhancements (`src/tenx/multiplexers.py`).
- Dispatcher command resolution & worktree creation (`src/tenx/dispatch.py`).
- CLI options & MCP tool definitions (`src/tenx/cli.py`, `src/tenx/mcp.py`).
- Smoke tests and dogfood verification.

## Non-goals

- Third-party Python dependencies (`CON-002`).

## Milestones

- [ ] M1 — Sidenav hierarchical ordering and parent commit branch isolation (`SPC-030`).
- [ ] M2 — Multi-harness engine adapters and Bifrost model routing (`SPC-031`).
