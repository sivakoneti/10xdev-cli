"""Artifact body templates and bundled skills (one skill per artifact type)."""

from __future__ import annotations

EPIC_BODY = """## Objective

One paragraph: the outcome this epic delivers and why it matters. Name who
benefits (the user/customer) and frame the problem from their point of view
— start with the user and work backwards.

## Key results

Measurable outcomes that prove the objective was met (2-5). Each must be
verifiable, not an activity: "reduce p95 latency to <200ms", not "improve
performance".

- KR1 —
- KR2 —

## Scope

- What this epic deliberately covers.

## Non-goals

- Things that could reasonably be goals but are explicitly NOT. This section
  prevents agent drift.

## Milestones

- [ ] M1 —
- [ ] M2 —
"""

SPEC_BODY = """## Summary

What this spec builds and why, in two or three sentences. Name the user or
caller who benefits.

## Context and scope

Objective background: the landscape this is built in and what is in scope.
Keep it succinct; link deeper detail rather than restating it.

## Goals / non-goals

Goals:
- What this spec must achieve.

Non-goals:
- Things that could be goals but are explicitly not.

## Design

The approach and its key trade-offs: components, files touched, data flow,
contracts changed. Link the conventions (CON-xxx) that apply. Record WHY
this design wins given the goals, not just WHAT it is.

## Alternatives considered

Other designs that would have worked and the trade-off that ruled each out.
If the solution is obvious with no real trade-off, say so in one line.

## Cross-cutting concerns

Security, privacy, observability, testing, backward compatibility — how each
is affected and addressed. Delete any line that does not apply.

## Tickets

Move tickets through todo -> in_progress -> in_review -> done. Keep the
frontmatter `tickets:` list in sync with this section.

## Validation

Exact commands, tests, and manual checks that prove the spec complete — the
definition of done.

## Open questions

- None yet.
"""

CONVENTION_BODY = """## Rule

State the rule in one imperative sentence.

## Why

What failure this prevents.

## Applies to

Files, languages, or situations where this rule binds.

## Good example

```
```

## Bad example

```
```
"""

DOC_BODY = """## Purpose

What this document covers and which agent tasks need it.

## Content

Write the content here. Pick the shape that fits:
- Architecture/system doc: components, data flow, invariants, how to run.
- Decision record (ADR): Context -> Decision -> Alternatives considered ->
  Consequences.
- Postmortem (blameless): Summary -> Impact -> Root cause(s) -> What we
  learned -> Follow-up actions. Fix systems and processes, not people.

## Last verified

Keep this doc current; bump `updated` when you change it.
"""

BODY_TEMPLATES = {
    "epic": EPIC_BODY,
    "spec": SPEC_BODY,
    "convention": CONVENTION_BODY,
    "doc": DOC_BODY,
}

INDEX_HEADER = """# Convention index

Every convention artifact in this harness, kept in sync by `tenx validate
--fix`. Agents: read this file before writing code; every entry binds you.

"""

HARNESS_README = """# .tenx — meta harness (context base)

This directory is the project's context base. The code repo says *what
exists*; this harness says *why it exists, what we are building
next, and how work must be done*.

Layout:

- `config.yaml` — project identity and rule settings
- `epics/` — EPC artifacts: what we are building + milestones
- `specs/` — SPC artifacts: ticket-by-ticket technical plans
- `conventions/` — CON artifacts + INDEX.md: rules that keep agents on rails
- `docs/` — DOC artifacts: architecture, decisions, external systems
- `log/activity.jsonl` — append-only activity log agents write back to
- `rules.yaml` — optional rule toggles/thresholds for `tenx validate`

CLI quick reference (run from the project root):

- `tenx context --mode agent` — full context packet (session start)
- `tenx next` — most important thing to work on next
- `tenx new <epic|spec|convention|doc> "Title"` — create an artifact
- `tenx log "message" --ref SPC-001` — record significant work
- `tenx validate` — lint the SDLC (drift, broken refs, stale artifacts)
- `tenx set <ID> status <status>` / `tenx ticket <SPEC> <TICKET> done`
"""

CONFIG_TEMPLATE = """# tenx harness configuration
project: {project}
description: "{description}"
{code_root_line}# Rule overrides for `tenx validate` (see rules.yaml defaults)
rules:
  stale_days: 14
  quiet_days: 7
"""

# Comment used in co-located configs; standalone configs get a real value.
CODE_ROOT_COMMENT = ("# code_root: the code repo this harness governs "
                     "(hooks + AGENTS.md land there).\n# code_root: ..\n")

# ---------------------------------------------------------------------------
# Skills: markdown skill files, one per artifact type + process skills.
# ---------------------------------------------------------------------------

SKILLS: dict[str, str] = {
    "tenx-process": """---
name: tenx-process
description: The tenx working loop for any task in this project. Use at session start and whenever unsure what to do next.
---

# tenx process loop

You are a senior engineer on this project. Follow this loop exactly:

1. **Check the tooling.** Run `tenx update --check`. If a newer tenx
   version exists, tell the human and suggest `tenx update`. Never block
   on this — if it cannot check (offline), move on.
2. **Brief yourself.** Run `tenx context --mode agent` and read the packet.
3. **Pick the work.** Run `tenx next`. It reports the highest-value action
   (fix validation errors > review in_review specs > advance active tickets
   > spec out draft epics > reconcile drift).
4. **Load full context.** For the artifact you will touch, run
   `tenx show <ID>` and read the file. Read `.tenx/conventions/INDEX.md`
   and every convention it lists before writing code.
5. **Do the work.** Small, verifiable steps. Follow all conventions.
6. **Write back.** After each significant step run
   `tenx log "what changed" --ref <ID>` and update ticket statuses
   (`tenx ticket <SPEC-ID> <TICKET-ID> <status>`). When you ship a behavior
   change, note it in the changelog in the same step (docs-sync):
   `tenx changelog add "what changed" --ref <ID>`.
7. **Validate.** Before ending, run `tenx validate`. Fix any drift you
   introduced. Never leave new errors behind.

Landing discipline (applies to every ticket you finish):
- **Evidence before done.** Only mark a ticket `done` when `tenx validate`
  passes and the spec's Validation section is satisfied (tests run, output
  quoted). No evidence, no done.
- **Docs are part of done.** A spec/epic cannot be marked complete until its
  shipped work is noted in CHANGELOG.md
  (`tenx changelog add "..." --ref <ID>`). The evidence gate enforces this.
- **Bounded fix loop.** If work bounces back from review, fix and retry —
  at most 2 cycles. Still failing? Stop and escalate to the human with the
  concrete failure instead of looping.
- **Human lands it.** Agents recommend land-or-bounce with evidence; the
  human approves the final merge/archive.

Rules:
- Never invent process facts; they live in `.tenx/` artifacts.
- If a convention conflicts with a spec, stop and ask the human.
- For non-trivial work the spec (design) comes before code: capture goals,
  non-goals, trade-offs, and alternatives first. If there is no real
  trade-off, just build it — do not write an implementation manual.
- If `tenx` is not installed, read `.tenx/README.md` and follow it manually.
""",
    "tenx-write-epic": """---
name: tenx-write-epic
description: How to author a tenx epic artifact (EPC). Use when creating or revising epics in .tenx/epics/.
---

# Writing an epic

Create with `tenx new epic "Title"`. An epic defines WHAT we build and why —
not how (that belongs in specs). Model it on OKRs and the working-backwards
habit of starting from the user.

Requirements:
- Objective: one paragraph, outcome-focused. Name who benefits and frame the
  problem from their point of view.
- Key results: 2-5 measurable outcomes that prove the objective. Each must be
  verifiable, not an activity ("reduce p95 latency to <200ms", not "improve
  performance").
- Scope and Non-goals: non-goals are mandatory — things that could reasonably
  be goals but are explicitly not. They prevent agent drift.
- 2-6 milestones, each independently checkable.
- Status lifecycle: draft -> in_review -> complete.
- Every spec references exactly one epic via `epic: EPC-xxx`.
""",
    "tenx-write-spec": """---
name: tenx-write-spec
description: How to author a tenx spec artifact (SPC). Use when creating or revising specs in .tenx/specs/.
---

# Writing a spec

Create with `tenx new spec "Title" --epic EPC-001`. A spec is a lightweight
design doc plus a ticket-by-ticket plan an agent can execute unattended.
Follow the classic design-doc shape: context, goals/non-goals, design with
trade-offs, alternatives, cross-cutting concerns.

Requirements:
- Summary and Validation sections are required (`tenx validate` checks them).
- Context and scope: objective background, kept succinct; link deeper detail.
- Goals / non-goals: name both; non-goals prevent drift.
- Design: record WHY this approach wins given the goals, not just WHAT. Link
  the conventions (CON-xxx) that apply.
- Alternatives considered: list real alternatives and the trade-off that
  ruled each out. If there is no real trade-off, say so in one line — a spec
  with no trade-offs may not have needed a spec (just build it).
- Cross-cutting concerns: security, privacy, observability, testing,
  backward compatibility.
- Break work into tickets in the frontmatter `tickets:` list; each ticket has
  id `<SPEC-ID>-T<n>`, title, and status (start at `todo`). Keep the markdown
  Tickets section in sync with the frontmatter list.
- Validation lists exact commands/tests that prove the spec done (definition
  of done).
- A spec is only `complete` when every ticket is `done`
  (`tenx validate` derives and enforces this).
""",
    "tenx-write-convention": """---
name: tenx-write-convention
description: How to author a tenx convention artifact (CON). Use when codifying a coding or process rule in .tenx/conventions/.
---

# Writing a convention

Create with `tenx new convention "Rule name"`. Conventions keep agents on
rails; they bind every coding session.

Requirements:
- One imperative rule sentence, then WHY (the failure it prevents).
- Applies-to scope: files, languages, or situations.
- Include a good and a bad example whenever practical.
- Run `tenx validate --fix` so INDEX.md picks the convention up.
- Only humans should retire conventions; agents flag conflicts instead.
""",
    "tenx-write-doc": """---
name: tenx-write-doc
description: How to author a tenx doc artifact (DOC). Use for architecture notes, decisions, external systems, deployment facts, postmortems.
---

# Writing a doc

Create with `tenx new doc "Title"`. Docs hold everything an agent might need
that is not a plan or a rule: architecture overviews, decision records,
external system configuration, deployment topology, postmortems.

Requirements:
- Purpose section says which agent tasks need this doc.
- Record facts an agent cannot derive from the codebase alone
  (env vars that exist, hosting setup, third-party accounts).
- Pick the right shape for the content:
  - Architecture/system: components, data flow, invariants, how to run.
  - Decision record (ADR): Context -> Decision -> Alternatives considered ->
    Consequences.
  - Postmortem (blameless): Summary -> Impact -> Root cause(s) -> What we
    learned -> Follow-up actions. Fix systems and processes, not people.
- Bump `updated` whenever content changes; stale docs get flagged.
""",
    "tenx-review": """---
name: tenx-review
description: Review pass for tenx artifacts and finished tickets. Use when a spec or epic enters in_review, or to archive completed epics.
---

# Reviewing

1. `tenx validate` — fix every error first.
2. `tenx review` lists what is ready to review (in_review specs/epics and
   done tickets). Work through that queue.
3. For each in_review spec: read the spec, then diff the code against it.
   Every ticket marked done must have its validation evidence (the spec's
   Validation section is the definition of done).
4. Check conventions compliance on the changed code (read
   `.tenx/conventions/INDEX.md` and every entry).
5. If good: `tenx log "review passed" --ref <ID>` first (that log entry is
   the evidence), then `tenx set <ID> status complete`. The CLI now enforces
   this: it blocks `status complete` unless validation is clean, tickets are
   done, and evidence is linked. If not good: move blocking tickets back to
   in_progress with a log entry saying why.
6. When an epic and all its specs are complete, `tenx archive <EPC-ID>` moves
   it out of the active queue (blameless — archive is a record, not a grade).

## Landing discipline (bounded fix loop + evidence gate)

- **Bounded fix loop.** When a review bounces work back, fix and re-review.
  Allow at most **2 fix cycles** for the same spec/ticket. If it still fails
  after the 2nd bounce, STOP and escalate to the human with the concrete
  failure — do not loop forever.
- **Evidence gate (CLI-enforced).** Never mark a spec/epic complete without
  evidence: `tenx validate` passes AND the spec's Validation section is
  satisfied (tests run, commands shown, output quoted). "It should work" is
  not evidence. The CLI blocks `tenx set <ID> status complete` until evidence
  is linked (a `--ref` log entry or an `evidence:` field); `--force` is the
  explicit human override.
- **Human gate for landing.** Merging/archiving is the human's call. Agents
  prepare the evidence and recommend land-or-bounce; the human approves the
  final merge. Do not self-merge past the human.
- **Verify like a user.** Where practical, confirm the change the way a user
  would (run the command, open the flow), not just that the code compiles.
""",
    "tenx-triage": """---
name: tenx-triage
description: Triage Officer agent role. Run periodically or on demand to rank what needs attention across the project and hand the human the single most important escalation. Read-only; never mutates state.
---

# Triage Officer (agent role)

You are the Triage Officer. Your job is to answer one question for the human
overseeing this project: "what needs ME right now?" You do not fix anything;
you rank, classify, and escalate.

## Loop

1. `tenx update --check` - if a newer tenx exists, tell the human once. Never
   block on this; offline is fine.
2. `tenx triage` - read the act-now / watch / healthy breakdown and the
   suggested escalation.
3. For each act-now item, decide in one line whether it needs:
   - a human decision (blocked, unattended, or a landing gate), or
   - an agent to be dispatched to it (then name the spec/ticket).
4. Report to the human in this exact shape:
   - **Escalate:** the single most important thing needing a human decision.
   - **Act now:** the remaining critical/unattended items, one line each.
   - **Watch:** items being handled or waiting review, one line each.
   - **Healthy:** how many in-progress specs have recent activity.
5. Do NOT mutate state. Do not mark anything complete, merge, or archive.
   Recommend; the human (or the review skill) lands.

## Rules

- Prefer `tenx triage --json` when another program consumes the output.
- If there is nothing to escalate, say so plainly - silence is a valid report.
- Keep the report short. One line per item. No prose padding.
""",
    "tenx-docs-sync": """---
name: tenx-docs-sync
description: Keep documentation in sync with shipped work. Maintain the Keep-a-Changelog CHANGELOG.md so READMEs and notes never drift from the code. Runs the changelog discipline and surfaces drift.
---

# Docs-sync (changelog discipline)

Documentation drifts because code changes have an enforced merge path while
doc updates are a separate manual step. This skill folds the doc update into
the path: every time you ship something, note it in the changelog.

## Loop

1. `tenx changelog` - read the current CHANGELOG.md (Keep a Changelog shape:
   an `[Unreleased]` section at the top, released versions below with dates).
2. Whenever you finish a spec/ticket or ship a behavior change, immediately:
   `tenx changelog add "<what changed>" --type <added|changed|deprecated|removed|fixed|security> --ref <ID>`
   Do this in the same step you mark the work complete - not later.
3. When cutting a release: `tenx changelog release v<X.Y.Z>`. This stamps
   `[Unreleased]` into a dated version and reopens a fresh `[Unreleased]`.
4. `tenx validate` - watch for docs-drift findings:
   - `changelog-missing` (no CHANGELOG.md; run `tenx init` or add one)
   - `changelog-format` (no `[Unreleased]` section)
   - `changelog-unreleased-empty` (completed work has no changelog entry)

## Rules

- The evidence gate requires a changelog entry referencing a spec/epic before
  it can be marked complete. Add the entry first; do not `--force` past it
  unless a human says so.
- Write entries for humans, not as git-log dumps. One clear line per change.
- Group by the Keep a Changelog types; put each entry under the right type.
- Keep the latest version first; never reorder released history.
- Prefer `tenx changelog --json` when another program consumes the output.
""",
}
