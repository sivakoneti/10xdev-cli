---
id: SPC-036
type: spec
title: "Delegation trigger, config-driven visual projection, and visual-launch failure integrity"
status: complete
epic: EPC-026
priority: P1
created: 2026-09-27
updated: '2026-09-27'
tickets:
- id: SPC-036-T1
  title: "Make the bundled tenx-dispatch skill route proactively on ticket-shaped intent (FR-001)"
  status: done
- id: SPC-036-T2
  title: Emit an actionable delegation action from tenx next (FR-002)
  status: done
- id: SPC-036-T3
  title: Emit a delegation block in the tenx exec brief (FR-003)
  status: done
- id: SPC-036-T4
  title: "Honor a dispatch section in .tenx/config.yaml with env override (FR-004)"
  status: done
- id: SPC-036-T5
  title: "Fail loudly when --visual cannot be honored (FR-005)"
  status: done
- id: SPC-036-T6
  title: "Remove residual worktree and branch on every failed launch (FR-006)"
  status: done
---

## Summary

This spec makes ticket delegation something the harness actually proposes.
Today `tenx dispatch` is reachable only if a human or agent thinks of it:
nothing in the loop, no skill routing rule, and no `tenx next` action ever
names it, so no project has ever seen a Herdr worker appear. This spec adds
the missing trigger surfaces (proactive skill contract, `tenx next` action,
`tenx exec` delegation block), a per-project `dispatch` config section that
turns Herdr/tmux projection into a default instead of a per-call flag, and
fixes two integrity defects on the visual path — a silent headless downgrade
and a leaked worktree/branch after a failed launch.

## Context and scope

`dispatch_ticket()` (`src/tenx/dispatch.py:473`) has exactly two call sites:
`cmd_dispatch` (`src/tenx/cli.py:1080`) and `run_swarm`
(`src/tenx/swarm.py:178`). No hook, no lifecycle transition, no `tenx next`
action, and no background loop invokes it. The agent-facing surfaces the model
reads each session do not mention it: the context packet's operating protocol
has nine steps and none of them is dispatch; `compute_next`
(`src/tenx/nextup.py:34-88`) emits only six action types and none is
delegation; and the bundled `tenx-dispatch` skill's front-matter explicitly
disarms itself with "Do not use for ordinary in-session coding", which is
exactly what working a spec ticket in-band is.

`--visual` is `action="store_true"` on both `tenx dispatch`
(`src/tenx/cli.py:1869`) and `tenx swarm` (`src/tenx/cli.py:1915`), and the
MCP tools hardcode `"visual": False` (`src/tenx/mcp.py:236`, `269`). No config
knob exists; `TENX_DISPATCH_MODEL` (`src/tenx/router.py:96`) only selects a
model. EPC-019 promised projection "unless `--visual` is specified **or
configured**" and the configured half was never built.

Two integrity defects sit on the same path. `plan_visual_projection` returns
`None` when no multiplexer is detected (`src/tenx/multiplexers.py:175`), so a
`--visual` request with neither Herdr nor tmux skips the projection block at
`src/tenx/dispatch.py:566` and falls through to the headless runner at line
681 — an invisible worker plus a success receipt. And `setup_worktree` runs at
line 554, before the `HERDR_ENV` re-check at line 578, so a launch that fails
after worktree creation leaves `.tenx/worktrees/<TICKET-ID>` and branch
`tenx/<TICKET-ID>` behind.

In scope: trigger surfaces, config, and the two defects. Out of scope: any
self-firing watcher, and any change to landing approval.

## Goals / non-goals

Goals:
- Make an agent working a spec discover the exact delegation command at the
  moment it decides what to do next, without the human suggesting it.
- Let a project configure visual projection once instead of passing a flag on
  every call, while keeping the headless default for projects that opt out.
- Make a visual request either visibly happen or visibly fail, never silently
  degrade.
- Leave no worktree or branch behind after a failed dispatch.

Non-goals:
- A background watcher, daemon, or ticket-transition hook that spawns workers
  with no operator act. Tickets are files on disk, so such a trigger is a
  poller: it burns idle compute and, without an idempotency guard keyed on
  ticket id, duplicates spend on retry. Unattended runs stay explicitly
  scheduled from CI or cron.
- Automatic merge, unattended `tenx reconcile`, or relaxing the operator
  approval gate in `tenx-dispatch`'s landing protocol.
- Flipping the default projection behavior for projects that have not set
  `dispatch.visual`.
- Replacing the Herdr/tmux adapters, worktree isolation, or the
  dispatch/swarm/reconcile command surface.

## Requirements

- FR-001: The bundled `tenx-dispatch` skill MUST carry a proactive trigger
  contract: its front-matter description MUST instruct proactive use and name
  ticket-shaped intent (a spec with open tickets, `tenx next` reporting
  implementable tickets, multi-ticket specs) as delegation triggers, and MUST
  NOT contain a clause that suppresses routing for ordinary spec-driven work.
- FR-002: `tenx next` MUST emit a delegation action for every spec in an
  active state that has at least one ticket in `todo` or `in_progress` status,
  and that action MUST name the literal `tenx dispatch <SPEC-ID> <TICKET-ID>`
  command for the next ready ticket, plus `tenx swarm <SPEC-ID>` when the
  spec's ready tickets are independent.
- FR-003: `tenx exec <SPEC-ID>` MUST include a delegation section naming the
  literal `tenx dispatch` / `tenx swarm` commands for the spec's tickets
  whenever the spec has more than one open ticket.
- FR-004: A `dispatch` section in `.tenx/config.yaml` MUST be able to set the
  default worker harness (`agent`) and whether projection is requested by
  default (`visual`), and a `TENX_DISPATCH_VISUAL` environment variable MUST
  override `dispatch.visual`. Absent configuration MUST preserve today's
  headless default for both `tenx dispatch` and `tenx swarm`, and the CLI
  `--visual` / `--agent` flags MUST continue to override configuration.
- FR-005: When visual projection is requested and no multiplexer is available
  to honor it, `tenx dispatch` and `tenx swarm` MUST return a non-zero exit
  with an explicit error naming the cause; they MUST NOT fall through to the
  headless runner.
- FR-006: Every dispatch failure path that occurs after worktree creation MUST
  leave no `.tenx/worktrees/<TICKET-ID>` directory and no `tenx/<TICKET-ID>`
  branch behind, unless a recorded receipt for that ticket already exists.

## Success criteria

- SC-001: Given a project with an active spec holding a `todo` ticket, When
  `tenx next --json` runs, Then exactly one delegation action is returned whose
  `detail` contains the runnable `tenx dispatch <SPEC-ID> <TICKET-ID>` string.
- SC-002: Given the bundled skill catalog, When the `tenx-dispatch`
  front-matter description is inspected, Then it contains a proactive-use
  instruction, names at least two ticket-shaped triggers, and contains no
  suppression clause matching "do not use for ordinary".
- SC-003: Given `.tenx/config.yaml` with `dispatch: {visual: true}`, When
  `tenx dispatch <SPEC> <TICKET> --dry-run --json` runs with no CLI flags,
  Then the result reports a visual projection plan; and given no config, the
  same call reports `visual: false`.
- SC-004: Given `HERDR_ENV` and `TMUX` both unset, When `tenx dispatch` is
  invoked with `--visual`, Then it exits non-zero with an error, performs no
  headless execution, and creates no worktree.
- SC-005: Given a launch that fails after worktree creation, When the command
  returns, Then neither `.tenx/worktrees/<TICKET-ID>` nor branch
  `tenx/<TICKET-ID>` exists.

## Design

Six independent changes, three in the "make the trigger visible" family and
three in the "make the path honest" family. Applies CON-001 (follow existing
structure, no new framework), CON-002 (standard library only — config
reuses the existing `yamlite` loader in `src/tenx/yamlite.py` via
`_load_config` in `src/tenx/discovery.py:70`), and CON-003 (both smoke modes
before commit).

**Trigger surfaces.** Three layers, ordered by how early the agent sees them.

*Skill routing contract (FR-001).* `SKILLS["tenx-dispatch"]` in
`src/tenx/templates.py:354`. The front-matter description is the only part of
a skill the agent sees before deciding to load it, and it is therefore the
routing rule. Rewrite it to instruct proactive use and name ticket-shaped
intent, and replace "Do not use for ordinary in-session coding" with a scoped
clause that excludes only non-ticket subagent work. No new file: the skill body
is already correct, only the contract is wrong.

*`tenx next` action (FR-002).* `compute_next` in `src/tenx/nextup.py`. A new
action at priority 3.5 (after review-and-land, before implement-in-band) for
specs with ready tickets. It reuses the existing ticket-iteration block and
`build_spec_dag` for the independence test, and puts the runnable command in
`detail` — the field `render_next` already prints. The action is advisory, not
executable: `tenx next` stays a read-only digest, so surfacing a command cannot
start spend without a second, explicit invocation.

*`tenx exec` block (FR-003).* `BRIEF_TEMPLATE` in `src/tenx/execbrief.py:24`.
This is the unattended path (`tenx exec SPC-001 | claude -p`) and it currently
tells the agent only to implement in order. Add a delegation section listing
the literal commands, gated on more than one open ticket so a single-ticket
spec is not pushed toward a handoff it does not need.

**Configured projection (FR-004).* A `dispatch` section in `.tenx/config.yaml`,
read through the existing `_load_config` helper. Nested sections are already
idiomatic here — `sync.py:104` reads `github.repo` the same way — so no
validation change is needed. Resolution order: CLI flag > `TENX_DISPATCH_VISUAL`
env > `dispatch.visual` in config > current default (`False`). `--agent` gains
the same config fallback for `dispatch.agent`. The default stays `False`:
per the project's own opt-in posture, and because the environment variable is
the escape hatch for one-off runs.

Why config rather than flipping the CLI default: projection is
*observability*, so enabling it is strictly safer than the headless path it
replaces, but it is still a behavior change for every existing project on
upgrade, and EPC-019's non-goals explicitly promised the headless default
stays. Config satisfies EPC-019's "or configured" clause without breaking
that promise.

**Visual-launch integrity (FR-005, FR-006).* In `dispatch_ticket`, resolve
projection once and treat "requested but impossible" as a hard error before
any mutation: if `visual` is set and `plan_visual_projection` returned `None`,
return an error naming the missing multiplexer instead of falling through. The
existing Herdr `HERDR_ENV` guard is hoisted above `setup_worktree`, and a
single cleanup helper removes the worktree and branch on any post-creation
failure, guarded by "no receipt already recorded" so a retry after a real
dispatch is never destructive. `run_swarm` propagates the same rule per
worker.

## Alternatives considered

- **Self-firing watcher on ticket availability.** Rejected. Tickets are files
  on disk, so there is no event source and the trigger would be a poller:
  idle compute plus, absent an idempotency guard keyed on ticket id, duplicate
  spend on retry. It would also fire on exactly the quick targeted tickets
  where delegation is anti-productive. Unattended execution remains available
  and explicit via `tenx swarm --auto-reconcile` from CI or cron.
- **Flip `--visual` to default-true.** Rejected: changes documented behavior
  for every project on upgrade and contradicts EPC-019's stated non-goal.
  Config gives the same end state per project, opt-in.
- **A `tenx auto-dispatch` command an agent is told to run.** Rejected: same
  discoverability problem as today with an extra indirection; the trigger has
  to live in the surfaces the agent already reads.
- **Auto-merge when a configured worker finishes.** Rejected: it removes the
  operator approval that makes the worktree sandbox the reason auto-dispatch
  is acceptable at all.
- **Renaming the skill or adding a second dispatch skill.** Rejected: the body
  and the command surface are correct; only the routing contract was wrong.

## Cross-cutting concerns

- **Security.** No new privilege surface. `dispatch.visual` only changes where
  a worker is displayed; the worktree sandbox, branch naming, and the
  operator-approval landing gate are unchanged. Auto-dispatch remains bounded
  because a worker cannot merge without `tenx reconcile` and operator approval.
- **Backward compatibility.** No behavior change without configuration. The
  CLI flags keep their current meaning and precedence; `dispatch.agent` and
  `dispatch.visual` are additive config keys that predate no code path.
- **Observability.** Every new failure path returns a structured `error` and
  exits non-zero, and cleanup is verifiable by the absence of the worktree and
  branch rather than by a log line.
- **Testing.** Regression coverage in `tests/smoke_test.py` for each FR:
  proactive contract string, `tenx next` delegation action, exec-brief
  delegation block, config resolution precedence, the no-multiplexer error
  path, and worktree/branch cleanup. Both smoke modes per CON-003.
- **Docs.** README gains a "Delegation trigger and configured projection"
  subsection; the visual section's default statement is corrected; CHANGELOG
  entry via `tenx changelog add` per CON-004.

## Tickets

- [ ] SPC-036-T1: Make the bundled tenx-dispatch skill route proactively on ticket-shaped intent (FR-001)
- [ ] SPC-036-T2: Emit an actionable delegation action from tenx next (FR-002)
- [ ] SPC-036-T3: Emit a delegation block in the tenx exec brief (FR-003)
- [ ] SPC-036-T4: Honor a dispatch section in .tenx/config.yaml with env override (FR-004)
- [ ] SPC-036-T5: Fail loudly when --visual cannot be honored (FR-005)
- [ ] SPC-036-T6: Remove residual worktree and branch on every failed launch (FR-006)

## Validation

- FR-001: Given the bundled skill catalog, When the `tenx-dispatch` description
  is read, Then it contains a proactive-use instruction and at least two
  ticket-shaped triggers and no "do not use for ordinary" suppression clause.
- FR-002: Given an active spec with a `todo` ticket, When `tenx next --json`
  runs, Then one returned action's `detail` contains the runnable
  `tenx dispatch <SPEC-ID> <TICKET-ID>` command.
- FR-003: Given a spec with more than one open ticket, When `tenx exec <SPEC-ID>`
  runs, Then the printed brief contains a `tenx dispatch` command for its
  tickets.
- FR-004: Given `dispatch: {visual: true}` in config, When
  `tenx dispatch <SPEC> <TICKET> --dry-run --json` runs with no flags, Then the
  result carries a projection plan; and Given no config, Then `visual` is
  false; and Given `TENX_DISPATCH_VISUAL=1`, Then the same call is visual.
- FR-005: Given `HERDR_ENV` and `TMUX` unset, When `tenx dispatch --visual` is
  invoked, Then it exits non-zero with an explicit multiplexer error and
  creates no worktree.
- FR-006: Given any launch that fails after worktree creation, When it returns,
  Then `.tenx/worktrees/<TICKET-ID>` and branch `tenx/<TICKET-ID>` are absent.
- Suite: `python3 tests/smoke_test.py` and `python3 tests/smoke_test.py --module`
  both pass; `tenx validate` reports 0 errors; `tenx converge SPC-036` reports
  CONVERGED.

## Open questions

- None.
