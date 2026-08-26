# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- DSH agent preset: rename to 'tenx — Meta-Harness Engineering Agent' and rewrite the description to lead with tenx's real purpose (context-as-code meta-harness) instead of describing it as a coding agent.
- Added tenx capabilities command and tenx_capabilities MCP tool: curated capability catalog with when-to-use guidance, advertised in the context packet (SPC-022)

### Fixed
- Fixed DSH preset mount failure in DSH web: added missing delegation rows (workflow-worker-thread, tool-subagent-list-agents, tool-subagent-fork, tool-ralph) to DSH_PRESET_CORDIS template (SPC-019)

## [v0.17.0] - 2026-08-25

### Added
- DSH agent preset: tenx hook install --agent dsh emits a mountable preset whose persona hard-mandates the tenx loop (validate MUST pass, landing gate) (SPC-019)
- Git pre-commit gate: tenx hook install --git (and init in a git repo) blocks commits while tenx validate reports errors — universal across all harnesses (SPC-020)

### Changed
- Hardened universal mandate block: AGENTS.md/bootstrap now state the loop as HARD RULES; per-harness forced tiers documented; agent aliases (dsh/agy/prime) (SPC-021)

## [v0.16.0] - 2026-08-25

### Added
- `tenx changelog` command (show/add/release) for Keep-a-Changelog discipline (SPC-018)
- Docs-drift validation rules: `changelog-missing`, `changelog-format`, `changelog-unreleased-empty` (SPC-018)
- Evidence gate now requires a changelog entry referencing a spec/epic before completion (SPC-018)
- `tenx init` seeds a CHANGELOG.md; `tenx_changelog` MCP tool; `tenx-docs-sync` skill (SPC-018)

## [0.15.0] - 2026-08-25

### Added
- Concurrency-safe harness state: per-project advisory lock (.tenx/.lock) serializes mutating commands (SPC-017)
- Atomic file writes (same-directory temp + os.replace) for all state-file updates (SPC-017)
- `TENX_LOCK_TIMEOUT` override; clean exit-2 on lock timeout, no traceback (SPC-017)

### Changed
- `.tenx/.lock` gitignored; read-only commands skip the harness lock (SPC-017)

## [0.14.0] - 2026-08-25

### Added
- Enforced evidence gate: `tenx set <ID> status complete` requires clean validate, done tickets, and linked evidence (EPC-008)
- `tenx triage` command + `tenx_triage` MCP tool + `tenx-triage` agent-role skill (EPC-008)
- `--force` human override and `evidence_gate: off` config escape hatch (EPC-008)

## [0.13.0] - 2026-08-25

### Added
- Priority tiers P0/P1/P2 for epics/specs; specs inherit epic priority (EPC-007)
- `tenx watchdog`: ranked attention items with are-they-handled verdicts (EPC-007)
- Landing discipline encoded in skills: evidence before done, bounded 2-cycle fix loop, human landing gate (EPC-007)

## [0.12.0] - 2026-08-25

### Added
- `tenx update [--check]`: self-update via GitHub Releases with branch fallback (EPC-005)
- Session-start update awareness in the context packet, AGENTS.md block, and process skill (EPC-005)

## [0.11.0] - 2026-08-24

### Added
- Deep SDLC linting: hygiene rules and `RULE_CATALOG` single source of truth (EPC-004)
- `tenx validate --list-rules [--json]` prints the rule catalog without a project (EPC-004)

## [0.10.0] - 2026-08-24

### Added
- `tenx review` queue and `tenx archive` to retire finished epics (SPC-006)

## [0.9.0] - 2026-08-24

### Added
- `tenx mcp`: stdio MCP JSON-RPC server exposing tenx as native agent tools (SPC-005)

## [0.8.0] - 2026-08-24

### Added
- Context-packet `--budget` truncation and throttled session logging (SPC-004)

## [0.7.0] - 2026-08-24

### Added
- `tenx sync push|pull`: two-way spec-ticket <-> GitHub Issues sync (SPC-003)

## [0.6.0] - 2026-08-24

### Added
- `tenx scan`: codebase-map bootstrap (stack, tests, CI, agent files) (SPC-002)

## [0.5.0] - 2026-08-23

### Added
- OpenDesign-style adapter registry: tenx works with any agent harness
