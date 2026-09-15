---
id: SPC-026
type: spec
title: "MCP converge tool: spec discipline for agent-driven projects"
status: complete
epic: EPC-016
created: 2026-08-26
updated: 2026-08-26
tickets:
  - id: SPC-026-T1
    title: "[FR-001,FR-002] tenx_converge MCP tool with lock-on-append"
    status: done
  - id: SPC-026-T2
    title: "[FR-003] capabilities catalog tags converge for both surfaces"
    status: done
  - id: SPC-026-T3
    title: "[SC-001] smoke coverage for the MCP converge tool"
    status: done
---

## Summary

SPC-025 shipped `tenx converge` to the CLI surface only. MCP-served agents
are the primary consumers of tenx, and they cannot run the convergence step
the exec brief now requires. This spec exposes converge as a `tenx_converge`
MCP tool so agent-driven projects get the same spec-discipline loop.

## Context and scope

`src/tenx/mcp.py` registers 14 tools; mutating ones take the per-project
advisory lock (SPC-023-T11). converge fits the same split: the report is
read-only, `--append` writes tickets and must hold the lock.

## Goals / non-goals

Goals:
- MCP clients can get the convergence report and append missing tickets
  without leaving the MCP surface.
- Locking semantics match the CLI: append serializes behind the harness
  lock; read-only reports do not.

Non-goals:
- `converge --all` harness sweep (future ticket if operators ask).
- New converge semantics — this is surface parity only; behavior stays
  exactly what SPC-025 shipped.

## Requirements

- FR-001: The MCP server MUST expose a `tenx_converge` tool that takes a
  spec id and returns the convergence report as JSON, with the same
  verdict/exit-code semantics as the CLI (0 CONVERGED, 1 NOT CONVERGED,
  2 bad spec id).
- FR-002: The tool MUST support an `append` flag; when set it MUST take
  the per-project advisory lock, and when unset it MUST NOT.
- FR-003: The capabilities catalog MUST tag `converge` surface `both`
  once the MCP tool exists.

## Success criteria

- SC-001: Smoke proves the MCP handler returns a JSON report for a live
  spec, and an append call against a held lock returns rc=2 (lock
  contention), matching the other mutating tools.
- SC-002: `tenx capabilities --json` shows converge surface `both`.

## Design

`_tooldefs()` gains one entry with a custom handler (the generic `mk()`
fixes lock-at-registration; converge needs lock-by-argument):

```python
def converge_handler(args):
    kw = {"json": True, **{k: v for k, v in args.items() if v is not None}}
    return _call_cli(C.cmd_converge, lock=bool(args.get("append")), **kw)
```

The tool always answers JSON: MCP is a machine interface, and the CLI
keeps its human format. cmd_converge already implements every semantic;
the handler is pure plumbing.

## Alternatives considered

- Register converge in the generic `mk()` twice (locked + unlocked): two
  tool names for one command confuses agents; rejected.
- Shell out to the tenx binary from MCP: breaks the in-process model and
  the lock contract; rejected.

## Cross-cutting concerns

- Concurrency: append takes the lock; verified by the held-lock smoke
  check (SC-001).
- Backward compatibility: additive tool; existing 14 tools untouched.

## Tickets

Move tickets through todo -> in_progress -> in_review -> done. Keep the
frontmatter `tickets:` list in sync with this section.

- SPC-026-T1 [FR-001,FR-002] tenx_converge MCP tool with lock-on-append
- SPC-026-T2 [FR-003] capabilities catalog tags converge both surfaces
- SPC-026-T3 [SC-001] smoke coverage

## Validation

- FR-001: Given a project with an FR-carrying spec, When an MCP client
  calls tenx_converge, Then it receives the JSON report and the handler
  rc mirrors the CLI verdict.
- FR-002: Given the harness lock is held, When tenx_converge is called
  with append=true, Then the call returns rc=2 (blocked on lock);
  append=false is unaffected.
- `python3 tests/smoke_test.py` and `python3 tests/smoke_test.py --module`
  both green; `tenx validate` clean; `tenx converge SPC-026` CONVERGED.

## Open questions

- Resolved 2026-08-26: the MCP tool keeps CLI semantics (rc=1 when NOT
  CONVERGED). mcp.py sets `isError: rc != 0` but still delivers the full
  JSON report in content — same contract as tenx_validate, so agents see
  "action required" plus the data in one call.
