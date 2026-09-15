---
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
