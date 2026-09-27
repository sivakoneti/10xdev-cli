---
id: EPC-028
type: epic
title: Host environment safety for dispatched workers
status: complete
priority: P1
created: 2026-09-27
updated: '2026-09-27'
---

## Objective

Isolation is the whole basis on which automatic delegation is safe, and today
it only isolates the *filesystem the worker writes to*. A worker can still
reach the host tool environment: dogfooding a live Herdr dispatch showed a
worker running an install from inside `.tenx/worktrees/SPC-037-T1`, which
re-pointed the operator's global `tenx-cli` at that worktree's `src`. When
`tenx reconcile` removed the worktree, the host CLI died with
`ModuleNotFoundError: No module named 'tenx'` — the operator lost their tool
with no error and no recovery hint, because the broken tool was the thing
that should have reported the problem. This epic makes worktree isolation
hold for the host environment too: the worker is told not to touch it, the
harness records what the host install looked like before the worker ran, and
teardown checks that assumption and says how to recover if it broke.

## Key results

- **KR1**: The ticket brief handed to every dispatched worker forbids
  package-manager installs and host tool-environment mutation, and names the
  worktree-local verification command (`python3 -m tenx`, `python3
  tests/smoke_test.py --module`) that a worker must use instead, so 0
  dispatched workers receive a brief that permits a global install.
- **KR2**: Every visual and headless dispatch receipt records the host
  install's resolved source path, so teardown can compare against what the
  worker was launched with instead of guessing.
- **KR3**: `tenx reconcile` and `tenx abort` verify the host install after
  removing the worktree and, when it was hijacked, report the exact recovery
  command — with 0 teardowns that remove a worktree without checking the host
  install it may have broken.
- **KR4**: `tenx doctor` reports when the running tenx resolves inside a
  `.tenx/worktrees/` path, so an operator can see a hijacked install instead
  of discovering it as a missing module.

## Scope

- The ticket brief text handed to dispatched workers.
- A host-install snapshot recorded in the dispatch receipt, and a health
  check that runs during teardown.
- Recovery instructions naming the real install command for the detected
  installer.
- A `tenx doctor` check for a worktree-scoped install source.

## Non-goals

- Sandboxing the worker process. This is a contract plus a detector, not a
  jail; a worker that ignores the brief is detected at teardown, not blocked
  mid-run.
- Automatically repairing a hijacked install. Recovery stays an explicit
  operator action, because it replaces a host-level tool.
- Changing the landing gate, the reconcile workflow, or the isolation model
  for the worker's own files.
- Removing the ability to install tenx from a checkout; that is a legitimate
  developer action outside a dispatched worker.

## Milestones

- [ ] M1: The brief forbids host-environment mutation and names the
      worktree-local verification path (KR1).
- [ ] M2: Dispatch records the host install snapshot in the receipt (KR2).
- [ ] M3: Reconcile and abort verify the host install at teardown and emit
      recovery instructions when it broke (KR3).
- [ ] M4: `tenx doctor` surfaces a worktree-scoped install source (KR4).
