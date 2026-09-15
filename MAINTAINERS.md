# Maintainer Playbook: Reviewing, Testing, and Releasing tenx

This guide outlines the standard operating procedures for maintainers to review incoming community Pull Requests, triage Issues, and cut new releases.

---

## 1. Reviewing Pull Requests (Inbound Community Contributions)

When an external contributor submits a PR, GitHub Actions automatically executes `.github/workflows/ci.yml` across Python 3.10, 3.12, and 3.13.

### The 4 Non-Negotiable Merge Gates:
1. **Zero Runtime Dependencies Gate (`CON-002`)**:
   - Check `pyproject.toml` diff.
   - `dependencies = []` must remain empty. External libraries (e.g. `requests`, `click`, `pydantic`) are strictly rejected. Standard library only (`subprocess`, `urllib`, `json`, `pathlib`, `dataclasses`, `socket`).
2. **SDLC Linter Gate**:
   - The CI run must show `tenx validate` passing with **0 errors and 0 warnings**.
3. **Docs-Sync & Changelog Gate**:
   - Every behavior change must include an entry in `CHANGELOG.md` under `[Unreleased]`.
4. **Smoke Suite Pass**:
   - `python tests/smoke_test.py --module` and `python tests/smoke_test.py` must pass 100%.

### Merge Strategy:
- Use **Squash and Merge** with a clean Conventional Commit message (`feat: ...`, `fix: ...`, `docs: ...`).

---

## 2. Issue Triage Protocol

We categorize incoming issues into:
- **`bug`**: Broken functionality, harness crash, or rule false positives.
  - Reproduce locally with `python tests/smoke_test.py`.
  - Add a reproducing assertion to `tests/smoke_test.py` before fixing.
- **`enhancement`**: New adapter for emerging LLM harnesses (e.g., new coding agents), new MCP tools, or additional validation rules.
  - Adding a harness adapter is zero-risk: simply add a declarative entry in `src/tenx/adapters.py` without modifying the core engine.
- **`question` / `discussion`**: Move open questions to GitHub Discussions.

---

## 3. Cutting a New Release

When enough features or fixes accumulate in `[Unreleased]`:

1. **Update Version**:
   - Bump version in `pyproject.toml` and `src/tenx/__init__.py`.
2. **Stamp Changelog**:
   ```bash
   tenx changelog release v0.XX.0
   ```
3. **Run Smoke Suite & Validation**:
   ```bash
   python tests/smoke_test.py --module
   tenx validate
   ```
4. **Commit and Tag**:
   ```bash
   git add -A
   git commit -m "chore: release v0.XX.0"
   git tag -a v0.XX.0 -m "Release v0.XX.0"
   git push origin main --tags
   ```
5. **Publish GitHub Release**:
   ```bash
   gh release create v0.XX.0 --generate-notes
   ```
   *Downstream users will immediately be alerted on session start via `tenx update --check`.*
