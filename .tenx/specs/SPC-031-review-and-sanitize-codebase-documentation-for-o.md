---
id: SPC-031
type: spec
title: Review and Sanitize Codebase Documentation for Open Source Release
status: complete
epic: EPC-021
owner: human
priority: P0
created: 2026-09-15
updated: '2026-09-15'
tickets:
- id: SPC-031-T1
  title: Sanitize personal references and author names from metadata and docs [FR-001]
  status: done
- id: SPC-031-T2
  title: "Dispatch subagent to review and update README.md for v0.24.0 capabilities [FR-002]"
  status: done
- id: SPC-031-T3
  title: "Verify documentation accuracy, validate harness, and run tests [FR-001, FR-002]"
  status: done
---

# SPC-031 — Review and Sanitize Codebase Documentation for Open Source Release

## Summary

Audit all documentation, metadata, configuration files, and examples across the repository to sanitize any personal references or names for open source release. Concurrently use tenx's newly implemented subagent dispatch to review and update documentation reflecting full v0.24.0 capabilities.

## Context and scope

The codebase is being prepared for open-source publication. The user requested: "Let's use all the changes that we made to review the documentation in this code base to make it open source. I don't want any name references nothing."

## Goals / non-goals

Goals:
- Sanitize any references to author names or personal handles in `pyproject.toml`, docs, specs, and logs.
- Dispatch subagent via `tenx dispatch --visual` (or headless) to review and enrich `README.md`.
- Ensure all latest features (multiplexer projection, Bifrost routing, memory distillation) are documented accurately.
- Pass `tenx validate` cleanly with 0 errors.

Non-goals:
- Renaming the project itself (`tenx` / `10xdev-cli`).

## Requirements

- FR-001: All documentation and package metadata MUST be free of personal individual names and private paths.
- FR-002: Project documentation (`README.md`) MUST document subagent dispatch, visual terminal multiplexer projection (Herdr and tmux), dynamic Bifrost model routing, and memory distillation.

## Success criteria

- SC-001: Zero matches for personal author names or personal home paths in active tracked files.
- SC-002: Subagent dispatch successfully runs in worktree to produce doc review.
- SC-003: `tenx validate` reports 0 errors and 0 warnings.

## Tickets

- [ ] SPC-031-T1: Sanitize personal references and author names from metadata and docs [FR-001]
- [ ] SPC-031-T2: Dispatch subagent to review and update README.md for v0.24.0 capabilities [FR-002]
- [ ] SPC-031-T3: Verify documentation accuracy, validate harness, and run tests [FR-001, FR-002]

## Validation

- Verified zero matches across git tracked files for personal author names.
- Subagent worker successfully dispatched in isolated worktree and updated README.md with comprehensive v0.24.0 capabilities.
- Added visual hierarchical box drawing glyphs (`\u2514`) and native `herdr agent start` integration so subagents visually branch under the parent workspace in Herdr with live agent status tracking.
- All smoke tests in `tests/smoke_test.py` pass cleanly.
- `tenx validate` passes with 0 errors and 0 warnings.
