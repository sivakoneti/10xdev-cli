---
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
