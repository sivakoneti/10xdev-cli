---
id: EPC-027
type: epic
title: "Capability catalog parity for configured dispatch"
status: draft
priority: P2
created: 2026-09-27
updated: 2026-09-27
---

## Objective

An agent that reads only `tenx capabilities` should not be able to reach a
harness that behaves differently from what the catalog says. After SPC-036
made delegation proactive and projection configurable, the catalog fell
behind: it still describes dispatch as a command to type, with no mention
that `tenx next` proposes the command, that a project can configure
projection as its default, or that `--no-visual` overrides that. This epic
closes that gap so the catalog is a truthful description of the shipped
surface, and keeps it truthful as the surface grows.

## Key results

- **KR1**: `tenx capabilities` lists the complete flag surface for
  `dispatch` and `swarm`, including `--no-visual`, in both markdown and JSON
  rendering, with 0 commands whose advertised usage names a flag the CLI does
  not accept.
- **KR2**: The catalog states that a `dispatch` section in
  `.tenx/config.yaml` and `TENX_DISPATCH_VISUAL` can make visual projection
  the project default, and that `tenx next` surfaces the delegation command,
  so an agent learns delegation is surfaced rather than only typed.

## Scope

- The `dispatch` and `swarm` entries in the capability catalog: flag surface
  and trigger/configuration guidance.
- Smoke coverage asserting the catalog stays in step with the CLI.

## Non-goals

- Changing dispatch, swarm, or any other command's behavior.
- New capabilities beyond the SPC-036 surface.
- Restructuring the catalog's groups, renderers, or MCP binding.
- Retro-auditing every other catalog entry's prose; this epic covers the
  entries SPC-036 made stale.

## Milestones

- [ ] M1: Catalog entries for `dispatch`/`swarm` match the shipped flag
      surface and configuration contract (KR1, KR2).
- [ ] M2: Smoke coverage pins the catalog text so drift is caught, not
      discovered by an agent (KR1).
