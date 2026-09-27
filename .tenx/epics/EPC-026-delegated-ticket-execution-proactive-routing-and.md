---
id: EPC-026
type: epic
title: 'Delegated Ticket Execution: proactive routing and default visual projection'
status: complete
priority: P1
created: 2026-09-27
updated: '2026-09-27'
---

## Objective

An agent working a tenx-governed project has no signal that isolated ticket
workers exist, so it implements every ticket in-band and the delegation,
context-isolation, and visual-observability machinery built in
EPC-018..EPC-025 never runs. Operators asked for workers to appear in their
Herdr sidebar as soon as there was ticket-shaped work; today nothing in the
harness ever proposes, triggers, or auto-projects a worker, and a `--visual`
request outside a multiplexer silently degrades to an invisible headless run
that still reports success. This epic closes the loop: delegation becomes a
proactive, discoverable step in the loop the agent already runs, Herdr
projection becomes a per-project configured default instead of a
per-invocation flag, and a failed visual launch can no longer leak a worktree
and branch or masquerade as a completed dispatch.

## Key results

- **KR1**: `tenx next` emits an actionable delegation command naming the exact
  `tenx dispatch` / `tenx swarm` invocation for any spec with ready tickets, and
  0 specs with ready tickets omit it.
- **KR2**: The bundled `tenx-dispatch` skill routes proactively on ticket-shaped
  intent, with its own "use proactively" trigger contract and no clause that
  suppresses it for ordinary spec-driven work.
- **KR3**: A project that sets `dispatch.visual` in `.tenx/config.yaml` gets Herdr
  or tmux projection on every `tenx dispatch` / `tenx swarm` without passing
  `--visual`; projects that set nothing keep today's headless default (0
  behavior change on upgrade).
- **KR4**: `tenx dispatch --visual` with no active multiplexer exits non-zero
  with an explicit error instead of running an invisible headless worker, and
  0 failed visual launches leave a `.tenx/worktrees/<TICKET-ID>` directory or
  `tenx/<TICKET-ID>` branch behind.

## Scope

- Proactive routing contract for the bundled `tenx-dispatch` skill and the
  agent-facing surfaces the model reads at session start.
- `tenx next` and `tenx exec` delegation guidance that names the literal
  command to run.
- A `dispatch` section in `.tenx/config.yaml` for default worker harness and
  projection preference, with an environment-variable override.
- Integrity of the visual launch path: explicit failure when projection is
  requested but impossible, and no residual worktree/branch after any failed
  launch.

## Non-goals

- A background watcher, daemon, or ticket-transition hook that spawns workers
  with no operator act. Unattended runs stay explicitly scheduled
  (`tenx swarm --auto-reconcile` from CI or cron), which is the correct
  shape for autonomous spend.
- Automatic merge or unattended `tenx reconcile`. Landing remains an explicit
  operator approval even when dispatch is configured.
- Changing the default projection behavior for projects that do not opt in.
- Replacing the Herdr/tmux adapters, the worktree isolation model, or the
  dispatch/swarm/reconcile command surface.
- A configurable per-ticket delegation policy (which ticket classes are worth
  delegating). The trigger surfaces the option; the orchestrating agent and the
  operator still decide.

## Milestones

- [ ] M1: Proactive routing contract — the `tenx-dispatch` skill triggers on
      ticket-shaped intent instead of suppressing itself (KR2).
- [ ] M2: Deterministic trigger surfaces — `tenx next` and `tenx exec` name the
      exact delegation command for any spec with ready tickets (KR1).
- [ ] M3: Configured projection — `dispatch.visual` / `dispatch.agent` in
      `.tenx/config.yaml` with environment override, default off (KR3).
- [ ] M4: Visual-launch integrity — explicit failure when projection is
      impossible and zero residual worktree/branch on any failed launch (KR4).
