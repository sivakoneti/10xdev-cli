---
name: tenx-docs-sync
description: Keep documentation in sync with shipped work. Maintain the Keep-a-Changelog CHANGELOG.md so READMEs and notes never drift from the code. Runs the changelog discipline and surfaces drift.
---

# Docs-sync (changelog discipline)

Documentation drifts because code changes have an enforced merge path while
doc updates are a separate manual step. This skill folds the doc update into
the path: every time you ship something, note it in the changelog.

## Loop

1. `tenx changelog` - read the current CHANGELOG.md (Keep a Changelog shape:
   an `[Unreleased]` section at the top, released versions below with dates).
2. Whenever you finish a spec/ticket or ship a behavior change, immediately:
   `tenx changelog add "<what changed>" --type <added|changed|deprecated|removed|fixed|security> --ref <ID>`
   Do this in the same step you mark the work complete - not later.
3. When cutting a release: `tenx changelog release v<X.Y.Z>`. This stamps
   `[Unreleased]` into a dated version and reopens a fresh `[Unreleased]`.
4. `tenx validate` - watch for docs-drift findings:
   - `changelog-missing` (no CHANGELOG.md; run `tenx init` or add one)
   - `changelog-format` (no `[Unreleased]` section)
   - `changelog-unreleased-empty` (completed work has no changelog entry)

## Rules

- The evidence gate requires a changelog entry referencing a spec/epic before
  it can be marked complete. Add the entry first; do not `--force` past it
  unless a human says so.
- Write entries for humans, not as git-log dumps. One clear line per change.
- Group by the Keep a Changelog types; put each entry under the right type.
- Keep the latest version first; never reorder released history.
- Prefer `tenx changelog --json` when another program consumes the output.
