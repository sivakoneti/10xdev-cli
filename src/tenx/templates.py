"""Artifact body templates and bundled skills (one skill per artifact type)."""

from __future__ import annotations

EPIC_BODY = """## Objective

One paragraph: what outcome this epic delivers and why it matters.

## Milestones

- [ ] M1 —
- [ ] M2 —

## Success criteria

- Measurable definition of done for the epic.

## Out of scope

- What this epic deliberately does not do.
"""

SPEC_BODY = """## Summary

What this spec builds, in two or three sentences.

## Architecture

Components, data flow, files touched, contracts changed. Link conventions
that apply (CON-xxx).

## Tickets

Move tickets through todo -> in_progress -> in_review -> done. Keep the
frontmatter `tickets:` list in sync with this section.

## Validation

How this spec is verified: commands, tests, manual checks.

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

Write the content here.

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
# Optional: link the code repo this harness governs (default: parent of .tenx)
# code_root: ..
# Rule overrides for `tenx validate` (see rules.yaml defaults)
rules:
  stale_days: 14
  quiet_days: 7
"""

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

1. **Brief yourself.** Run `tenx context --mode agent` and read the packet.
2. **Pick the work.** Run `tenx next`. It reports the highest-value action
   (fix validation errors > review in_review specs > advance active tickets
   > spec out draft epics > reconcile drift).
3. **Load full context.** For the artifact you will touch, run
   `tenx show <ID>` and read the file. Read `.tenx/conventions/INDEX.md`
   and every convention it lists before writing code.
4. **Do the work.** Small, verifiable steps. Follow all conventions.
5. **Write back.** After each significant step run
   `tenx log "what changed" --ref <ID>` and update ticket statuses
   (`tenx ticket <SPEC-ID> <TICKET-ID> <status>`).
6. **Validate.** Before ending, run `tenx validate`. Fix any drift you
   introduced. Never leave new errors behind.

Rules:
- Never invent process facts; they live in `.tenx/` artifacts.
- If a convention conflicts with a spec, stop and ask the human.
- If `tenx` is not installed, read `.tenx/README.md` and follow it manually.
""",
    "tenx-write-epic": """---
name: tenx-write-epic
description: How to author a tenx epic artifact (EPC). Use when creating or revising epics in .tenx/epics/.
---

# Writing an epic

Create with `tenx new epic "Title"`. An epic defines WHAT we build and the
milestones to get there — not how (that belongs in specs).

Requirements:
- Objective: one paragraph, outcome-focused, says why it matters.
- 2-6 milestones, each independently checkable.
- Success criteria must be measurable.
- Out-of-scope section is mandatory; it prevents agent drift.
- Status lifecycle: draft -> in_review -> complete.
- Every spec references exactly one epic via `epic: EPC-xxx`.
""",
    "tenx-write-spec": """---
name: tenx-write-spec
description: How to author a tenx spec artifact (SPC). Use when creating or revising specs in .tenx/specs/.
---

# Writing a spec

Create with `tenx new spec "Title" --epic EPC-001`. A spec is the
ticket-by-ticket technical plan an agent can execute unattended.

Requirements:
- Architecture section names components, files, contracts, and the
  conventions (CON-xxx) that apply.
- Break the work into tickets in the frontmatter `tickets:` list; each
  ticket has id `<SPEC-ID>-T<n>`, title, and status (start at `todo`).
- Keep the markdown Tickets section in sync with the frontmatter list.
- Validation section lists exact commands/tests that prove the spec done.
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
description: How to author a tenx doc artifact (DOC). Use for architecture notes, decisions, external systems, deployment facts.
---

# Writing a doc

Create with `tenx new doc "Title"`. Docs hold everything an agent might need
that is not a plan or a rule: architecture overviews, decision records,
external system configuration, deployment topology, user feedback.

Requirements:
- Purpose section says which agent tasks need this doc.
- Record facts an agent cannot derive from the codebase alone
  (env vars that exist, hosting setup, third-party accounts).
- Bump `updated` whenever content changes; stale docs get flagged.
""",
    "tenx-review": """---
name: tenx-review
description: Review pass for tenx artifacts and finished tickets. Use when a spec or epic enters in_review.
---

# Reviewing

1. `tenx validate` — fix every error first.
2. For each in_review spec: read the spec, then diff the code against it.
   Every ticket marked done must have its validation evidence.
3. Check conventions compliance on the changed code.
4. If good: `tenx set <ID> status complete` and `tenx log "review passed" --ref <ID>`.
   If not: move blocking tickets back to in_progress with a log entry saying why.
""",
}
