---
id: SPC-003
type: spec
title: GitHub Issues ticket sync
status: complete
epic: EPC-002
created: 2026-08-24
updated: 2026-08-24
tickets:
  - id: SPC-003-T1
    title: token + repo resolution helpers
    status: done
  - id: SPC-003-T2
    title: GitHub API client via urllib
    status: done
  - id: SPC-003-T3
    title: tenx sync push + --dry-run
    status: done
  - id: SPC-003-T4
    title: tenx sync pull + write-back
    status: done
  - id: SPC-003-T5
    title: live dogfood sync to upstream issue tracker
    status: done
---

## Summary

Two-way sync between spec tickets and GitHub Issues — the video's
"all the tickets moved to the right column in the tracker" moment,
tracker-native. `tenx sync push` creates/updates one issue per ticket;
`tenx sync pull` maps issue state back into ticket status. Zero new
dependencies (stdlib urllib); token never written into `.tenx/`.

## Architecture

New module `src/tenx/sync.py`:

- Token resolution order: `TENX_GITHUB_TOKEN` env > `GITHUB_TOKEN` env >
  `~/.git-credentials` github.com entry (password field). Missing token
  -> clear error, no partial writes.
- Repo resolution: `github_repo: owner/name` in `.tenx/config.yaml`
  wins; else parse `git remote get-url origin` (https or ssh form);
  else error.
- Issue<->ticket binding: issue title prefix `[SPC-002-T1]`. Search by
  listing issues with `per_page=100&state=all` and matching the marker
  (repos are small; no search API needed).
- push: create missing issues (title `[TID] <ticket title>`, body with
  spec id, status, spec path); existing issues get state reconciled
  (ticket done -> close, else open) and the status line in the body
  updated. Labels: `tenx`, plus status label (`tenx:todo`,
  `tenx:in_progress`, `tenx:in_review`, `tenx:done`) created on demand.
- pull: for issues carrying a marker, map closed -> done (open keeps
  authored status unless body status line disagrees); write back via the
  same path as `tenx ticket`, log one `progress` activity entry
  summarizing changes.
- `--dry-run` on both directions prints the plan, touches nothing.
- `--spec SPC-xxx` limits scope; default is all specs with tickets.

Security: token only in memory; never echoed, never stored in
artifacts or logs. Add this rule to CON-001 in the same change.

## Tickets

- SPC-003-T1 token + repo resolution helpers (offline, unit-testable)
- SPC-003-T2 GitHub API client (list/create/update/labels) via urllib
- SPC-003-T3 `tenx sync push` + `--dry-run`
- SPC-003-T4 `tenx sync pull` + write-back + activity log
- SPC-003-T5 live dogfood: sync EPC-002 specs to upstream issue tracker

## Validation

- Smoke: resolution helpers against fake env/config (no network).
- Live: `tenx sync push --dry-run` then real push on this repo; verify
  issues exist; move one ticket, `tenx sync push`, verify issue state;
  close one issue in GitHub UI, `tenx sync pull`, verify ticket -> done.

## Open questions

- Rate limits: fine at this scale; revisit if a repo has >100 tenx
  issues (pagination).
