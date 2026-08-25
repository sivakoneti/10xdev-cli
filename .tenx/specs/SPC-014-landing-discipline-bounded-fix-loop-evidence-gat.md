---
id: SPC-014
type: spec
title: Landing discipline (bounded fix loop + evidence gate)
status: complete
epic: EPC-007
created: 2026-08-25
updated: 2026-08-25
priority: P2
tickets:
  - id: SPC-014-T1
    title: tenx-review skill landing discipline
    status: done
  - id: SPC-014-T2
    title: tenx-process skill landing discipline
    status: done
  - id: SPC-014-T3
    title: README + smoke checks
    status: done
---

## Summary

Encode a landing discipline into the bundled `tenx-review` and `tenx-process`
skills: evidence before done, a bounded 2-cycle fix loop, and a human gate on
the final merge. The caller who benefits is any agent finishing work — it gets
an explicit rulebook that prevents infinite review loops and "trust me, it
works" completions.

## Context and scope

High-throughput agent shops land PRs with a bounded review/fix loop, require
verification evidence, and keep a human approval gate. tenx's review skill
told agents to land or bounce but did not bound the loop or require evidence.
Scope: skill-text changes (no new CLI surface). Out of scope: enforcing the
loop in code (it is judgment, best taught as guidance).

## Goals / non-goals

Goals:
- `tenx-review` skill: bounded fix loop (max 2 cycles then escalate),
  evidence gate (validate passes + spec Validation satisfied), human landing
  gate, verify-like-a-user.
- `tenx-process` skill: evidence before done + bounded loop + human lands it.
- README documents the discipline; smoke checks lock the skill text.

Non-goals:
- Hard-enforcing cycle counts or evidence in the CLI.

## Design

Skill-text edits in `templates.py`. The review skill gains a "Landing
discipline" section; the process loop gains a matching block at the validate
step. Kept as guidance rather than code because "has this bounced twice /
is this real evidence" is judgment an agent must make, not a lint rule.

## Alternatives considered

A `tenx land` command that mechanically enforces the loop was considered and
rejected for now: landing decisions are context-heavy, and over-coding them
would fight the human. Skill guidance is the lighter, reversible choice.

## Cross-cutting concerns

No runtime behavior change; only agent-facing text. Testing: smoke checks
assert the skill files teach the bounded loop, evidence gate, and human gate.

## Tickets

- SPC-014-T1 tenx-review skill landing discipline — done
- SPC-014-T2 tenx-process skill landing discipline — done
- SPC-014-T3 README + smoke checks — done

## Validation

- `tenx skills install` writes skills containing "Bounded fix loop",
  "Evidence gate"/"Evidence before done", and a human gate.
- `python3 tests/smoke_test.py` and `--module` both pass.

## Open questions

- None.
