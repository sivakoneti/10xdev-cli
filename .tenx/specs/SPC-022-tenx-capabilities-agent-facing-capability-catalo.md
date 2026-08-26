---
id: SPC-022
type: spec
title: tenx capabilities - agent-facing capability catalog
status: complete
epic: EPC-012
created: 2026-08-26
updated: 2026-08-26
tickets:
  - id: SPC-022-T1
    title: capability registry module src/tenx/capabilities.py
    status: done
  - id: SPC-022-T2
    title: "CLI command `tenx capabilities [--json]`"
    status: done
  - id: SPC-022-T3
    title: MCP tool tenx_capabilities
    status: done
  - id: SPC-022-T4
    title: discovery pointer in the context packet
    status: done
  - id: SPC-022-T5
    title: README section + smoke coverage
    status: done
---

## Summary

Agents only learn the full tenx surface by reading the whole context
packet or README; there is no single answer to "what can I do with tenx,
and when do I use each piece?". This spec adds a curated capability
catalog exposed three ways: `tenx capabilities` on the CLI, a
`tenx_capabilities` MCP tool, and a discovery pointer inside the context
packet so agents find it unprompted.

## Context and scope

The MCP server (`src/tenx/mcp.py`, SPC-005) already carries hand-written
tool descriptions, but an agent connected over MCP sees only its client's
tool list, and a CLI-only agent sees nothing at all beyond `--help`.
Scope: a static, curated catalog of every CLI subcommand and MCP tool
with `what` / `when` guidance, rendered as text or JSON. Non-goal:
generating argparse help or `_tooldefs()` descriptions from the registry
(deliberately deferred — touching all 13 existing tools risks churn for
zero behavior gain).

## Goals / non-goals

Goals:
- One registry (`CAPABILITIES`) as the single listing source for CLI and MCP.
- `tenx capabilities [--json]`: human table by default, stable JSON for agents.
- `tenx_capabilities` MCP tool returning the same text via `_call_cli`.
- Context packet gains one pointer line so any harness discovers the catalog.
- Zero runtime dependencies (CON-002); smoke suite stays green in both
  modes (CON-003).

Non-goals:
- Auto-generating MCP descriptions or argparse help from the registry.
- Runtime capability introspection (feature flags, version gating).

## Design

New module `src/tenx/capabilities.py`:

- `CAPABILITIES`: list of dicts — `{name, surface ("cli"|"mcp"|"both"),
  group, what, when, usage}`. Groups follow the session loop: discover,
  plan, track, quality, integrate, environment.
- `render_text()` groups entries under headings with usage lines;
  `catalog()` returns the JSON payload (`{"cli_version", "capabilities"}`).

`src/tenx/cli.py`: `cmd_capabilities(args)` wires both renderers through
the existing `_emit` helper; parser subcommand `capabilities` with
`--json`. Read-only — not added to MUTATING_COMMANDS.

`src/tenx/mcp.py`: one new tooldef `tenx_capabilities`, empty input
schema, handler `mk(C.cmd_capabilities, {"json": False})`.

`src/tenx/context.py`: PROTOCOL gains one step pointing at
`tenx capabilities`; the packet's workspace section mentions it once.

Why this wins: curated `when` guidance is the actual value (argparse help
cannot say "run watchdog after context"); keeping `_tooldefs()`
untouched makes this additive and low-risk.

## Alternatives considered

- Generate everything from `_tooldefs()` + argparse: true single source
  but rewrites 13 smoke-tested tool descriptions and still lacks `when`
  guidance. Rejected for this iteration.
- Docs-only page: no machine surface, agents never find it. Rejected.

## Cross-cutting concerns

Testing: smoke adds `tenx capabilities` (text + JSON parse), asserts the
MCP round trip lists 14 tools and can call `tenx_capabilities`, and
asserts the context packet advertises the command. Backward compat: the
"mcp lists N tools" assertion moves 13 -> 14; nothing else changes.

## Tickets

- SPC-022-T1 capability registry module `src/tenx/capabilities.py`
- SPC-022-T2 CLI command `tenx capabilities [--json]`
- SPC-022-T3 MCP tool `tenx_capabilities`
- SPC-022-T4 discovery pointer in the context packet
- SPC-022-T5 README section + smoke coverage

## Validation

- `python3 tests/smoke_test.py` and `PYTHONPATH=src python3 tests/smoke_test.py --module` green.
- Manual: `tenx capabilities`, `tenx capabilities --json | python3 -m json.tool`,
  JSON-RPC round trip calling `tools/list` then `tenx_capabilities`.
- `tenx validate` reports 0 errors before completion.

## Open questions

- None.
