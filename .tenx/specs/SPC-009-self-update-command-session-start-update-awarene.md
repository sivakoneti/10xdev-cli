---
id: SPC-009
type: spec
title: Self-update command + session-start update awareness
status: complete
epic: EPC-005
created: 2026-08-25
updated: 2026-08-25
tickets:
  - id: SPC-009-T1
    title: "tenx update command (check/upgrade, offline-safe)"
    status: done
  - id: SPC-009-T2
    title: session-start update awareness (protocol/AGENTS/bootstrap/skill)
    status: done
  - id: SPC-009-T3
    title: README Updating section
    status: done
  - id: SPC-009-T4
    title: smoke checks for update + awareness
    status: done
---

## Summary

tenx is installed per-user/per-project as a standalone CLI. When the
10xdev codebase ships new features, existing installs do NOT pick them up
automatically, and — because tenx is agent-facing — the agents driving it
have no way to know a newer version exists. This spec adds a self-update
capability and makes agents aware of it at session start.

Two halves:

1. **`tenx update` command.** Checks the upstream repo for a newer version
   and (optionally) upgrades in place using the installer that performed
   the original install (uv / pipx). Version source is the GitHub Releases
   API, with a fallback to `pyproject.toml` on the default branch so the
   check works before any formal release is published. The check is
   offline-tolerant: a network failure never crashes or blocks an agent.

2. **Session-start update awareness.** Every surface an agent loads at
   session start tells it the CLI self-updates and to run
   `tenx update --check`: the operating protocol in the context packet, the
   AGENTS.md managed block, the harness-agnostic bootstrap snippet, and the
   bundled `tenx-process` skill. Agents check (non-mutating), notify the
   human if a newer version exists, and only apply with `tenx update`.

## Design decisions

- `tenx update --check` is non-mutating and always exits 0 (a failed check
  prints a note, never a traceback) so it is safe to run at session start.
- `tenx update` performs the upgrade; `--yes` is implicit for the upgrade
  path but the command prints exactly what it will run first.
- `--json` on both for machine-readable output.
- No network call is added inside `tenx context` / `hook emit` / MCP: those
  stay offline-safe and fast. The update check is a discrete command the
  protocol instructs the agent to run.
- Upgrade is best-effort: detect uv vs pipx, run the matching
  `<installer> upgrade tenx`; if unknown, print manual instructions.

## Validation

- `tenx update --check` exits 0 offline and with no releases (no traceback).
- Version parse/compare logic is unit-checked in the smoke suite.
- The agent packet, AGENTS.md block, bootstrap snippet, and process skill all
  mention the self-update check.
- README has an "Updating" section.
