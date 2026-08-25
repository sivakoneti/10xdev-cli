---
id: SPC-019
type: spec
title: DSH agent preset — persona-mandated tenx loop
status: complete
epic: EPC-011
created: 2026-08-25
updated: 2026-08-25
tickets:
  - id: SPC-019-T1
    title: tenx preset template (persona + gates) in templates.py
    status: done
  - id: SPC-019-T2
    title: tenx hook install --agent dsh writes a mountable preset
    status: done
  - id: SPC-019-T3
    title: preset persona mandates tenx validate must pass + landing gate
    status: done
  - id: SPC-019-T4
    title: "smoke: dsh preset generated + persona content"
    status: done
---

## Summary

Ship tenx as a DSH agent preset so the DeepSeek Harness guarantees tenx
compliance instead of hoping the agent reads AGENTS.md. DSH presets are
mounted by the harness runtime into the agent's persona/tools, so the mandate
becomes the agent's identity — the production-grade pattern observed in the
acqos preset ("qa.py must pass", "DO NOT SEND until operator approves").

## Context and scope

DSH (`~/.dsh/.agent-presets/<name>/`) presets compose `preset.yml` (metadata)
+ `agent.cordis.yml` (persona, tools, skills). tenx currently gives dsh only
an advisory AGENTS.md (adapter `deepseek-harness`). We add a preset generator
that emits a mountable `tenx/` preset whose persona hard-mandates the loop.

## Goals / non-goals

Goal: `tenx hook install --agent dsh` (and init) emit a ready-to-mount preset.
Non-goal: owning DSH's runtime; we only emit the declarative preset files.

## Design

- `templates.py`: `DSH_PRESET_META` (preset.yml) + `DSH_PRESET_CORDIS`
  (agent.cordis.yml) with a `persona` section mandating: run `tenx context
  --mode agent` at session start; before calling work done, `tenx validate`
  must pass and the spec needs evidence; never archive/merge without operator
  sign-off; write back with `tenx log ... --ref <ID>`.
- `adapters.py`: extend the `deepseek-harness` adapter with a preset hook so
  `install` writes `.dsh-agent-presets/tenx/` (project-local) for the user to
  mount, alongside AGENTS.md.
- Persona uses `{{model}}`/`{{cwd}}` placeholders DSH resolves at mount.

## Alternatives considered

Keep dsh advisory-only (rejected: that is exactly the gap being closed).
Inject via AGENTS.md only (rejected: weaker than a mounted persona).

## Validation

- `tenx hook install --agent dsh` writes preset.yml + agent.cordis.yml.
- The cordis persona contains the mandatory-gate language.
- Smoke asserts both files + persona content.
