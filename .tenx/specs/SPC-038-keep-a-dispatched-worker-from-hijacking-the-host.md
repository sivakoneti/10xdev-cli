---
id: SPC-038
type: spec
title: Keep a dispatched worker from hijacking the host tool install
status: complete
epic: EPC-028
priority: P1
created: 2026-09-27
updated: '2026-09-27'
tickets:
- id: SPC-038-T1
  title: Forbid host-environment mutation in the dispatched worker brief (FR-001)
  status: done
- id: SPC-038-T2
  title: Record the host install snapshot in the dispatch receipt (FR-002)
  status: done
- id: SPC-038-T3
  title: Verify the host install during reconcile and abort teardown (FR-003)
  status: done
- id: SPC-038-T4
  title: Report a worktree-scoped install source from tenx doctor (FR-004)
  status: done
---

## Summary

Worktree isolation covers the files a worker writes, not the host tool
environment a worker can reach. A dispatched worker that runs a
package-manager install re-points the operator's global `tenx-cli` at the
worktree, and teardown then leaves the operator with a CLI that cannot start
and no hint why. This spec makes the contract explicit in the brief, records
what the host install looked like at launch, checks that assumption at
teardown, and reports the recovery command when it no longer holds.

## Context and scope

Observed live while dogfooding a Herdr dispatch: the worker's verification
step installed from inside `.tenx/worktrees/SPC-037-T1`, leaving
`_editable_impl_tenx_cli.pth` pointing at that worktree's `src`. `tenx
reconcile` then removed the worktree and the global `tenx` binary failed at
import with `ModuleNotFoundError: No module named 'tenx'`. Recovery required
knowing the install story, and the tool that should have reported it could
not run.

The detection cannot live only in the worker: once the module is unimportable
there is no process left to ask. So the check must run in the parent, at
teardown, against a snapshot taken before the worker started.

In scope: the brief, the receipt snapshot, the teardown check, and a doctor
check. Out of scope: sandboxing the worker and auto-repairing the install.

## Goals / non-goals

Goals:
- A dispatched worker receives a brief that forbids host installs and names
  the worktree-local verification command.
- Teardown knows what the host install pointed at before the worker ran, and
  reports a concrete recovery command if that changed.
- An operator can see a worktree-scoped install from `tenx doctor`.

Non-goals:
- Blocking a worker that ignores the brief; detection at teardown only.
- Replacing a host-level tool automatically.
- Any change to the landing gate, the merge workflow, or worktree isolation
  of the worker's own files.

## Requirements

- FR-001: The ticket brief handed to a dispatched worker MUST forbid
  package-manager installs and host tool-environment mutation, MUST name the
  worktree-local verification command the worker must use instead, and MUST
  instruct the worker to report an install requirement in its final message
  rather than performing it.
- FR-002: Dispatch MUST record the host install's resolved source path in the
  ticket receipt before the worker is launched, for both visual and headless
  launches.
- FR-003: `tenx reconcile` and `tenx abort` MUST compare the host install
  after teardown against the receipt snapshot, and when it no longer holds,
  the result MUST carry a host-install warning naming the recovery command.
  A broken host install MUST NOT turn a successful merge into a failure.
- FR-004: `tenx doctor` MUST report a problem when the running tenx resolves
  inside a `.tenx/worktrees/` path.

## Success criteria

- SC-001: Given the brief text, When a worker reads it, Then it names a
  forbidden install command set and the worktree-local verification command.
- SC-002: Given a dispatch receipt, When it is read, Then it carries a
  `host_install` snapshot with the resolved source path.
- SC-003: Given a receipt whose snapshot pointed inside a removed worktree,
  When teardown runs, Then the result carries a `host_install_warning` naming
  the recovery command, and the merge status is still `merged`.
- SC-004: Given a tenx resolving inside `.tenx/worktrees/`, When `tenx doctor`
  runs, Then it reports the problem and names the recovery command.

## Design

Four tickets, three modules. Applies CON-001 (follow the existing structure)
and CON-002 (standard library only — the snapshot is `sys.executable` plus
the resolved module path, no imports beyond the stdlib).

**Brief (FR-001).** Extend `TICKET_BRIEF_TEMPLATE` in `src/tenx/dispatch.py`
with a `## Host environment` section. It states that the worktree is deleted
at teardown, that any install pointing at it breaks the operator's CLI,
forbids `uv tool install`/`uv tool upgrade`/`pip install`/`pipx install`,
and gives `python3 -m tenx …` and `python3 tests/smoke_test.py --module` as
the verification path. This is the load-bearing change: the brief is the only
thing a worker reliably reads.

**Snapshot (FR-002).** New `src/tenx/install_health.py` with
`snapshot_host_install()` returning `{"tenx_source", "python"}` from
`importlib`/`sys`. Dispatch writes it into the receipt alongside the existing
lifecycle fields, on both the visual and headless paths. Recording before
launch is what makes the teardown comparison meaningful.

**Teardown check (FR-003).** `check_host_install(snapshot)` returns `None`
when the current source still matches, and a warning dict when the snapshot
pointed at a path that no longer exists or when the current source moved.
`reconcile_subagent_ticket` and `abort_subagent_ticket` call it after
`_remove_worktree_and_branch` and set `ReconcileResult.host_install_warning`;
the CLI prints it. The status stays `merged`/`aborted`: the work landed, and
the host repair is the operator's explicit call.

**Doctor (FR-004).** Add a check to `cmd_doctor` that reports when the
resolved tenx source sits under `.tenx/worktrees/`, reusing the same helper
so the wording and recovery command cannot drift between the two surfaces.

## Alternatives considered

- Sandboxing the worker process so it cannot write outside the worktree.
  Rejected: the stdlib-only, zero-dependency constraint (CON-002) rules out a
  container, and a contract plus a detector is proportionate to the failure
  (a discarded worktree and a repairable install, not data loss).
- Auto-repairing the install at teardown. Rejected: replacing a host-level
  tool without being asked is a bigger action than the problem.
- Detecting inside the worker before it finishes. Rejected: a worker that has
  already broken the install may not survive to report, and the parent can
  always be trusted to check.
- Recording only the worktree path instead of the resolved install source.
  Rejected: the failure is a *host* pointer, so the host's resolution is the
  thing to compare.

## Cross-cutting concerns

- **Security:** the change reduces blast radius; it grants no new capability
  and runs no worker code.
- **Backward compatibility:** the receipt gains an optional field and
  `ReconcileResult` an optional one; receipts written by older versions have
  no snapshot and are treated as "nothing to compare" rather than an error.
- **Observability:** the warning is carried in the reconcile result, printed
  by the CLI, and written to the activity log, so the operator sees it in the
  command they just ran rather than having to look for it.
- **Testing:** smoke coverage for the brief text, the receipt snapshot, the
  teardown warning, and the doctor check.

## Tickets

- [ ] SPC-038-T1: Forbid host-environment mutation in the dispatched worker brief (FR-001)
- [ ] SPC-038-T2: Record the host install snapshot in the dispatch receipt (FR-002)
- [ ] SPC-038-T3: Verify the host install during reconcile and abort teardown (FR-003)
- [ ] SPC-038-T4: Report a worktree-scoped install source from tenx doctor (FR-004)

## Validation

- FR-001: Given the ticket brief, When it is generated, Then it names the
  forbidden install commands and the worktree-local verification command.
- FR-002: Given a dispatch receipt, When it is read, Then `host_install`
  carries the resolved source path.
- FR-003: Given a receipt whose snapshot path no longer exists, When teardown
  runs, Then the result carries `host_install_warning` with a recovery command
  and the status is still `merged`.
- FR-004: Given a tenx source under `.tenx/worktrees/`, When `tenx doctor`
  runs, Then the problem is reported with a recovery command.
- Suite: `python3 tests/smoke_test.py` and `python3 tests/smoke_test.py --module`
  both pass; `tenx validate` reports 0 errors; `tenx converge SPC-038` reports
  CONVERGED.

## Open questions

- None.
