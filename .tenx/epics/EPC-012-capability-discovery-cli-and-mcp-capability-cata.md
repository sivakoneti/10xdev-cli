---
id: EPC-012
type: epic
title: Capability discovery - CLI and MCP capability catalog
status: complete
created: 2026-08-26
updated: 2026-08-26
---

## Objective

An agent dropped into a tenx-governed project (over CLI, hooks, or MCP)
currently has no single answer to "what can I do with tenx, and when do
I use each piece?" — it must read the whole context packet or README.
This epic delivers a curated capability catalog exposed on every surface
the agent already has, so agents discover and actually use the full
tenx loop unprompted. The beneficiary is anyone running agents on
tenx-governed repos: better tenx usage without extra onboarding.

## Key results

- KR1 — `tenx capabilities [--json]` prints the full command/tool
  catalog grouped by session-loop stage, each entry with `what` and
  `when` guidance.
- KR2 — the same catalog is callable as the `tenx_capabilities` MCP tool.
- KR3 — the context packet advertises the catalog, so any harness finds
  it without being told.

## Scope

- Curated registry module (`src/tenx/capabilities.py`) as the single
  listing source for CLI + MCP surfaces.
- Discovery pointer in the context packet protocol + workspace section.

## Non-goals

- Auto-generating `_tooldefs()` descriptions or argparse help from the
  registry (deferred; touching 13 existing tools for zero behavior gain).
- Runtime/feature-flag capability gating.

## Milestones

- [x] M1 — SPC-022: registry + CLI command + MCP tool + packet pointer,
      smoke-tested in both modes.
