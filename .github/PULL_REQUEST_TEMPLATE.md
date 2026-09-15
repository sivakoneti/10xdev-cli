## Pull Request Checklist

Thank you for contributing to `tenx`! Please ensure your pull request meets the following standards:

### 1. Harness & SDLC Compliance
- [ ] `tenx validate` passes with **0 errors and 0 warnings**.
- [ ] If changing functionality or fixing bugs, a corresponding ticket exists or is referenced.
- [ ] Write-back logged via `tenx log "<description>" --ref <ID>`.
- [ ] `CHANGELOG.md` updated under `[Unreleased]` via `tenx changelog add "<summary>" --type <added|changed|fixed|security>`.

### 2. Architecture & Code Quality
- [ ] **Zero Runtime Dependencies (`CON-002`)**: No external dependencies added to `pyproject.toml` (standard library only).
- [ ] Added or updated automated tests in `tests/smoke_test.py`.
- [ ] Tests pass locally: `python tests/smoke_test.py --module` and `python tests/smoke_test.py`.

### 3. PR Description
- **What changed?**
- **Why is this change necessary?**
- **How was it tested?**
