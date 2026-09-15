# Contributing to tenx

Thank you for your interest in contributing to `tenx`! `tenx` is an autonomous meta-harness providing context-as-code for AI coding agents.

## Architectural Principles

1. **Zero Runtime Dependencies (`CON-002`)**: Standard library only (`socket`, `subprocess`, `urllib.request`, `json`, `pathlib`, `dataclasses`). Do not add external runtime dependencies to `pyproject.toml`. PyYAML is optionally used if present, with our zero-dependency fallback `yamlite.py`.
2. **Context as Code**: SDLC artifacts live under `.tenx/` (`epics/`, `specs/`, `conventions/`, `docs/`, `log/activity.jsonl`).
3. **Strict Validation**: All contributions must pass `tenx validate` with 0 errors and 0 warnings.

## Getting Started

### Local Development Setup

Clone the repository and install in editable mode with `uv` or `pip`:

```bash
git clone https://github.com/sivakoneti/10xdev-cli.git
cd 10xdev-cli

# Install editable binary
uv tool install --editable . --force
# Or via pip
pip install -e .
```

### Running Tests

We maintain a comprehensive smoke test suite that verifies CLI commands, MCP tools, and hermetic harness isolation:

```bash
# Run standalone module mode
python tests/smoke_test.py --module

# Run installed mode
python tests/smoke_test.py

# Run SDLC linting
tenx validate
```

## Making Changes

1. **Track Work**: Find or create the relevant spec/ticket (`tenx next`, `tenx show <ID>`).
2. **Write Back**: Log significant progress with `tenx log "<message>" --ref <ID>`.
3. **Evidence Gate**: Before marking any spec or ticket complete, ensure tests pass and `CHANGELOG.md` is updated (`tenx changelog add "<message>"`).
4. **Pre-commit Gate**: Ensure `tenx validate` passes before committing.

## Submitting Pull Requests

- Keep PRs focused on a single feature, spec, or bug fix.
- Ensure all CI checks pass.
- Write clear, imperative commit messages (`feat: ...`, `fix: ...`, `docs: ...`).
