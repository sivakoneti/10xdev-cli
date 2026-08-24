# .tenx — meta harness (context base)

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
