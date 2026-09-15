---
id: EPC-008
type: epic
title: Enterprise wedge — enforced gates + triage agent
status: complete
priority: P0
created: 2026-08-25
updated: 2026-08-25
---

## Objective

Give an enterprise platform team two concrete reasons to pilot tenx as its
agent-coordination layer. First, a **trust primitive tenx can lead on**: an
enforced landing policy, so no agent can mark a spec/epic `complete` without
clean validation and linked evidence. Second, a **flagship demonstration of
value**: a Triage agent role that reads the project pulse, ranks what needs
attention, and hands a human the single most important escalation. Together
they turn tenx's "engineering-manager layer" story from guidance into
enforced, demonstrable machinery.

## Key results

- KR1 — `tenx set <spec|epic> status complete` is blocked without evidence;
  an explicit `--force` human override exists; covered by offline smoke checks.
- KR2 — `tenx triage` emits a ranked escalation report (act-now / watch /
  healthy + one human escalation), exposed as CLI, MCP tool, and installable
  `tenx-triage` agent-role skill.
- KR3 — Both features documented in README; full smoke suite green in CLI and
  module mode; `tenx validate` clean.

## Scope

- Enforced evidence gate in `cmd_set` (spec/epic -> complete), config flag,
  `--force` override, `evidence` settable field.
- `tenx triage` command + `triage.py` over `compute_watchdog`, MCP tool,
  `tenx-triage` agent-role skill.
- README + landing-skill documentation and offline smoke checks.

## Non-goals

- Identity/SSO, RBAC/ACLs, database backend, pluggable sync adapters,
  sandboxing, model-cost metering — separate epics or not tenx's layer.
- A new model/engine. tenx stays agent-agnostic; the triage role runs on the
  enterprise's own runtime.

## Milestones

- [x] M1 — enforced evidence gate (SPC-015)
- [x] M2 — triage command + agent role (SPC-016)
