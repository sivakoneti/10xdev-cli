---
id: EPC-003
type: epic
title: deeper agent integration — MCP server and review flow
status: in_progress
created: 2026-08-24
updated: 2026-08-24
---

## Goal

Close the remaining integration gaps: harnesses with native MCP support
(Claude Code, Cursor, Cline, Windsurf, Copilot...) get tenx as first-class
tools instead of prompt instructions, and the daily loop gets a proper
review queue plus a way to archive finished epics.

## Milestones

1. M1 — `tenx mcp` serves the tenx surface over MCP stdio (SPC-005).
   One command, zero dependencies, works with any MCP-capable harness.
2. M2 — `tenx review` shows what awaits review; `tenx archive` retires
   finished epics cleanly (SPC-006).

## Out of scope (for now)

- MCP resources/prompts (tools only — they cover the whole surface).
- Remote/HTTP MCP transport (stdio is what harnesses spawn locally).

## Done means

An MCP-capable harness can list and call tenx tools end-to-end; review
and archive are part of the daily loop; smoke tests green.
