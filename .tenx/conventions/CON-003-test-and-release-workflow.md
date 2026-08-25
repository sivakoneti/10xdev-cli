---
id: CON-003
type: convention
title: Test and release workflow
status: complete
created: 2026-08-25
updated: 2026-08-25
---

## Rule

Run the full smoke suite in both modes before every commit, and release by
bumping the version in both files, tagging, publishing a GitHub Release, and
syncing issues.

## Why

tenx governs other projects' SDLC, so its own drift is the worst failure
mode. The two smoke modes catch install-path and source-path regressions;
the release steps keep the self-update channel (releases API) honest.

## Applies to

Any change to `src/tenx/` or `tests/`. Release steps apply to any version
bump.

## Good example

```
python3 tests/smoke_test.py            # CLI mode
python3 tests/smoke_test.py --module   # source mode
# bump pyproject.toml AND src/tenx/__init__.py
git tag vX.Y.Z && git push origin vX.Y.Z   # then create the Release
tenx sync push
```

## Bad example

```
# commit after editing src/ without running the smoke suite
```
