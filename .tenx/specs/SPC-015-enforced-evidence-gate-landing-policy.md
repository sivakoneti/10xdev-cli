---
id: SPC-015
type: spec
title: Enforced evidence gate (landing policy)
status: complete
epic: EPC-008
priority: P0
created: 2026-08-25
updated: 2026-08-25
tickets:
  - id: SPC-015-T1
    title: gate logic + --force + evidence field
    status: done
  - id: SPC-015-T2
    title: wire gate into cmd_set + config flag
    status: done
  - id: SPC-015-T3
    title: README + landing-skill update + smoke checks
    status: done
---

## Summary

Enforce the landing policy tenx already teaches: `tenx set <ID> status
complete` for a spec or epic is blocked unless (a) validation has no errors on
that artifact, (b) for a spec, all its tickets are done, and (c) evidence is
linked — an `evidence:` field or a substantive activity-log entry with
`--ref <ID>`. A `--force` flag is the explicit human override. Controlled by
config `evidence_gate: on|off` (default on). The caller who benefits is any
team that needs "done" to mean verified, not self-declared.

## Context and scope

SPC-014 encoded the landing discipline (bounded fix loop + evidence gate +
human gate) as skill guidance only — `cmd_set` had no guard. This spec makes
the evidence gate real policy. Scope is the `status complete` transition for
spec/epic; ticket-level completion stays ungated to keep friction low.

## Goals / non-goals

Goals:
- Block `status complete` without clean validation + linked evidence.
- Provide `--force` human override and a config off-switch.
- Add `evidence` as a settable, free-form field.

Non-goals:
- Gating ticket `done`, archive, or sync write-back.
- Verifying the evidence is *true* (tenx checks presence, not correctness).

## Design

New `src/tenx/gate.py` with `check_evidence_gate(root, harness, art, ruleset)
-> (ok, reasons)`. It reuses `rules.validate` for per-artifact errors,
`Artifact.tickets` for the all-done check, and `activity.read_entries` for
evidence (types progress/review/decision/note). `cmd_set` calls the gate only
when `field=="status"`, `value=="complete"`, `art.type in (spec, epic)`, the
gate is enabled, and `--force` is absent. `evidence` joins `SETTABLE_FIELDS`
(free-form). This wins because it enforces policy at the exact landing moment
with zero new storage and a clean escape hatch.

## Alternatives considered

- Gate every status change: rejected — too much friction; only landing matters.
- Require an explicit `evidence:` field only: rejected — a logged `--ref`
  entry is already strong evidence and matches the existing write-back loop.
- Default the gate off: rejected — enforcement is the point; `--force`/config
  provide the escape.

## Cross-cutting concerns

- Backward compatibility: default-on changes `set ... complete` behavior;
  `--force` and `evidence_gate: off` are the documented overrides. Existing
  already-complete artifacts are untouched (gate fires only on new transitions).

## Tickets

- SPC-015-T1 gate logic + --force + evidence field
- SPC-015-T2 wire gate into cmd_set + config flag
- SPC-015-T3 README + landing-skill update + smoke checks

## Validation

- `tenx set <spec> status complete` with no evidence -> exit 2, "evidence gate
  blocked", reasons listed.
- After `tenx log "x" --ref <spec>` (or `tenx set <spec> evidence "..."`) the
  same command succeeds.
- `--force` bypasses with a warning; `evidence_gate: off` disables.
- Offline smoke checks cover block/pass/force/config; full suite green.

## Open questions

- None.
