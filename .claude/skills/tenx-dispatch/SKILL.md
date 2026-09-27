---
name: tenx-dispatch
description: Delegate a tenx spec ticket to an isolated worker in a git worktree, then project, supervise, reconcile, or abort it. Use proactively whenever a tenx-governed project has ticket-shaped work: a spec with open tickets, `tenx next` reporting a ready or implementable ticket, a multi-ticket spec where isolation would keep test output and exploration out of this session, or any mention of `tenx ticket-brief`, `tenx dispatch`, `tenx reconcile`/`merge`, `tenx abort`, `tenx dag`/`tenx swarm`, delegated spec tickets, parallel ticket workers, isolated worker branches, landing worker changes, or a Herdr-visible ticket worker. Delegation is a routing decision: prefer an isolated worker for a wide ticket, several ready tickets, or anything likely to produce large test logs, and implement in band only for quick targeted changes. Do not use for generic non-ticket subagent tasks or plain Herdr control that does not involve a tenx ticket/worktree.
---

# Subagent Ticket Dispatch

You are the supervisor agent. Isolated workers keep exploratory output and
test logs out of the supervisor context, leaving you focused on scope,
evidence, and landing.

## Before dispatching

1. Read the target spec, ticket brief, and project conventions.
2. Inspect the exact dry-run command and model route. Do not launch an
   adapter that requests approval, sandbox, filesystem, network, or
   credential bypass unless the user explicitly approved that exact scope.
3. If Herdr is involved, read `skill://herdr` first when it is available. Herdr
   is an explicit control surface, not a substitute for the tenx
   ticket/worktree contract. Do not block on that skill being routed: the
   supervision commands you need are listed inline below.

## Dispatch modes

### Herdr-managed visual dispatch

Use when Herdr projection is requested or configured (`dispatch.visual` in
`.tenx/config.yaml`, or `TENX_DISPATCH_VISUAL=1`). Herdr requires
`HERDR_ENV=1`; if the check fails, stop and report that the command must run
from a Herdr-managed pane. `tenx dispatch --visual` fails loudly rather than
downgrading to a headless worker, so a silent invisible run is a bug, not a
configuration to work around.

Read `herdr --help` and the relevant command groups instead of running bare
`herdr` for discovery; bare `herdr` launches or attaches the TUI.

The dispatch engine creates the isolated worktree, then uses Herdr's agent
surface with the returned workspace and pane IDs. The supervisor must retain
the full lifecycle:

1. Create the isolated location with the worktree as its cwd.
2. Start the requested supported agent kind in the returned available pane.
3. Prompt the named agent with the ticket brief and use `--wait` for the
   first settled state.
4. Inspect `blocked` with `herdr agent get` and `herdr agent read`; never
   answer an approval or question dialog without the user's decision.
5. Treat `idle` and `done` as ready-for-input states, not automatic proof of
   correctness. Read the output and review the worktree diff.
6. On success, use `tenx reconcile <TICKET-ID> --json` only after operator
   approval. On failure or abandonment, use `tenx abort <TICKET-ID>` and
   preserve the receipt.

The receipt from `tenx dispatch` carries `workspace_id`, `pane_id`, and
`agent_name`; those are the stable handles for the lifecycle above. Inspect
them with the supervisor commands directly when the herdr skill has not been
loaded:

```bash
herdr agent get <agent_name>
herdr agent read <agent_name> --source recent-unwrapped --lines 120
herdr agent wait <agent_name> --until blocked --timeout 120000
```

Read those outputs before answering a blocked agent, and never derive
completion from a missing target, an unparsed response, or a command that was
merely submitted. Use stable IDs from JSON. Use `--no-focus` for background
work.

### Headless dispatch

Run `tenx dispatch <SPEC-ID> <TICKET-ID> --agent <name>` for a blocking
headless worker. This creates `.tenx/worktrees/<TICKET-ID>`, stores the
scoped brief and receipt under `.tenx/dispatch/<TICKET-ID>/`, and returns
execution metadata. That metadata is not test or validation evidence; run
the exact project checks yourself.

### Native in-band delegation

Use a host-native tool only when `tenx dispatch` cannot represent the worker.
Pass the same ticket brief and preserve the same diff, validation, evidence,
approval, and landing gates. Confirm that it created the expected
`.tenx/worktrees/<TICKET-ID>` and `tenx/<TICKET-ID>` branch before using
`tenx reconcile`; otherwise use the host's documented cleanup and landing
mechanism.

## The dispatch protocol

1. Generate and review the brief:
   `tenx ticket-brief <SPEC-ID> <TICKET-ID>`.
2. Inspect the dry-run:
   `tenx dispatch <SPEC-ID> <TICKET-ID> --agent <name> --dry-run --json`.
3. Launch exactly one supported worker mode and retain its structured receipt.
4. Supervise through completion or a real blocked/failure state. Do not
   advance to landing from a timeout, missing target, malformed response, or
   silently failed launch.
5. Run the exact tests named by the spec and conventions in the worktree.
   `tenx validate` is required but is not a substitute for project tests.
6. Review the actual diff against the parent branch, not a hard-coded `main`:
   `git diff --stat HEAD...tenx/<TICKET-ID>` and
   `git diff HEAD...tenx/<TICKET-ID>`.
7. Present evidence and obtain explicit operator approval before merging,
   deleting branches/worktrees, aborting worker work, or using automatic
   swarm reconciliation. Never use `--skip-verify` for normal landing.
8. After approval, land with `tenx reconcile <TICKET-ID> --json`, then run
   `tenx validate` and log evidence with `tenx log ... --ref <SPEC-ID>`.

## Full lifecycle invariant

Every visual worker has an owner, stable workspace/pane/agent identifiers, a
submitted task, an observed lifecycle state, readable output, a preserved
worktree, and exactly one terminal outcome: reconciled, aborted, or blocked
for human action. Missing evidence is a failure, not a successful dispatch.
