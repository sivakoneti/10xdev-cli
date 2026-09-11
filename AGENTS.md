<!-- tenx:begin (managed block — do not edit by hand) -->
## Project context — tenx meta-harness

This project keeps its context base in `.tenx/` (epics, specs, conventions,
docs, activity log). At the start of every session, before planning or
writing code:

1. Run `tenx update --check` (non-blocking; if a newer tenx exists, tell the
   human and suggest `tenx update`).
2. Run `tenx context --mode agent` and read the whole packet.
3. Follow the operating protocol printed at the end of that packet.
4. Read `.tenx/conventions/INDEX.md` and every convention it lists.

### Hard rules (non-negotiable)

- Scope: tenx governs codebase engineering (code, architecture, tests, docs).
  Operational execution (running pipelines, workflows, scripts, generating
  media/assets) runs directly without creating or updating tenx artifacts.
- Track work in the harness: before non-trivial changes, find or create the
  epic+spec (`tenx next`, `tenx show <ID>`); move tickets with
  `tenx ticket <SPEC> <TICKET> <status>`.
- Write back as you go: `tenx log "<what changed>" --ref <ID>`.
- Before you call ANY work done, `tenx validate` MUST pass with 0 errors and
  the spec must have evidence. Never mark work complete otherwise.
- Never archive, merge, or delete without explicit human/operator approval.
- A git pre-commit hook enforces this: commits are rejected while
  `tenx validate` reports errors. Do not bypass it with `--no-verify`
  unless the human explicitly says to.
Useful: `tenx next` (what to work on), `tenx show <ID>` (full artifact),
`tenx log "msg" --ref <ID>` (write back), `tenx validate` (self drift),
`tenx watchdog` / `tenx triage` (what needs attention).
<!-- tenx:end -->
