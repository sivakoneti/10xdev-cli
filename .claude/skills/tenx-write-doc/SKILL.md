---
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
