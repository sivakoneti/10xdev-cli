---
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
