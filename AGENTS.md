<!-- tenx:begin (managed block — do not edit by hand) -->
## Project context — tenx meta-harness

This project keeps its context base in `.tenx/` (epics, specs, conventions,
docs, activity log). At the start of every session, before planning or
writing code:

1. Run `tenx context --mode agent` and read the whole packet.
2. Follow the operating protocol printed at the end of that packet.
3. Read `.tenx/conventions/INDEX.md` and every convention it lists.

Useful: `tenx next` (what to work on), `tenx show <ID>` (full artifact),
`tenx log "msg" --ref <ID>` (write back), `tenx validate` (self drift).
<!-- tenx:end -->
