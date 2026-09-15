---
id: SPC-001
type: spec
title: Core CLI + validation + hooks
status: complete
epic: EPC-001
created: 2026-08-24
updated: 2026-08-24
tickets:
  - id: SPC-001-T1
    title: Artifact model + zero-dep frontmatter parsing
    status: done
  - id: SPC-001-T2
    title: Validation engine with derived-status drift rule
    status: done
  - id: SPC-001-T3
    title: "Context packets (operator/agent, md/json)"
    status: done
  - id: SPC-001-T4
    title: SessionStart hook install for claude/codex/opencode/gemini
    status: done
  - id: SPC-001-T5
    title: Skills bundle + smoke test suite
    status: done
---
## Summary

The v0.1 core: a CLI that models epics/specs/conventions/docs as markdown
artifacts with YAML frontmatter, validates the SDLC for drift, and emits a
context packet + SessionStart hooks so agents brief themselves. This is the
foundation every later epic builds on.

## Architecture

- `artifacts.py` — frontmatter parse, load/create/update, derived status.
- `rules.py` — validation engine (drift, dangling refs, required fields).
- `context.py` — packet builder (operator/agent, md/json).
- `hooks.py` — SessionStart hook install + managed md blocks.
- `cli.py` — argparse entry, one cmd_* per subcommand.
Conventions: CON-002 (zero deps) governs all of it.

## Tickets

- SPC-001-T1 Artifact model + zero-dep frontmatter parsing — done
- SPC-001-T2 Validation engine with derived-status drift rule — done
- SPC-001-T3 Context packets (operator/agent, md/json) — done
- SPC-001-T4 SessionStart hook install for claude/codex/opencode/gemini — done
- SPC-001-T5 Skills bundle + smoke test suite — done

## Validation

python3 tests/smoke_test.py (both modes) green; `tenx validate` clean on a
fresh `tenx init` project; `tenx context --mode agent` renders.

## Open questions

- None.
