---
id: CON-004
type: convention
title: Write-back and commit policy
status: complete
created: 2026-08-25
updated: 2026-08-25
---

## Rule

Record all significant work through the harness (ticket status + log with a
ref), keep artifact frontmatter valid YAML, run `tenx validate` before
finishing, and never add co-author trailers to commits.

## Why

The harness is the source of truth an agent briefs from next session. Work
that is not written back is lost context. Invalid frontmatter or leftover
validation errors poison every later session. Co-author trailers are banned
by project policy.

## Applies to

Every working session in a tenx-governed repo, and every git commit.

## Good example

```
tenx ticket SPC-001 SPC-001-T2 done
tenx log "wired --list-rules" --ref SPC-001
tenx validate   # 0 errors before stopping
```

## Bad example

```
git commit -m "fix" --trailer "Co-authored-by: ..."   # banned trailer
# stopping while `tenx validate` still reports errors
```
