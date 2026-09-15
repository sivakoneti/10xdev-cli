---
id: SPC-017
type: spec
title: Concurrency-safe harness state
status: complete
epic: EPC-009
created: 2026-08-25
updated: 2026-08-25
tickets:
  - id: SPC-017-T1
    title: "locking.py: harness_lock + atomic_write_text"
    status: done
  - id: SPC-017-T2
    title: "main(): serialize mutating commands behind the lock"
    status: done
  - id: SPC-017-T3
    title: atomic writes for artifact/index/skill/hook files
    status: done
  - id: SPC-017-T4
    title: gitignore .lock + concurrency smoke checks
    status: done
---

## Summary

Make `.tenx` state safe for a fleet of agents running tenx concurrently against
the same project. Today there is no locking anywhere: two processes doing
read-modify-write on the same markdown artifact, or appending to the same
`activity.jsonl`, can lose or corrupt writes. This spec adds a per-project
advisory lock that serializes every mutating command, plus atomic
write-then-rename for state files so a reader never sees a torn file.

## Context and scope

The enterprise-readiness analysis flagged concurrency as the most acute gap for
the "manage many agents" story. Scope is the locking + atomic-write layer only.
Identity, tamper-evident audit, pluggable backends, and ACLs are separate specs
under EPC-009. Stdlib only (CON-002 zero runtime dependencies): POSIX `fcntl`
with a best-effort no-op fallback where unavailable.

## Goals / non-goals

Goals:
- One exclusive advisory lock per project (`.tenx/.lock`) held for the whole of
  each mutating command, so read-modify-write cycles are atomic.
- `flock`-based, so a crashed tenx releases the lock automatically (no stale
  lockfiles). Bounded wait with a clean `LockTimeout` error, not a traceback.
- Atomic replacement (write temp + `os.replace`) for artifact/index/skill/hook
  files so partial writes never land.
- Mutating commands covered: init, new, set, ticket, log, archive, hook,
  skills, sync, validate.

Non-goals:
- Fine-grained per-file locks (coarse global lock is correct and simpler).
- Changing read-only commands (context/status/show/list/next/watchdog/triage).
- Distributed/multi-host locking (single-host advisory lock only).

## Design

- New `src/tenx/locking.py`: `harness_lock(root, timeout)` context manager
  using `fcntl.flock(LOCK_EX | LOCK_NB)` in a poll loop against `.tenx/.lock`;
  `atomic_write_text(path, text)` writes to a same-dir temp file then
  `os.replace`. `LockTimeout` raised on deadline.
- `cli.main()` wraps `args.func(args)` in the lock when the subcommand is in
  `MUTATING_COMMANDS` and the harness is initialized; `LockTimeout` prints a
  clean message and exits 2.
- Swap `write_text` for `atomic_write_text` in artifacts (create/update),
  convention-index rebuild, skills install, and hook installs.

## Alternatives considered

- Per-file locks: rejected — multi-file commands (set -> artifact + log) would
  not be atomic, and lock ordering invites deadlocks.
- PID lockfiles: rejected — stale after a crash; `flock` is auto-released.
- A SQLite backend: deferred to a later EPC-009 spec; overkill for this fix.

## Cross-cutting concerns

- Zero new dependencies (CON-002). Windows has no `fcntl`; the lock degrades to
  a documented no-op there (best-effort, matching the repo's Windows stance).
- `.tenx/.lock` is gitignored so the runtime lockfile is never committed.

## Tickets

- SPC-017-T1 locking.py: harness_lock + atomic_write_text
- SPC-017-T2 main(): serialize mutating commands behind the lock
- SPC-017-T3 atomic writes for artifact/index/skill/hook files
- SPC-017-T4 gitignore .lock + concurrency smoke checks

## Validation

- `python3 tests/smoke_test.py` and `--module` pass, including new checks:
  concurrent `tenx log` appends lose no entries; concurrent `tenx set` leaves a
  valid artifact; `atomic_write_text` yields intact content; lock times out
  cleanly when held.
- `tenx validate`: 0 errors.

## Open questions

- None blocking. Multi-host locking is explicitly out of scope.
