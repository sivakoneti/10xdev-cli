---
id: EPC-016
type: epic
title: Agent reach for the spec discipline
status: complete
created: 2026-08-26
updated: 2026-08-26
---

## Objective

An agent working through MCP never has to leave the governed loop. SPC-025
made tenx specs checkable (FR-### requirements, clarify markers, coverage,
converge), but that discipline was only reachable from the CLI. Agents in
Claude/Cursor/other MCP clients are the primary tenx users; if they cannot
run the convergence step the exec brief requires, the discipline degrades
to a CLI-only ritual. This epic brings the spec-discipline loop to every
surface agents actually use, so "did this spec converge?" is one tool call
away in any project.

## Key results

- KR1 — MCP agents can get a deterministic convergence verdict for any
  spec and append missing tickets without a CLI round-trip (shipped:
  tenx_converge, SPC-026).
- KR2 — Surface parity is visible in the capability catalog: converge is
  tagged `both`, so agents discover it via tenx_capabilities.

## Scope

- MCP/agent-surface exposure of the SPC-025 discipline primitives.
- Docs that keep README/DOC-001 tool counts and semantics exact.

## Non-goals

- New converge semantics (SPC-025 owns behavior).
- `converge --all` harness sweep (future ticket on operator demand).
- Non-MCP agent surfaces (skills already teach the CLI loop).

## Milestones

- [x] M1 — tenx_converge MCP tool shipped with lock-on-append (SPC-026).
