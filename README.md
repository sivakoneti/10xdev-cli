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

## Updating

tenx is installed per machine as a standalone CLI, so existing installs do
not pick up new features on their own. It ships with a self-update command:

```bash
tenx update --check        # report whether a newer version exists (no change)
tenx update                # check, then upgrade in place via uv/pipx
tenx update --check --json # machine-readable
```

The check reads the upstream repo (GitHub Releases, falling back to
`pyproject.toml` on the default branch) and is offline-tolerant: a failed
check prints a note and exits 0, it never crashes. The upgrade detects the
installer (`uv tool` vs `pipx`) and runs the matching upgrade command; if it
cannot detect one it prints manual instructions.

Because tenx is agent-facing, the session-start surfaces already tell agents
to check: the operating protocol in `tenx context --mode agent`, the
`AGENTS.md` managed block, the bootstrap snippet, and the `tenx-process`
skill all instruct agents to run `tenx update --check` at session start and
to tell a human before installing a newer version.

## Concurrency-safe state (v0.15+)

A fleet of agents can run `tenx` against the same project at the same time.
Mutating commands (`init`, `new`, `set`, `ticket`, `log`, `archive`,
`hook`, `skills`, `sync`, `validate`) are serialized behind a per-project
advisory lock at `.tenx/.lock` (via `fcntl.flock`; the OS releases it on
crash or exit). State-file writes use atomic replacement (`temp +
os.replace`), so readers never see partial files.

If another process holds the lock, a mutating command waits up to 60 s
(override with `TENX_LOCK_TIMEOUT=seconds`), then exits `2` with a clean
message — no traceback. Read-only commands (`context`, `show`, `list`,
`next`, `watchdog`, `triage`, `review`, `history`, `doctor`,
`update --check`) do not take the lock.

`.tenx/.lock` is gitignored; never commit it.

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
4. **Native MCP tools** — harnesses with Model Context Protocol support
   (Claude Code, Cursor, Cline, Windsurf, Copilot, ...) can call tenx
   as structured tools instead of shell commands. See
   [MCP server](#native-tools-via-mcp) below.

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

### Artifact shapes (best-practice defaults)

`tenx new` seeds each artifact with a structure modeled on how top
engineering orgs plan work, so a fresh project starts world-class:

- **epic** — OKR-style: Objective (who benefits, working backwards from the
  user), measurable **Key results**, Scope, **Non-goals**, Milestones.
- **spec** — design-doc style: Summary, Context and scope, Goals/non-goals,
  Design (with trade-offs), **Alternatives considered**, Cross-cutting
  concerns (security/privacy/observability/testing), Tickets, Validation
  (definition of done).
- **convention** — one imperative Rule, the Why (failure it prevents),
  Applies-to, and a good/bad example.
- **doc** — Purpose plus a shape that fits: architecture/system, a decision
  record (Context → Decision → Alternatives → Consequences), or a blameless
  postmortem (Summary → Impact → Root cause → Learnings → Follow-ups).

The matching `tenx-write-*` skills teach the same structures. Only `## Summary`
and `## Validation` are enforced on specs (`tenx validate`); the rest are
guidance, so existing artifacts are never flagged.

## Command reference

```bash
tenx init [--bootstrap]          # scaffold .tenx/ in this project
tenx context --mode operator     # human dashboard
tenx context --mode agent [--budget N]  # full packet; --budget truncates low-priority sections
tenx status                      # alias for the operator dashboard
tenx new <epic|spec|convention|doc> "Title" [--epic EPC-001] [--priority P0]
tenx show <ID> [--json]          # full artifact, metadata + body
tenx list [type] [--json]
tenx set <ID> status in_review   # update metadata (status/owner/epic/title/tags/priority/evidence)
tenx set <ID> priority P0        # business priority tier: P0/P1/P2
tenx set <ID> status complete [--force]  # gated: needs clean validate + done tickets + linked evidence
tenx ticket SPC-001 SPC-001-T2 done
tenx validate [--fix] [--json]   # lint the SDLC; --fix rebuilds the convention index
tenx validate --list-rules [--json]  # print the rule catalog (no linting)
tenx log "implemented webhook handler" --ref SPC-001 --type progress
tenx history [--limit 20] [--json]
tenx next [--json]               # prioritized work queue (the self-improving loop)
tenx watchdog [--json] [--window 7] [--top 5]  # top things needing attention + are they handled
tenx triage [--json] [--window 7] [--top 5]    # what needs a human now: act/watch/escalation
tenx review [--json]             # what awaits review (in_review specs/tickets)
tenx archive EPC-xxx [--yes]     # retire a finished epic and its specs
tenx scan [--json] [--write]     # map the codebase; --write stores it as a DOC
tenx sync push|pull [--spec SPC-xxx] [--dry-run] [--json]
tenx mcp [serve|install]         # MCP server; install writes .mcp.json
tenx skills list|install [--target DIR]
tenx hook [--mode agent] [--budget N] [--no-log]  # emit the packet; logs a throttled session entry
tenx hook install --agent <id|all|detected>  # see `tenx hook detect`
tenx doctor                      # health check
tenx update [--check] [--json]   # self-update; --check reports only
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

### Keep packets cheap and auditable

Large projects bloat the session-start packet. `--budget N` keeps
sections whole while they fit, in priority order (workspace →
validation → conventions → epics → specs → docs → activity), cuts the
first section that overflows with a pointer to `tenx show <ID>`, and
lists omitted sections at the end. The operating protocol is always
kept. Header + protocol are protected from the budget.

Every `tenx hook emit` also writes a throttled `session` entry to the
activity log (at most one per hour), so `tenx history` shows when
agents actually booted with context. Use `--no-log` to opt out.

```bash
tenx context --mode agent --budget 1500
tenx hook emit --budget 1500
```

### Native tools via MCP

`tenx mcp` runs a Model Context Protocol server on stdio (newline-
delimited JSON-RPC 2.0, zero dependencies). MCP-capable harnesses get
the whole tenx surface as native tools — no prompt parsing, structured
arguments, typed errors.

```bash
tenx mcp install               # writes managed .mcp.json (Claude Code)
# or register manually in any MCP-capable harness:
#   command: tenx   args: ["mcp"]
```

Exposed tools: `tenx_context`, `tenx_next`, `tenx_status`, `tenx_show`,
`tenx_list`, `tenx_ticket`, `tenx_log`, `tenx_validate`, `tenx_scan`,
`tenx_exec`. Each maps onto the same code path as the CLI command, so
output and exit semantics match exactly. The server is fault-isolated:
a bad tool call or malformed line returns an error result and keeps
serving.

### Multiplayer: sync tickets to GitHub Issues

Spec tickets are the source of truth in `.tenx/`; `tenx sync` mirrors
them to GitHub Issues so the team sees work where it already looks.

```bash
tenx sync push --dry-run   # preview the plan
tenx sync push             # create/update one issue per ticket
tenx sync pull             # map issue state back into ticket status
```

- Binding: issue titles carry a `[SPC-002-T1]` marker; push is
  idempotent and reconciles state, labels (`tenx:todo` … `tenx:done`),
  and the status line in the issue body.
- Pull maps closed → `done` (and honors the body status line for open
  issues), writing back through the same path as `tenx ticket`.
- Repo resolution: `github_repo: owner/name` in `.tenx/config.yaml`,
  else the `origin` remote. Token resolution: `TENX_GITHUB_TOKEN` >
  `GITHUB_TOKEN` > `~/.git-credentials`. The token is never written
  into `.tenx/` or the activity log.
- Zero new dependencies (stdlib `urllib`). Network errors fail clean
  with a `tenx sync: …` message and a non-traceback exit; re-run to
  resume (push is idempotent). `TENX_GITHUB_API` overrides the endpoint
  (GitHub Enterprise / tests).

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

Within the "do the work" buckets (3–5), a **business priority tier**
(`P0`/`P1`/`P2`, set with `tenx set <ID> priority P0`) floats urgent work
above normal work. Harness health (1–2) always comes first regardless of
priority — fix the machine, then build. A spec inherits its epic's priority
when it has none of its own.

`tenx watchdog` is the pulse check: it scans the whole harness and surfaces
the top few problems — broken validation, drift, blocked or stalled specs,
open blockers, work waiting in review — and cross-references recent activity
to say whether each is **being handled** or **unattended**. Run it after
`tenx context` to spot work that has gone quiet.

`tenx triage` is the escalation layer on top of watchdog: it classifies the
current attention items into **act now** (critical, or high and unattended),
**watch** (being handled or awaiting review), and **healthy**, then picks the
single most important thing needing a human decision. The bundled
`tenx-triage` skill wraps this as a read-only **Triage Officer** agent role you
can schedule to report what needs you right now.

Install the bundled `tenx-process` skill (`tenx skills install`) and agents
run this loop autonomously: brief → pick → load context → work → write back →
validate. The bundled `tenx-review` skill adds the **landing discipline**:
evidence before done, a bounded 2-cycle fix loop, and a human gate on the
final merge.

The **evidence gate is enforced by the CLI**: `tenx set <ID> status complete`
for a spec/epic is blocked unless `tenx validate` is clean for that artifact,
its tickets are done, and evidence is linked (a `--ref` log entry or an
`evidence:` field). `--force` is the explicit human override, and
`evidence_gate: off` in `.tenx/config.yaml` disables it per project.

## Validation rules

`tenx validate` lints the SDLC with 29 rules. The catalog
below is generated from `RULE_CATALOG` in `src/tenx/rules.py`; run
`tenx validate --list-rules` (or `--list-rules --json`) to print it from
the CLI at any time — no project needed.

**Harness & frontmatter**

| Rule | Default | What it catches |
|------|---------|-----------------|
| `archived-epic-active-specs` | warning | epic is archived but one or more of its specs are not |
| `blocker-unresolved` | info | recent blocker log entry has no follow-up progress/decision entry (param: blocker_days) |
| `config-code-root` | error | config declares a code_root that does not exist |
| `convention-empty-body` | warning | convention body has too little content to be followed (param: min_convention_chars) |
| `convention-index` | warning | conventions/INDEX.md drifts from the convention files (run `tenx validate --fix`) |
| `dates-monotonic` | warning | artifact `updated` date is before its `created` date |
| `derived-status-drift` | warning | authored spec status disagrees with the status derived from its tickets (the 10X checkpoint rule; also surfaces as info when all tickets are done but the spec is not promoted) |
| `epic-no-specs` | info | active epic has no specs yet |
| `epic-progress-drift` | warning | epic status disagrees with its specs' statuses (also surfaces as info when all specs are done but the epic is not promoted) |
| `epic-ref` | error | spec has no epic reference or references an unknown epic |
| `frontmatter-parse` | error | artifact frontmatter is not parseable YAML |
| `frontmatter-required` | error | artifact is missing a required frontmatter field (id/type/title/status per type) |
| `harness-missing` | error | no .tenx/ harness found; run `tenx init` first |
| `id-filename-mismatch` | warning | artifact filename does not start with its id (manual rename broke navigation) |
| `id-format` | error | artifact id must look like EPC-001 / SPC-001 / CON-001 / DOC-001 |
| `id-type-mismatch` | error | artifact id prefix does not match its type |
| `id-unique` | error | two artifacts share the same id |
| `log-progress-no-ref` | info | progress log entry has no artifact ref — write-back should reference an artifact |
| `log-quiet` | info | no activity logged for quiet_days (param: quiet_days) |
| `orphan-spec` | warning | spec is in_progress/in_review/complete but defines no tickets |
| `priority-format` | warning | priority is set but not one of P0/P1/P2 (unset is fine; it means normal queue order) |
| `spec-missing-sections` | warning | spec body lacks required sections (param: spec_sections, default Summary,Validation) |
| `stale-artifact` | info | artifact sat in_review longer than stale_days (param: stale_days) |
| `status-valid` | error | artifact status missing or not in the allowed vocabulary |
| `ticket-id` | error | spec ticket without an id |
| `ticket-id-prefix` | warning | ticket id should be '<SPEC-ID>-T<n>' — GitHub sync markers depend on it |
| `ticket-id-unique` | error | duplicate ticket id within one spec |
| `ticket-status-valid` | error | ticket status not in todo/in_progress/in_review/done/blocked |
| `ticket-title-missing` | info | ticket has no title |
| `type-unknown` | error | artifact type is not one of epic/spec/convention/doc |

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
