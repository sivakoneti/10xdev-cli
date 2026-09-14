# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [v0.23.0] - 2026-09-15

### Added
- Visual multiplexer projection for tenx dispatch (Herdr workspaces in sidenav and tmux windows) (SPC-029)

## [v0.22.0] - 2026-09-15

### Added
- Add subagent ticket dispatch system with tenx ticket-brief, tenx dispatch, and tenx-dispatch skill (SPC-028)

## [v0.21.0] - 2026-09-11

### Added
- Validate epic body substance and block evidence gate on unpopulated boilerplate epics (SPC-027)

## [v0.20.0] - 2026-09-11

### Added
- GitHub Actions CI: smoke suite runs in both modes (module + pip-installed) plus tenx validate on every push/PR across Python 3.10/3.12/3.13 (SPC-024)
- Structured spec template: numbered FR-### requirements, SC-### success criteria, [NEEDS CLARIFICATION] markers, Given/When/Then acceptance guidance (SPC-025)
- tenx validate enforces spec discipline: clarify-markers-open (error on open ambiguity past draft), requirement-uncovered / requirement-orphan coverage rules (marker-driven, legacy specs immune) (SPC-025)
- tenx converge <SPC>: deterministic spec-completion convergence — FR-### vs tickets report, --append creates missing tickets (append-only, byte-for-byte no-op when clean), --json for agents (SPC-025)
- tenx_converge MCP tool (15 tools total): JSON convergence report for agent-driven projects; append=true creates missing tickets under the harness lock, report stays lock-free (SPC-026)

### Changed
- the tenx repo now runs commit_gate: on — staged code without activity-log write-back blocks the commit (new projects keep the warn default) (SPC-024)
- commit-without-writeback rule builds its git --since window with whole-second ISO timestamps for consistent parsing across git versions (SPC-024)
- define explicit development vs operational execution scope boundary in managed agent instructions and skills

### Fixed
- smoke suite module mode is now hermetic: it provides a PATH shim running the source tree so the git pre-commit gate works on bare checkouts (fresh CI runners) without an installed tenx (SPC-024)
- git-aware enforcement (commit-without-writeback rule, gate commit-check) now parses git timestamps with a trailing Z — on UTC hosts with Python 3.10 both previously failed open and never fired (SPC-024)

## [v0.19.0] - 2026-08-26

### Added
- Git-aware enforcement: tenx validate now flags recent code commits that have no activity-log write-back (commit-without-writeback rule, fail-open without git), and a new staged-change freshness gate (tenx gate commit-check) runs inside the git pre-commit hook; configure with commit_gate: on|warn|off (default warn) (SPC-023)
- tenx doctor now audits enforcement health — missing/stale git pre-commit gate, core.hooksPath bypass, stale managed agent surfaces, missing .mcp.json / bundled skills, commit_gate: off — exits non-zero on problems with exact fix commands; tenx doctor --json adds enforcement_problems (SPC-023)
- blocked is now a legal ticket status (workflow already referenced it); ticket creation and moves auto-append activity-log entries so ticket state changes are auditable (SPC-023)
- Audit trail for gate escapes: evidence-gate blocks log a blocker entry, --force completions log a decision entry, and tenx archive now requires --approved-by "<operator>" and records the approver in the activity log (SPC-023)
- tenx update re-syncs hooks and managed agent surfaces (hook install --agent detected --git) automatically after a successful upgrade (SPC-023)

### Changed
- Completion-drift rules (derived-status-drift, orphan-spec, epic-progress-drift) are now errors when an artifact is authored complete without the derived progress to back it — hand-editing status: complete in a spec/epic file no longer passes validate (SPC-023)
- Evidence gate changelog check now scans every changelog section (not only [Unreleased]), so work documented under a released version also satisfies docs-sync (SPC-023)
- cleanup from audit LOW findings: removed dead cli.py imports, completed the cli.py command map in the module docstring (capabilities/changelog/exec/gate/review/archive/scan/sync/mcp), README fixes (changelog in the mutating-command list, skills status, archive --approved-by, full init flag set), and the exec brief now runs validate before set-complete (SPC-023)

### Fixed
- Git hook discovery handles linked worktrees (.git pointer files resolve to the common hooks dir); the pre-commit hook is timeout-wrapped and fails open with a warning if tenx itself fails, so a broken tenx can never block all commits (SPC-023)
- MCP mutating tools now take the same per-project harness lock as the CLI (tenx_ticket/log/set/scan/... no longer race concurrent agents); MCP callers may pass root explicitly (SPC-023)
- yamlite hardening: zero-indent lists parse correctly and fallback-parser problems are reported visibly instead of silently dropping content (SPC-023)
- Changelog round-trip preserves heading-less entries, sub-bullets, and prose (byte-stable re-render) (SPC-023)
- Capabilities catalog fixes: init and gate entries added, capabilities tagged for both CLI+MCP surfaces, archive/doctor/scan guidance updated; stale managed agent surfaces are now also a validate warning (agent-surface-stale) (SPC-023)
- Docs refresh: architecture overview + README MCP tool list updated to current reality, dead docs/agent-adapters.md link removed, bundled tenx-process skill priority order aligned with tenx next, exec brief now documents the evidence gate, changelog requirement, and commit gate (SPC-023)
- tenx watchdog now flags only unresolved blocker log entries (a blocker counts as resolved once a later progress/decision entry follows up on the same ref) — audited gate-block entries no longer pollute the watchdog forever (SPC-023)
- tenx scan makes the census top-15 truncation visible (heading says 'top 15 of N entries'), so a missing entry in the codebase map reads as not-shown instead of deleted (SPC-023)
- --root is now accepted both before and after the subcommand (tenx validate --root X works; previously only tenx --root X validate did) (SPC-023)
- tenx scan --write now actually preserves manual additions appended below the regeneration promise in the codebase map (the promise was previously false: re-scans silently deleted them) (SPC-023)

## [v0.18.0] - 2026-08-26

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
