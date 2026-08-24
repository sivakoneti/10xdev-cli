---
id: SPC-005
type: spec
title: tenx mcp — Model Context Protocol server mode
status: complete
epic: EPC-003
created: 2026-08-24
updated: 2026-08-24
tickets:
  - id: SPC-005-T1
    title: "JSON-RPC stdio core (framing, initialize, ping, errors)"
    status: done
  - id: SPC-005-T2
    title: "tool registry: 10 tools mapped onto cmd_* functions"
    status: done
  - id: SPC-005-T3
    title: tenx mcp serve + subprocess round-trip smoke test
    status: done
  - id: SPC-005-T4
    title: tenx mcp install writes managed .mcp.json
    status: done
  - id: SPC-005-T5
    title: README + adapter notes for MCP harnesses
    status: done
---

## Summary

`tenx mcp` runs a Model Context Protocol server on stdio (newline-
delimited JSON-RPC 2.0), exposing the tenx surface as native tools to
any MCP-capable harness. Zero new dependencies (stdlib json/sys). This
is tier-4 integration: beyond hooks, instruction files, and the
bootstrap snippet, harnesses with MCP get structured tool access.

## Architecture

New module `src/tenx/mcp.py`:

- Transport: newline-delimited JSON on stdin/stdout (MCP stdio). Loop
  until EOF; each request with an `id` gets exactly one response;
  notifications (`notifications/initialized`, `notifications/cancelled`)
  get none. Malformed lines -> JSON-RPC parse error, server keeps
  running (fault isolation, same philosophy as adapter detection).
- Methods: `initialize` (echo client protocolVersion when known, else
  "2025-03-26"; capabilities `{tools: {}}`; serverInfo tenx/version),
  `ping` ({}), `tools/list`, `tools/call`. Unknown method -> -32601.
- Tool registry: list of {name, description, inputSchema, handler}.
  Handlers reuse the existing CLI command functions by building an
  `argparse.Namespace` and capturing stdout with
  `contextlib.redirect_stdout` — no logic duplication, no subprocess.
  Exceptions inside a handler become `isError: true` tool results,
  never server crashes.
- Tools (v1): tenx_context, tenx_next, tenx_status, tenx_show,
  tenx_list, tenx_ticket, tenx_log, tenx_validate, tenx_scan,
  tenx_exec.
- Project root: resolved from the server process cwd via the normal
  discovery chain; `--root` overrides.

CLI wiring: `tenx mcp` (serve, default) and `tenx mcp install`
(writes managed `.mcp.json` for Claude Code project MCP config into
the governed code repo; idempotent like other managed files).

## Tickets

- SPC-005-T1 JSON-RPC stdio core (framing, initialize, ping, errors)
- SPC-005-T2 tool registry: 10 tools mapped onto existing cmd_* fns
- SPC-005-T3 `tenx mcp` serve + subprocess round-trip smoke test
- SPC-005-T4 `tenx mcp install` writes managed .mcp.json
- SPC-005-T5 README + adapter notes for MCP-capable harnesses

## Validation

- Smoke: spawn `tenx mcp` as a subprocess; send initialize ->
  tools/list -> tools/call(tenx_next) -> tools/call with bad tool ->
  malformed line; assert correct responses, error shapes, clean EOF
  exit.
- Manual: `claude mcp add tenx -- tenx mcp` works from a project dir.

## Open questions

- None; resources/prompts deferred by design.
