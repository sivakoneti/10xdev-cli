---
id: EPC-001
type: epic
title: tenx v0.1 — portable context base for agents
status: complete
created: 2026-08-24
updated: 2026-08-24
---
## Objective

Ship tenx v0.1: a portable, zero-dependency context base that lets any AI
coding agent brief itself on a project and keep the SDLC honest. Delivers
the meta-harness / context-as-code pattern: epics, specs, conventions, and
docs as markdown artifacts, a validation engine to prevent drift, and hook
installs so every agent harness picks the context up at session start.

## Milestones

- [x] M1 — artifact model + frontmatter load/create/update (artifacts.py)
- [x] M2 — validation engine with drift/dangling-ref rules (rules.py)
- [x] M3 — context packet builder, operator + agent modes (context.py)
- [x] M4 — hook install for agent harnesses + managed blocks (hooks.py)
- [x] M5 — `tenx init` bootstrap + bundled skills (cli.py, skills.py)

## Success criteria

- `tenx init` scaffolds a working .tenx/ on any repo in one command.
- `tenx validate` detects authored-vs-derived status drift and broken refs.
- `tenx context --mode agent` emits a self-serve packet an agent can act on.
- Zero runtime dependencies; installs via uv/pipx on a fresh machine.

## Out of scope

- Multi-user collaboration / locking (single-writer assumption).
- Any hosted service; everything is local files + git.
