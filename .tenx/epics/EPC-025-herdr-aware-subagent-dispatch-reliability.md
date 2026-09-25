---
id: EPC-025
type: epic
title: Herdr-aware subagent dispatch reliability
status: complete
created: 2026-09-25
updated: 2026-09-25
---

## Objective

Make Herdr-backed subagent dispatch reliable for supervisors and workers. A supervisor must be able to discover the correct Herdr API, start an agent in an isolated pane, submit work safely, observe its lifecycle, and diagnose launch failures without silently reporting success.

## Key results

- KR1 — The bundled `tenx-dispatch` skill requires the Herdr skill and gives supervisors an executable Herdr-first dispatch protocol.
- KR2 — A live Herdr dispatch reports creation, launch, and lifecycle errors as failures instead of returning a false success receipt.
- KR3 — Both smoke modes and focused Herdr dispatch scenarios pass with regression coverage for the broken paths.

## Scope

- Herdr skill integration in the bundled and installed dispatch skill.
- Correct Herdr workspace/pane command construction, JSON parsing, launch verification, and lifecycle supervision.
- Regression coverage and user-facing dispatch documentation.

## Non-goals

- Replacing Herdr's server, protocol, or agent runtime.
- Changing unrelated headless adapters or tmux behavior.
- Automatically answering blocked approval/question dialogs.

## Milestones

- [ ] M1 — Specify the Herdr-first dispatch contract and capture the confirmed failures.
- [ ] M2 — Implement skill, projection, and lifecycle reliability fixes with regression tests.
- [ ] M3 — Validate the live Herdr path and complete the evidence gate.

