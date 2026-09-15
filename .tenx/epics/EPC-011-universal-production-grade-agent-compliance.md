---
id: EPC-011
type: epic
title: Universal production-grade agent compliance
status: complete
created: 2026-08-25
updated: 2026-08-25
---

## Objective

Make tenx compliance hold at production grade across EVERY agent harness —
not just the ones that happen to read a file. Today tenx writes an advisory
AGENTS.md; an agent can simply ignore it (demonstrated when the agent that
builds tenx skipped tenx in tenx's own repo). The user running DSH, Claude
Code, prime-agent, antigravity, omp, hermes, pi, etc. needs a guarantee that
shipped work followed the process. The fix is defense in depth: inject the
mandate at the strongest layer each harness offers, and back it with a
git-layer gate that no harness can bypass.

## Key results

- KR1 — DSH users can mount a `tenx` agent preset whose persona mandates the
  tenx loop (`tenx validate` must pass before work is done; no archive/merge
  without operator sign-off).
- KR2 — `tenx hook install --git` installs a pre-commit hook that runs
  `tenx validate` and blocks the commit on errors — enforced by git, below
  any agent, so it works on every harness identically.
- KR3 — The managed instruction block is hardened from "context" to
  "mandate" (HARD RULES persona language) so even advisory-file harnesses get
  strong instructions; forced tiers (claude SessionStart, prime-agent system
  prompt, omp --append-system-prompt) are documented per adapter.
- KR4 — `tenx init` wires all of the above by default in a git repo, so a
  fresh project is production-grade out of the box.

## Scope

- DSH agent preset generation (persona + mandatory gates).
- Git pre-commit enforcement (`tenx hook install --git`), wired into init.
- Hardened universal mandate block + per-harness forced-tier wiring/docs.
- Smoke coverage for each mechanism.

## Non-goals

- Controlling each harness's internal system-prompt injection (tenx cannot
  own another runtime's prompt); we use the strongest lever each exposes.
- A CI/CD-hosted gate (GitHub Action) — proposed follow-up, not this epic.
- Rewriting the adapter registry; we extend it data-only.

## Milestones

- [ ] M1 — SPC-019 DSH preset installable + mountable.
- [ ] M2 — SPC-020 git pre-commit gate blocks non-compliant commits.
- [ ] M3 — SPC-021 hardened mandate block + forced-tier docs; init wires all.
