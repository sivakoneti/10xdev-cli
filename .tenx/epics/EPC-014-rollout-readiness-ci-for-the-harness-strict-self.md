---
id: EPC-014
type: epic
title: Rollout readiness — CI for the harness + strict self-enforcement
status: complete
created: 2026-08-26
updated: 2026-08-26
specs:
  - SPC-024
---

## Objective

Establish complete automated CI verification and strict self-enforcement for the tenx repository itself. Enable commit-gate enforcement on all commits and run smoke test suites across supported Python versions (3.10, 3.11, 3.12) to ensure release readiness.

## Key results

- KR1 — GitHub Actions CI matrix running smoke tests across Python 3.10, 3.11, and 3.12 on pull requests and pushes.
- KR2 — Strict `commit_gate: on` activated for tenx development.
- KR3 — Zero regressions on cross-version Python runtime compatibility.

## Scope

- GitHub Actions workflow configuration (`.github/workflows/ci.yml`).
- Harness configuration enabling `commit_gate: on` in `.tenx/config.yaml`.
- Compatibility fixes for Python 3.10 ISO timestamp parsing.

## Non-goals

- Supporting legacy Python versions below 3.10.
- Setting up external package publishing automations outside standard release flows.

## Milestones

- [x] M1 — Create GitHub Actions CI workflow covering Python 3.10, 3.11, and 3.12 (SPC-024).
- [x] M2 — Activate strict commit-gate in tenx configuration (SPC-024).
- [x] M3 — Fix py3.10 git timestamp parsing and verify CI green (SPC-024).
