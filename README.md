# tenx — meta-harness: context-as-code for AI coding agents

> "The percentage of time you spend engineering the markdown should be higher
> than the time you spend executing the code." — the 10X team

`tenx` turns any project into a **context base**: a structured packet of
markdown artifacts that keeps AI coding agents briefed, on-rails, and
accountable across sessions. It implements the "meta-harness" pattern
described by the 10X team (Alex Lieberman & Dan, David Ondrej podcast):

- **Context as code.** Epics, specs, conventions, and docs live as
  structured markdown with parseable frontmatter — in git, reviewed like
  code, more valuable than the code itself.
- **Benevolent prompt injection.** Every agent session boots with the exact
  right context packet via a session-start hook, so each session starts like
  a senior engineer on the project.
- **Linting for the SDLC.** `tenx validate` compares authored state against
  derived state (ticket progress vs claimed status, broken refs, stale
  artifacts) and reports drift — hundreds-of-rules style, self-correctable
  by the agent.
- **Write-back loop.** Agents log activity, move tickets, and re-validate,
  leaving a full trail of what happened and why.

Works on any project. Zero runtime dependencies (Python 3.10+ stdlib;
uses PyYAML if present).

## Install

```bash
uv tool install /path/to/10xdev        # or: pipx install /path/to/10xdev
tenx --version
```

## Quick start (any project)

```bash
cd your-project
tenx init --bootstrap                  # scaffold .tenx/ + seed starter docs
tenx new epic "Ship the billing system"
tenx new spec "Billing API" --epic EPC-001
tenx hook install --agent claude       # or codex / opencode / gemini / all
tenx skills install                    # one skill per artifact type + process
```

From then on, every Claude Code session in the project starts with the full
context packet injected, and Codex/OpenCode/Gemini agents are instructed via
a managed `AGENTS.md` block to run it.

## The artifact types

| Type | ID | Purpose |
|------|----|---------|
| epic | `EPC-001` | What we are building + milestones to get there |
| spec | `SPC-001` | Detailed technical plan, ticket by ticket |
| convention | `CON-001` | Rules that keep agents on rails (indexed in `conventions/INDEX.md`) |
| doc | `DOC-001` | Architecture, decisions, external systems, anything an agent might need |

Every artifact is markdown with YAML frontmatter:

```yaml
---
id: SPC-001
type: spec
title: Billing API
status: in_progress
epic: EPC-001
created: 2026-08-24
updated: 2026-08-24
tickets:
  - id: SPC-001-T1
    title: Add /api/invoices endpoint
    status: done
  - id: SPC-001-T2
    title: Stripe webhook handler
    status: in_progress
---
```

## Command reference

```bash
tenx init [--bootstrap]          # scaffold .tenx/ in this project
tenx context --mode operator     # human dashboard
tenx context --mode agent        # full session-start context packet
tenx status                      # alias for the operator dashboard
tenx new <epic|spec|convention|doc> "Title" [--epic EPC-001]
tenx show <ID> [--json]          # full artifact, metadata + body
tenx list [type] [--json]
tenx set <ID> status in_review   # update metadata (status/owner/epic/title/tags)
tenx ticket SPC-001 SPC-001-T2 done
tenx validate [--fix] [--json]   # lint the SDLC; --fix rebuilds the convention index
tenx log "implemented webhook handler" --ref SPC-001 --type progress
tenx history [--limit 20] [--json]
tenx next [--json]               # prioritized work queue (the self-improving loop)
tenx skills list|install [--target DIR]
tenx hook [--mode agent]         # emit the packet (used by the SessionStart hook)
tenx hook install --agent claude|codex|opencode|gemini|all
tenx doctor                      # health check
```

All read commands support `--json` for machine consumption. `TENX_ROOT`
overrides project discovery; otherwise `tenx` walks up from cwd looking for
`.tenx/` (then `.git`).

## The agent loop

`tenx next` derives the highest-value action, in this order:

1. fix validation errors
2. reconcile drift (authored vs derived status)
3. review specs sitting in `in_review`
4. implement the next open ticket in active specs
5. write specs for draft epics
6. (nothing queued → create an epic)

Install the bundled `tenx-process` skill (`tenx skills install`) and agents
run this loop autonomously: brief → pick → load context → work → write back →
validate.

## Validation rules

`tenx validate` ships with: frontmatter parse/required-field checks, id
format & uniqueness, status vocabulary, epic references, ticket status &
uniqueness, **derived-status drift** (a spec claiming `complete` while
tickets are open — the checkpoint rule), epic progress drift, convention
index sync, stale in_review artifacts, non-monotonic dates, and a quiet
activity-log notice.

Override in `.tenx/rules.yaml`:

```yaml
disable:
  - log-quiet
severity:
  - stale-artifact: warning
params:
  stale_days: 21
```

## Layout created by `tenx init`

```
.tenx/
  config.yaml        # project identity + rule params
  README.md          # harness guide
  epics/             # EPC artifacts
  specs/             # SPC artifacts
  conventions/       # CON artifacts + INDEX.md
  docs/              # DOC artifacts
  log/activity.jsonl # append-only agent activity log
```

## Philosophy

- The codebase says *what exists*; the harness says *why it exists, what we
  build next, and how work must be done*. You should be able to rebuild the
  product from the context repo alone.
- Agents are great at consistency and structure; humans at the first and
  final mile. Give the agents the things they're great at — including
  holding the process accountable via `tenx validate`.
- Minimize entropy and diversion from plan while keeping agent speed.
