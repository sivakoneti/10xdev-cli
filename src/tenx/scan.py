"""tenx scan — bootstrap a codebase map from any existing repo.

Walks the governed code root and reports stack markers, entry points,
test setup, CI, existing agent instruction files, and a bounded
top-level directory census. Pure stdlib, no writes in scan_tree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SKIP_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env",
    "dist", "build", "__pycache__", ".next", ".nuxt", "target",
    ".tenx", ".tox", ".mypy_cache", ".pytest_cache", ".cache",
    "coverage", ".turbo", ".parcel-cache",
}

# marker file -> stack label
STACK_MARKERS: dict[str, str] = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "requirements.txt": "python",
    "package.json": "node",
    "pnpm-workspace.yaml": "node (pnpm workspace)",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "pom.xml": "java (maven)",
    "build.gradle": "java/kotlin (gradle)",
    "build.gradle.kts": "kotlin (gradle)",
    "Gemfile": "ruby",
    "composer.json": "php",
    "mix.exs": "elixir",
    "CMakeLists.txt": "c/c++ (cmake)",
}

AGENT_FILES = (
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "QWEN.md", "CONVENTIONS.md",
    ".windsurfrules", ".continuerules",
    ".cursor/rules", ".clinerules", ".kiro/steering",
    ".github/copilot-instructions.md",
)

TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec", "e2e"}
TEST_MARKERS = {
    "pytest.ini", "tox.ini", "vitest.config.ts", "vitest.config.js",
    "jest.config.js", "jest.config.ts", "playwright.config.ts",
    "karma.conf.js", ".mocharc.json",
}
CI_MARKERS = (".github/workflows", ".gitlab-ci.yml", "Jenkinsfile",
              ".circleci", ".buildkite")


def _iter_files(root: Path, max_depth: int):
    """Yield (path, depth, is_dir) up to max_depth, skipping SKIP_DIRS.

    Directories are yielded too so callers can see empty dirs (tests/)
    and dir-level markers (.github/workflows).
    """
    def walk(d: Path, depth: int):
        if depth > max_depth:
            return
        try:
            entries = sorted(d.iterdir())
        except (PermissionError, OSError):
            return
        for e in entries:
            if e.is_symlink():
                continue
            if e.is_dir():
                if e.name in SKIP_DIRS or e.name == ".git":
                    continue
                yield e, depth, True
                yield from walk(e, depth + 1)
            else:
                yield e, depth, False
    yield from walk(root, 1)


def scan_tree(project_root: Path, code_root: Path) -> dict[str, Any]:
    """Scan code_root and return the codebase-map dict. No writes."""
    code_root = code_root.resolve()
    stacks: list[str] = []
    markers_found: list[str] = []
    entry_hints: list[str] = []
    test_setup: list[str] = []
    ci: list[str] = []
    agent_files: list[str] = []
    census: dict[str, int] = {}
    file_count = 0

    # marker files: full-depth scan for known names is cheap enough when
    # bounded; we scan to depth 4 for markers, depth 2 for census.
    for f, depth, is_dir in _iter_files(code_root, max_depth=4):
        rel = f.relative_to(code_root).as_posix()
        name = f.name
        if is_dir:
            if depth <= 2 and name in TEST_DIR_NAMES and rel not in test_setup:
                test_setup.append(rel)
            if depth <= 4:
                for cm in CI_MARKERS:
                    if (rel == cm or rel.startswith(cm + "/")) and cm not in ci:
                        ci.append(cm)
            continue
        file_count += 1
        if depth <= 2:
            top = rel.split("/", 1)[0]
            census[top] = census.get(top, 0) + 1
        if name in STACK_MARKERS and depth <= 3:
            stack = STACK_MARKERS[name]
            if stack not in stacks:
                stacks.append(stack)
            markers_found.append(rel)
        if name in TEST_MARKERS:
            test_setup.append(rel)
        if depth <= 2 and name.lower() in {
                "main.py", "cli.py", "app.py", "index.js", "index.ts",
                "main.go", "main.rs", "main.ts", "main.js"}:
            entry_hints.append(rel)
        if depth <= 4:
            for af in AGENT_FILES:
                if rel == af or rel.startswith(af + "/"):
                    if rel not in agent_files:
                        agent_files.append(rel)
            for cm in CI_MARKERS:
                if rel == cm or rel.startswith(cm + "/"):
                    if cm not in ci:
                        ci.append(cm)
        # test dirs
        if depth <= 2:
            parent = f.parent.name
            if parent in TEST_DIR_NAMES and rel.count("/") <= 2:
                tdir = f.parent.relative_to(code_root).as_posix()
                if tdir not in test_setup:
                    test_setup.append(tdir)

    # node package name + scripts hint
    pkg = code_root / "package.json"
    node_name = None
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            node_name = data.get("name")
        except Exception:
            pass

    # python project name from pyproject
    pyproj = code_root / "pyproject.toml"
    py_name = None
    if pyproj.is_file():
        try:
            for line in pyproj.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("name"):
                    py_name = line.split("=", 1)[1].strip().strip('"\'')
                    break
        except Exception:
            pass

    return {
        "code_root": str(code_root),
        "project": py_name or node_name,
        "stacks": stacks,
        "markers": sorted(markers_found),
        "entry_hints": sorted(entry_hints),
        "test_setup": sorted(set(test_setup)),
        "ci": sorted(ci),
        "agent_files": sorted(agent_files),
        "file_count_scanned": file_count,
        "top_level_census": dict(sorted(census.items(),
                                        key=lambda kv: -kv[1])[:15]),
    }


MAP_TAG = "codebase-map"


def _render_body(result: dict[str, Any]) -> str:
    lines = [
        "## Summary",
        "",
        f"Auto-generated codebase map from `tenx scan` "
        f"({result['file_count_scanned']} files scanned).",
        "",
        f"- project: {result['project'] or 'unnamed'}",
        f"- code root: `{result['code_root']}`",
        f"- stacks: {', '.join(result['stacks']) or 'none detected'}",
        f"- tests: {', '.join(result['test_setup']) or 'none found'}",
        f"- CI: {', '.join(result['ci']) or 'none found'}",
        f"- agent instruction files: "
        f"{', '.join(result['agent_files']) or 'none'}",
        "",
        "## Stack markers",
        "",
    ]
    lines += [f"- `{m}`" for m in result["markers"]] or ["- none"]
    lines += ["", "## Entry-point hints", ""]
    lines += [f"- `{e}`" for e in result["entry_hints"]] or ["- none"]
    lines += ["", "## Top-level census", ""]
    for name, n in result["top_level_census"].items():
        lines.append(f"- `{name}` — {n} file(s)")
    lines += [
        "",
        "## Notes",
        "",
        "Regenerate with `tenx scan --write`. Manual additions below this "
        "line are preserved only if you keep the `codebase-map` tag; the "
        "body above is rewritten on each scan.",
    ]
    return "\n".join(lines) + "\n"


def write_codebase_map(project_root: Path, code_root: Path,
                       result: dict[str, Any]) -> str:
    """Upsert the DOC artifact tagged `codebase-map`. Returns rel path."""
    from .activity import append_entry
    from .artifacts import (Artifact, create_artifact, load_artifact,
                            load_harness, today)

    harness = load_harness(project_root)
    existing = None
    for a in harness.by_type("doc"):
        tags = a.meta.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        if MAP_TAG in [str(t) for t in tags]:
            existing = a
            break

    body = _render_body(result)
    if existing is not None:
        existing.meta["updated"] = today()
        existing.body = body
        existing.path.write_text(existing.render(), encoding="utf-8")
        art = existing
        verb = "updated"
    else:
        art = create_artifact(
            project_root, "doc", "Codebase map",
            extra_meta={"tags": [MAP_TAG], "status": "complete"},
            body=body,
        )
        verb = "created"

    append_entry(
        project_root,
        f"codebase map {verb} from tenx scan "
        f"({result['file_count_scanned']} files, "
        f"stacks: {', '.join(result['stacks']) or 'none'})",
        entry_type="progress",
        ref=art.id,
    )
    try:
        return art.path.relative_to(harness.root).as_posix()
    except ValueError:
        return str(art.path)
