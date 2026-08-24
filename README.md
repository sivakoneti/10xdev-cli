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

### Works with any agent harness

tenx is harness-agnostic by contract: the context base is plain markdown
files and the tooling is one shell command that prints text. Any harness
with a terminal tool can use 100% of it.

The harness layer follows OpenDesign's agent-adapter architecture
(`docs/agent-adapters.md`): **adapters are data, not code**. Each harness
is one declarative record in `src/tenx/adapters.py` (bins to probe,
auto-loaded instruction files, hook mechanism, skills dir); a generic
engine installs and detects from those fields. Adding a harness is a
one-entry change — no engine edits.

```bash
tenx hook detect              # probe PATH for ~29 known harnesses
tenx hook detect --json
tenx hook install --agent detected   # wire only what's installed
tenx hook install --agent hermes     # or any single adapter id
tenx hook install --agent all        # every file-based target
```

Injection tiers:

1. **Forced hook** — the harness runs a command at session start and
   injects stdout: Claude Code (`.claude/settings.json` SessionStart).
   Any harness with an equivalent hook mechanism just needs to run
   `tenx context --mode agent`.
2. **Auto-loaded instruction files** — the adapter catalog covers:
   claude, codex, opencode, cursor, gemini, cline, windsurf, copilot,
   continue, aider, amp, qoder, qwen, grok, deepseek, deepseek-harness
   (dsh), prime-agent, omp (Oh My Pie), antigravity (agy), devin,
   hermes, kimi, kiro, kilo, vibe, vela, trae, pi, generic.
3. **Universal bootstrap** — for anything else: paste the output of
   `tenx hook bootstrap` into the harness's system prompt / custom
   instructions. That block is the entire integration; it only assumes
   the agent can run shell commands. Even with nothing installed, an
   agent can always run `tenx context --mode agent` on demand.

### Alternative: standalone PM repo (the 10X layout)

10X keeps their artifacts in a dedicated *project management repo*, separate
from the code repos. tenx supports that layout first-class:

```bash
mkdir my-project-pm && cd my-project-pm && git init
tenx init --standalone --code-root /path/to/code-repo --bootstrap
tenx hook install --agent all      # hooks + AGENTS.md land in the CODE repo
```

Wiring: the harness config records `code_root:`; the code repo gets a
`.tenxlink` pointer file back to the PM repo. From inside the code repo,
every `tenx` command resolves the harness through the link automatically.
Co-located (`.tenx/` inside the code repo) remains the default.

### Multiplayer: share the harness

The context base and the skills are plain git-trackable markdown:

- Commit `.tenx/` (or the standalone PM repo) and review it in PRs — the
  team's context compounds instead of living in individual chat histories.
- Team skill channels: clone a shared skills repo and run
  `tenx skills install --target <shared-repo>/skills`; good skills get
  merged into main, mirroring 10X's "channels merged into main" workflow.
- The activity log (`tenx history`) records who/what did what, human or
  agent, so overnight runs leave an audit trail.

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
tenx scan [--json] [--write]     # map the codebase; --write stores it as a DOC
tenx skills list|install [--target DIR]
tenx hook [--mode agent]         # emit the packet (used by the SessionStart hook)
tenx hook install --agent <id|all|detected>  # see `tenx hook detect`
tenx doctor                      # health check
```

### Onboard an existing codebase in one command

`tenx scan` walks the governed code repo and reports stacks, entry-point
hints, test setup, CI, existing agent instruction files, and a top-level
directory census. `tenx scan --write` upserts that map as a DOC artifact
tagged `codebase-map`, so a fresh project goes from zero to briefed in
one command and every later session starts with the map in the packet.

```bash
tenx init --bootstrap
tenx scan            # read the map
tenx scan --write    # store it as .tenx/docs/DOC-xxx-codebase-map.md
```

### Spec-first autonomous execution

Write the spec (3–4 hours of markdown, per the video), then hand the agent
an execution brief:

```bash
tenx exec SPC-001 | claude -p     # headless overnight run
tenx exec SPC-001                 # or paste into an interactive session
```

The brief tells the agent to work ticket by ticket, write back every state
change (`tenx ticket`, `tenx log`), validate before finishing, and commit
both repos. `tenx ticket` creates tickets on first touch, so agents can grow
a spec's ticket list as they discover work.

All read commands support `--json` for machine consumption. Discovery
order: `TENX_ROOT` env > `.tenx/` walking up > `.tenxlink` walking up >
`.git` > cwd.

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
