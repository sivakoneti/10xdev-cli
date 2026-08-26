---
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
