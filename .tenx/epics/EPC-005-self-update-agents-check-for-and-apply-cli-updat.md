---
id: EPC-005
type: epic
title: "Self-update: agents check for and apply CLI updates"
status: complete
created: 2026-08-25
updated: 2026-08-25
specs:
  - SPC-009
---

## Objective

Ensure agents and operators working across multiple repositories always have access to the latest tenx CLI features, bug fixes, and enforcement capabilities. Provide non-blocking update checks at session start and seamless in-place self-updates via `tenx update`.

## Key results

- KR1 — `tenx update --check` checks upstream GitHub Releases (or repo pyproject.toml) without blocking or failing when offline.
- KR2 — `tenx update` performs in-place upgrades detecting uv vs pipx installation methods.
- KR3 — Session-start protocols across AGENTS.md, context packets, and skills instruct agents to check for updates.

## Scope

- CLI command `tenx update [--check] [--json]`.
- Upstream version resolution via GitHub Releases and raw pyproject.toml.
- Environment detection for `uv tool` and `pipx`.
- Agent instruction surfaces wiring `tenx update --check` into session start.

## Non-goals

- Automatic unattended background updates without operator confirmation.
- Modifying OS-level system package managers (apt, pacman, brew).

## Milestones

- [x] M1 — Implement `tenx update` command with `--check` flag and GitHub Releases version check (SPC-009).
- [x] M2 — Wire session-start awareness into context packets, bootstrap snippets, and agent templates (SPC-009).
