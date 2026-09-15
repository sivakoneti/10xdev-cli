---
id: EPC-021
type: epic
title: Open Source Sanitization and Documentation Review
status: complete
lead: human
priority: P0
created: 2026-09-15
updated: 2026-09-15
---

# EPC-021 — Open Source Sanitization and Documentation Review

## Overview

To release tenx as an enterprise-grade open-source project, all documentation, metadata, configuration, examples, and logs must be thoroughly audited and sanitized. No individual names, personal home directory paths, private credentials, or author-specific fingerprints should remain in the public surface. The documentation must be comprehensive, modern, accurate, and completely neutral.

## Key results

- KR-001: 100% removal of personal names and author fingerprints from all documentation, package configurations, and manifests.
- KR-002: Complete review and update of `README.md` and docs reflecting latest v0.24.0 capabilities (visual Herdr/tmux projection, Bifrost routing, subagent dispatch, memory distillation).
- KR-003: Clean verification through `tenx validate` and automated smoke testing suite.

## Non-goals

- Altering core CLI command semantics or breaking public API schemas.
- Removing generic git commit history if already upstreamed.

## Milestones

1. Audit and redact all personal identity references in `pyproject.toml`, docs, specs, and logs.
2. Subagent dogfood dispatch to review and update documentation.
3. Validate and verify release hygiene.
