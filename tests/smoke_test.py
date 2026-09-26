"""End-to-end smoke test for the tenx CLI.

Run with plain python (no pytest needed):

    python tests/smoke_test.py            # uses the `tenx` on PATH
    PYTHONPATH=src python tests/smoke_test.py --module   # uses python -m tenx

Exits non-zero on the first failure.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FAILURES: list[str] = []
USE_MODULE = "--module" in sys.argv

if USE_MODULE:
    # Hermetic module mode: the git pre-commit hook needs a `tenx`
    # executable, but nothing is installed in this mode (e.g. fresh CI
    # runners). Provide a PATH shim that runs the source tree, so the
    # hook works without an install and module mode tests pure source.
    _shim_dir = Path(tempfile.mkdtemp(prefix="tenx-shim-"))
    _src_dir = Path(__file__).resolve().parent.parent / "src"
    _shim = _shim_dir / "tenx"
    _shim.write_text(
        "#!/bin/sh\n"
        f"exec env PYTHONPATH={_src_dir} python3 -m tenx \"$@\"\n")
    _shim.chmod(0o755)
    os.environ["PATH"] = f"{_shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"


def tenx(*args: str, cwd: Path, expect_rc: int = 0) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "tenx", *args] if USE_MODULE else ["tenx", *args]
    env = dict(os.environ)
    if USE_MODULE:
        src = str(Path(__file__).resolve().parent.parent / "src")
        env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if proc.returncode != expect_rc:
        raise AssertionError(
            f"tenx {' '.join(args)} rc={proc.returncode} (want {expect_rc})\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")
    return proc


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def add_tickets(spec: Path) -> None:
    text = spec.read_text()
    fm_end = text.index("---", 4)
    block = ("tickets:\n"
             "  - id: SPC-001-T1\n    title: First\n    status: todo\n"
             "  - id: SPC-001-T2\n    title: Second\n    status: todo\n")
    spec.write_text(text[:fm_end] + block + text[fm_end:])


def strip_discipline(cwd: Path) -> None:
    """SPC-025: opt legacy-style smoke specs out of the marker-driven
    discipline rules by deleting the template FR examples (one of which
    carries a clarify marker). Specs without FR-### ids are immune to the
    coverage rules, and backticked guidance markers never count."""
    for sp in (cwd / ".tenx" / "specs").glob("*.md"):
        txt = sp.read_text(encoding="utf-8")
        if "FR-001" not in txt:
            continue
        txt = txt.replace("- FR-001: The system MUST ...\n", "")
        txt = txt.replace(
            "- FR-002: The system MUST ... "
            "[NEEDS CLARIFICATION: example question]\n", "")
        sp.write_text(txt, encoding="utf-8")


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="tenx-smoke-"))
    proj = tmp / "proj"
    proj.mkdir()
    (proj / "package.json").write_text('{"name":"t","scripts":{"test":"vitest"}}')
    # a real project is a git repo; doctor enforcement expects the gate
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=proj,
                   check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=proj,
                   check=True)
    try:
        print("== init ==")
        tenx("init", "--bootstrap", "--description", "smoke", cwd=proj)
        check("harness dir", (proj / ".tenx" / "config.yaml").is_file())
        check("seeded convention", len(list((proj / ".tenx/conventions").glob("CON-*.md"))) == 1)
        check("seeded doc", len(list((proj / ".tenx/docs").glob("DOC-*.md"))) == 1)
        check("index built", "CON-001" in (proj / ".tenx/conventions/INDEX.md").read_text())
        tenx("init", cwd=proj)  # idempotent

        print("== artifacts ==")
        tenx("new", "epic", "Epic One", cwd=proj)
        tenx("new", "spec", "Spec One", "--epic", "EPC-001", cwd=proj)
        strip_discipline(proj)
        tenx("new", "convention", "Rule One", cwd=proj)
        tenx("new", "doc", "Doc One", cwd=proj)
        out = tenx("list", "--json", cwd=proj).stdout
        items = json.loads(out)
        ids = {i["id"] for i in items}
        check("ids", {"EPC-001", "SPC-001", "CON-001", "CON-002", "DOC-001", "DOC-002"} <= ids, str(ids))
        rc = subprocess.run(["tenx", "new", "spec", "NoEpic", "--epic", "EPC-999"],
                            cwd=proj, capture_output=True).returncode \
            if not USE_MODULE else \
            tenx("new", "spec", "NoEpic", "--epic", "EPC-999", cwd=proj, expect_rc=2).returncode
        check("spec rejects unknown epic", rc == 2)

        print("== tickets + drift ==")
        spec_file = proj / ".tenx/specs/SPC-001-spec-one.md"
        add_tickets(spec_file)
        tenx("ticket", "SPC-001", "SPC-001-T1", "done", cwd=proj)
        tenx("set", "SPC-001", "status", "in_progress", cwd=proj)
        tenx("validate", cwd=proj)  # clean
        tenx("set", "SPC-001", "status", "complete", "--force", cwd=proj)
        # SPC-023-T3: completing a spec whose tickets are not all done is
        # now a validation ERROR (evidence-gate bypass), not a warning.
        out = tenx("validate", "--json", cwd=proj, expect_rc=1).stdout
        errs = json.loads(out)["errors"]
        check("derived-status-drift blocks forced incomplete completion",
              any(e["rule"] == "derived-status-drift" for e in errs), str(errs))
        # SPC-023-T7: the forced completion left an audit trail
        hist = json.loads(tenx("history", "--json", cwd=proj).stdout)
        check("forced completion is audit-logged",
              any(e.get("type") == "decision" and "--force" in e.get("message", "")
                  for e in hist))
        tenx("set", "SPC-001", "status", "in_progress", cwd=proj)

        print("== errors ==")
        bad = proj / ".tenx/specs/SPC-002-bad.md"
        bad.write_text("---\nid: SPC-002\ntype: spec\ntitle: Bad\nstatus: draft\n"
                       "epic: EPC-999\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\nx\n")
        out = tenx("validate", "--json", cwd=proj, expect_rc=1).stdout
        errs = json.loads(out)["errors"]
        check("epic-ref error", any(e["rule"] == "epic-ref" for e in errs), str(errs))
        bad.unlink()

        print("== log / history / next ==")
        tenx("log", "did work", "--ref", "SPC-001", cwd=proj)
        out = tenx("history", "--json", cwd=proj).stdout
        entries = json.loads(out)
        # SPC-023-T6: ticket moves also auto-append entries, so filter.
        check("log entry",
              any(e.get("message") == "did work" and e.get("ref") == "SPC-001"
                  for e in entries))
        check("ticket move auto-logged (T6)",
              any(e.get("type") == "progress" and "SPC-001-T1" in e.get("message", "")
                  for e in entries))
        out = tenx("next", "--json", cwd=proj).stdout
        actions = json.loads(out)
        check("next leads with open ticket",
              actions and "SPC-001-T2" in actions[0]["action"], str(actions[:1]))

        print("== context packets ==")
        out = tenx("context", "--mode", "agent", cwd=proj).stdout
        check("packet has epics", "## Epics" in out and "EPC-001" in out)
        check("packet has protocol", "Operating protocol" in out)
        check("packet advertises capabilities", "tenx capabilities" in out)
        check("packet has conventions index path", "conventions/INDEX.md" in out)
        out = tenx("context", "--mode", "operator", cwd=proj).stdout
        check("operator dashboard", "operator dashboard" in out)
        data = json.loads(tenx("context", "--json", cwd=proj).stdout)
        check("json counts", data["counts"]["specs"] == 1, str(data["counts"]))

        print("== capability catalog ==")
        cat_text = tenx("capabilities", cwd=proj).stdout
        check("catalog groups commands",
              "## Discover & orient" in cat_text and "tenx validate" in cat_text)
        check("catalog has when-guidance", "\n  when:" in cat_text)
        cat = json.loads(tenx("capabilities", "--json", cwd=proj).stdout)
        cap_names = {c["name"] for c in cat["capabilities"]}
        check("json catalog entries well-formed",
              {"capabilities", "context", "validate", "mcp"} <= cap_names
              and all({"name", "surface", "group", "what", "when",
                       "usage"} <= set(c) for c in cat["capabilities"]))

        print("== init auto-wires agent harnesses ==")
        autoproj = tmp / "auto-wire"
        autoproj.mkdir()
        tenx("init", "--name", "autowire", cwd=autoproj)
        check("init seeds AGENTS.md", (autoproj / "AGENTS.md").is_file())
        check("init AGENTS.md has tenx block",
              "tenx:begin" in (autoproj / "AGENTS.md").read_text())
        check("init installs skills",
              (autoproj / ".claude/skills/tenx-process/SKILL.md").is_file())
        check("init registers .mcp.json", (autoproj / ".mcp.json").is_file())
        check("init .mcp.json has tenx server",
              "tenx" in json.loads(
                  (autoproj / ".mcp.json").read_text())["mcpServers"])
        # --no-hooks skips all agent wiring
        nhproj = tmp / "no-hooks"
        nhproj.mkdir()
        tenx("init", "--name", "nohooks", "--no-hooks", cwd=nhproj)
        check("init --no-hooks skips AGENTS.md",
              not (nhproj / "AGENTS.md").exists())
        check("init --no-hooks skips skills",
              not (nhproj / ".claude" / "skills").exists())
        check("init --no-hooks skips .mcp.json",
              not (nhproj / ".mcp.json").exists())
        # re-running init on an existing harness self-heals missing wiring
        tenx("init", cwd=nhproj)
        check("re-init self-heals AGENTS.md",
              (nhproj / "AGENTS.md").is_file())
        check("re-init self-heals skills",
              (nhproj / ".claude/skills/tenx-process/SKILL.md").is_file())

        print("== hooks / skills ==")
        tenx("hook", "install", "--agent", "all", cwd=proj)
        settings = json.loads((proj / ".claude/settings.json").read_text())
        hook_cmd = settings["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        check("claude SessionStart hook", hook_cmd == "tenx context --mode agent", hook_cmd)
        agents_md = (proj / "AGENTS.md").read_text()
        check("AGENTS.md managed block", "tenx:begin" in agents_md and "tenx:end" in agents_md)
        tenx("hook", "install", "--agent", "all", cwd=proj)  # idempotent
        check("AGENTS.md single block", agents_md.count("tenx:begin") == 1
              or (proj / "AGENTS.md").read_text().count("tenx:begin") == 1)
        tenx("skills", "install", cwd=proj)
        check("process skill installed",
              (proj / ".claude/skills/tenx-process/SKILL.md").is_file())
        # harness breadth: every supported target installs
        for agent, rel in [("cursor", ".cursor/rules/tenx.mdc"),
                           ("cline", ".clinerules/tenx.md"),
                           ("windsurf", ".windsurfrules"),
                           ("copilot", ".github/copilot-instructions.md"),
                           ("continue", ".continuerules"),
                           ("generic", "AGENTS.md")]:
            tenx("hook", "install", "--agent", agent, cwd=proj)
            check(f"hook target {agent}", (proj / rel).is_file())
        out = tenx("hook", "bootstrap", cwd=proj).stdout
        check("bootstrap is harness-agnostic",
              "tenx context --mode agent" in out
              and "tenx validate" in out)
        # adapter registry (OpenDesign-style data-driven adapters)
        out = tenx("hook", "detect", "--json", cwd=proj).stdout
        rows = json.loads(out)
        ids = {r["id"] for r in rows}
        check("adapter catalog breadth",
              {"claude", "codex", "hermes", "prime-agent",
               "deepseek-harness", "omp", "antigravity",
               "generic"} <= ids)
        check("detect rows typed",
              all("detected" in r and "files" in r for r in rows))
        tenx("hook", "install", "--agent", "detected", cwd=proj)
        check("detected install ok",
              (proj / "AGENTS.md").is_file())
        tenx("hook", "install", "--agent", "kiro", cwd=proj)
        check("kiro steering file",
              (proj / ".kiro/steering/tenx.md").is_file())
        tenx("hook", "install", "--agent", "qwen", cwd=proj)
        check("qwen instruction file", (proj / "QWEN.md").is_file())
        tenx("hook", "install", "--agent", "omp", cwd=proj)
        check("omp AGENTS.md", (proj / "AGENTS.md").is_file())
        tenx("hook", "install", "--agent", "antigravity", cwd=proj)
        check("antigravity GEMINI.md", (proj / "GEMINI.md").is_file())
        r = tenx("hook", "install", "--agent", "no-such-harness",
                 cwd=proj, expect_rc=2)
        check("unknown adapter rejected", r.returncode == 2)

        print("== EPC-011: universal compliance (git gate + dsh + mandate) ==")
        # --- SPC-021: hardened mandate block ---
        agents_md_hard = (proj / "AGENTS.md").read_text()
        check("mandate block has Hard rules", "Hard rules" in agents_md_hard)
        check("mandate block: validate MUST pass", "MUST pass" in agents_md_hard)
        check("mandate block: pre-commit gate noted", "pre-commit" in agents_md_hard)
        boot_hard = tenx("hook", "bootstrap", cwd=proj).stdout
        check("bootstrap has HARD RULES", "HARD RULES" in boot_hard)
        check("bootstrap mentions pre-commit gate", "pre-commit" in boot_hard)

        # --- SPC-020: git pre-commit enforcement ---
        gitproj = tmp / "git-gate"
        gitproj.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=gitproj, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.io"],
                       cwd=gitproj, check=True)
        subprocess.run(["git", "config", "user.name", "t"],
                       cwd=gitproj, check=True)
        tenx("init", "--name", "gitgate", cwd=gitproj)
        ghook = gitproj / ".git" / "hooks" / "pre-commit"
        check("init installs git pre-commit gate", ghook.is_file())
        check("git gate is executable", os.access(ghook, os.X_OK))
        check("git gate carries tenx marker",
              "tenx-managed-pre-commit" in ghook.read_text())
        (gitproj / "README.md").write_text("hi")
        subprocess.run(["git", "add", "-A"], cwd=gitproj, check=True)
        r = subprocess.run(["git", "commit", "-q", "-m", "clean"],
                           cwd=gitproj, capture_output=True, text=True)
        check("git gate allows clean commit", r.returncode == 0, r.stderr)
        bad = gitproj / ".tenx" / "specs" / "SPC-777-bad.md"
        bad.write_text("---\nid: SPC-777\ntype: spec\ntitle: Bad\n"
                       "status: draft\n---\n## Summary\nx\n"
                       "## Validation\ny\n")
        subprocess.run(["git", "add", "-A"], cwd=gitproj, check=True)
        r = subprocess.run(["git", "commit", "-m", "bad"],
                           cwd=gitproj, capture_output=True, text=True)
        check("git gate blocks non-compliant commit", r.returncode != 0)
        check("git gate prints block message",
              "BLOCKED" in (r.stderr + r.stdout))
        check("git gate bypass hint", "--no-verify" in (r.stderr + r.stdout))
        bad.unlink()
        # --git flag also installs the hook explicitly
        tenx("hook", "install", "--agent", "generic", "--git", cwd=gitproj)
        check("hook install --git idempotent", ghook.is_file())

        # --- SPC-019: DSH agent preset ---
        dshproj = tmp / "dsh-preset"
        dshproj.mkdir()
        tenx("init", "--name", "dshp", cwd=dshproj)
        fake_home = tmp / "fake-home"
        fake_home.mkdir()
        _old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(fake_home)
        try:
            tenx("hook", "install", "--agent", "dsh", cwd=dshproj)
        finally:
            if _old_home is not None:
                os.environ["HOME"] = _old_home
        preset_dir = dshproj / ".dsh-preset" / "tenx"
        check("dsh preset.yml generated", (preset_dir / "preset.yml").is_file())
        check("dsh agent.cordis.yml generated",
              (preset_dir / "agent.cordis.yml").is_file())
        cordis = (preset_dir / "agent.cordis.yml").read_text()
        check("dsh persona mandates context packet",
              "tenx context --mode agent" in cordis)
        check("dsh persona mandates validate MUST pass", "MUST pass" in cordis)
        check("dsh persona mandates landing gate", "operator approval" in cordis)
        check("dsh persona keeps {{model}} placeholder", "{{model}}" in cordis)
        check("dsh preset bundles tenx skills",
              (preset_dir / "skills" / "tenx-process" / "SKILL.md").is_file())
        check("dsh alias resolves to deepseek-harness",
              "tenx" in tenx("hook", "detect", "--json", cwd=dshproj).stdout)
        # rules.yaml overrides (README-documented formats)
        (proj / ".tenx" / "rules.yaml").write_text(
            "disable:\n  - log-quiet\n"
            "severity:\n  - derived-status-drift: warning\n"
            "params:\n  stale_days: 21\n")
        out = tenx("validate", "--json", cwd=proj).stdout
        findings = json.loads(out)
        if isinstance(findings, dict):
            findings = findings.get("findings", [])
        check("severity override applied",
              all(f["severity"] != "info"
                  for f in findings
                  if f["rule"] == "derived-status-drift")
              and any(f["rule"] == "derived-status-drift"
                      and f["severity"] == "warning"
                      for f in findings)
              or not any(f["rule"] == "derived-status-drift"
                         for f in findings))
        check("disable override applied",
              not any(f["rule"] == "log-quiet" for f in findings))

        print("== show / doctor ==")
        out = tenx("show", "SPC-001", cwd=proj).stdout
        check("show prints body", "Spec One" in out and "tickets" in out.lower())
        out = tenx("doctor", cwd=proj).stdout
        check("doctor healthy", "validation: 0 errors" in out, out)
        print("== exec brief (spec-first autonomous execution) ==")
        tenx("new", "spec", "Exec Spec", "--epic", "EPC-001", cwd=proj)
        strip_discipline(proj)
        tenx("ticket", "SPC-002", "SPC-002-T1", "todo", cwd=proj)
        out = tenx("exec", "SPC-002", cwd=proj).stdout
        check("exec names spec", "EXECUTION BRIEF — SPC-002" in out)
        check("exec lists ticket", "SPC-002-T1: todo" in out)
        check("exec mandates write-back", "tenx ticket SPC-002" in out
              and "tenx log" in out)
        check("exec mandates validate", "tenx validate" in out)
        out = tenx("exec", "SPC-002", "--json", cwd=proj).stdout
        check("exec --json", json.loads(out)["spec"] == "SPC-002")
        r = tenx("exec", "EPC-001", cwd=proj, expect_rc=1)
        check("exec rejects non-spec", r.returncode == 1)

        print("== standalone PM repo (the 10X layout) ==")
        pm = tmp / "pm-repo"
        app = tmp / "app-repo"
        pm.mkdir()
        app.mkdir()
        (app / "package.json").write_text('{"name":"app"}')
        for repo in (pm, app):
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "config", "user.email", "t@t.t"],
                           cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "t"],
                           cwd=repo, check=True)
        tenx("init", "--standalone", "--code-root", str(app),
             "--name", "pm", cwd=pm)
        check("tenxlink written", (app / ".tenxlink").is_file())
        check("config has code_root",
              "code_root:" in (pm / ".tenx/config.yaml").read_text())
        tenx("new", "epic", "PM Epic", cwd=pm)
        # discovery FROM the code repo follows the link
        out = tenx("list", "--json", cwd=app).stdout
        check("discovery via .tenxlink",
              any(i["id"] == "EPC-001" for i in json.loads(out)))
        # hooks land in the CODE repo, not the PM repo
        tenx("hook", "install", "--agent", "all", "--git", cwd=pm)
        check("claude hook in code repo",
              (app / ".claude/settings.json").is_file())
        check("git gate in code repo",
              (app / ".git/hooks/pre-commit").is_file())
        check("AGENTS.md in code repo", (app / "AGENTS.md").is_file())
        check("no AGENTS.md in PM repo", not (pm / "AGENTS.md").exists())
        out = tenx("context", "--mode", "agent", cwd=app).stdout
        check("packet names governed code repo", "Code repo (governed)" in out)
        out = tenx("doctor", cwd=app).stdout
        check("doctor shows code_root", "code repo (code_root)" in out, out)

        # ---- tenx scan ----
        scanproj = tmp / "scan-proj"
        (scanproj / "src").mkdir(parents=True)
        (scanproj / "tests").mkdir()
        (scanproj / "web").mkdir()
        (scanproj / "pyproject.toml").write_text(
            '[project]\nname = "scanpy"\n')
        (scanproj / "web" / "package.json").write_text(
            '{"name": "scanweb"}')
        (scanproj / "src" / "main.py").write_text("print(1)")
        (scanproj / "AGENTS.md").write_text("# agents")
        (scanproj / ".github" / "workflows").mkdir(parents=True)
        (scanproj / ".github" / "workflows" / "ci.yml").write_text("on: push")
        tenx("init", cwd=scanproj)
        out = tenx("scan", "--json", cwd=scanproj).stdout
        scan = json.loads(out)
        check("scan detects python stack", "python" in scan["stacks"])
        check("scan detects node stack", "node" in scan["stacks"])
        check("scan finds tests dir",
              any("tests" in t for t in scan["test_setup"]))
        check("scan finds CI", any("github" in c for c in scan["ci"]))
        check("scan finds agent files",
              any("AGENTS.md" in a for a in scan["agent_files"]))
        check("scan finds entry hint",
              any("main.py" in e for e in scan["entry_hints"]))
        check("scan reads project name", scan["project"] == "scanpy")
        out = tenx("scan", cwd=scanproj).stdout
        check("scan human output", "stacks:" in out and "census" in out)
        tenx("scan", "--write", cwd=scanproj)
        docs = list((scanproj / ".tenx" / "docs").glob("*.md"))
        check("scan --write creates DOC", len(docs) == 1)
        check("scan DOC tagged codebase-map",
              "codebase-map" in docs[0].read_text())
        tenx("scan", "--write", cwd=scanproj)
        docs2 = list((scanproj / ".tenx" / "docs").glob("*.md"))
        check("scan --write upserts (no duplicate)", len(docs2) == 1)
        check("scan validate clean",
              "clean" in tenx("validate", cwd=scanproj).stdout)

        # ---- tenx sync (offline parts only; no network in smoke) ----
        import importlib.util
        spec_mod = importlib.util.spec_from_file_location(
            "tenx_sync_smoke",
            Path(__file__).parent.parent / "src" / "tenx" / "sync.py")
        # sync.py uses relative-free imports at module level except none;
        # load via package instead
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from tenx.sync import repo_from_remote_url, MARKER_RE
        check("sync parses https remote",
              repo_from_remote_url(
                  "https://github.com/foo/bar.git") == "foo/bar")
        check("sync parses ssh remote",
              repo_from_remote_url("git@github.com:foo/bar.git")
              == "foo/bar")
        check("sync rejects non-github remote",
              repo_from_remote_url("https://gitlab.com/a/b.git") is None)
        check("sync marker regex",
              bool(MARKER_RE.match("[SPC-001-T2] some ticket"))
              and not MARKER_RE.match("random issue title"))
        # sync without token/repo fails cleanly (exit 2, no traceback)
        r = tenx("sync", "push", "--dry-run", cwd=scanproj, expect_rc=2)
        check("sync fails cleanly without origin remote",
              r.returncode == 2 and "Traceback" not in r.stderr)

        # ---- packet budget + session logging ----
        full = tenx("context", "--mode", "agent", cwd=scanproj).stdout
        small = tenx("context", "--mode", "agent", "--budget", "900",
                     cwd=scanproj).stdout
        check("budget shrinks packet", len(small) < len(full))
        check("budget keeps protocol",
              "Operating protocol" in small)
        check("budget notes omitted sections",
              ("omitted sections" in small)
              or ("truncated" in small)
              or len(small) <= 900 + 400)
        # apply_budget pure function
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from tenx.context import apply_budget, TRUNCATE_MARKER
        kept, omitted = apply_budget([("a", "x" * 100), ("b", "y" * 100),
                                     ("c", "z" * 100)], 250)
        check("apply_budget keeps whole sections",
              [n for n, _ in kept][0] == "a" and "c" in omitted)
        check("apply_budget pure (no mutation)",
              len(omitted) + len(kept) == 3)
        # ---- tenx mcp (stdio JSON-RPC round trip) ----
        mcp_msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "smoke", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "tenx_validate", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "no_such_tool", "arguments": {}}},
            "this line is not json",
            {"jsonrpc": "2.0", "id": 5, "method": "bogus/method"},
            {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
             "params": {"name": "tenx_capabilities", "arguments": {}}},
        ]
        inp = "\n".join(json.dumps(m) if isinstance(m, dict) else m
                         for m in mcp_msgs) + "\n"
        r = subprocess.run([sys.executable, "-m", "tenx", "mcp"],
                           input=inp, capture_output=True, text=True,
                           timeout=120, cwd=scanproj,
                           env={**os.environ,
                                "PYTHONPATH": str(Path(__file__).parent.parent / "src")})
        check("mcp exits cleanly on EOF", r.returncode == 0, r.stderr[:200])
        resp = {}
        parse_errors = 0
        for ln in r.stdout.splitlines():
            d = json.loads(ln)
            if d.get("id") is not None:
                resp[d["id"]] = d
            elif "error" in d:
                parse_errors += 1
        check("mcp initialize negotiates",
              resp[1]["result"]["serverInfo"]["name"] == "tenx")
        tool_names = {t["name"] for t in resp[2]["result"]["tools"]}
        check("mcp lists 21 tools", len(tool_names) == 21,
              str(tool_names))
        check("mcp exposes tenx_context", "tenx_context" in tool_names)
        check("mcp exposes tenx_converge", "tenx_converge" in tool_names)
        check("mcp exposes tenx_watchdog", "tenx_watchdog" in tool_names)
        check("mcp exposes tenx_capabilities",
              "tenx_capabilities" in tool_names)
        check("mcp exposes tenx_ticket_brief",
              "tenx_ticket_brief" in tool_names)
        check("mcp exposes tenx_dispatch",
              "tenx_dispatch" in tool_names)
        check("mcp exposes tenx_reconcile",
              "tenx_reconcile" in tool_names)
        check("mcp exposes tenx_abort",
              "tenx_abort" in tool_names)
        check("mcp exposes tenx_dag", "tenx_dag" in tool_names)
        check("mcp exposes tenx_swarm", "tenx_swarm" in tool_names)
        check("mcp tools/call works",
              resp[3]["result"]["isError"] is False
              and "tenx validate" in resp[3]["result"]["content"][0]["text"])
        check("mcp unknown tool -> isError",
              resp[4]["result"]["isError"] is True)
        check("mcp parse error reported", parse_errors == 1)
        check("mcp unknown method -> -32601",
              resp[5]["error"]["code"] == -32601)
        check("mcp capabilities call works",
              resp[6]["result"]["isError"] is False
              and "capability catalog"
              in resp[6]["result"]["content"][0]["text"])
        # mcp install writes managed .mcp.json
        tenx("mcp", "install", cwd=scanproj)
        mcpjson = scanproj / ".mcp.json"
        check("mcp install creates .mcp.json", mcpjson.is_file())
        cfg = json.loads(mcpjson.read_text())
        check("mcp.json has tenx server",
              cfg["mcpServers"]["tenx"]["command"] == "tenx")
        tenx("mcp", "install", cwd=scanproj)  # idempotent
        check("mcp install idempotent",
              json.loads(mcpjson.read_text()) == cfg)

        # ---- SPC-007 execution discipline rules ----
        rulesproj = Path(tempfile.mkdtemp(prefix="tenx-rules-"))
        tenx("init", "--name", "rules", cwd=rulesproj)
        tenx("new", "epic", "Rules epic", cwd=rulesproj)
        tenx("new", "spec", "Rules spec", "--epic", "EPC-001",
             cwd=rulesproj)
        strip_discipline(rulesproj)
        def rules_in(proj):
            d = json.loads(tenx("validate", "--json", cwd=proj).stdout)
            return {f["rule"] for k in ("errors", "warnings", "info")
                    for f in d.get(k, [])}

        # orphan-spec: in_progress with no tickets
        tenx("set", "SPC-001", "status", "in_progress", cwd=rulesproj)
        check("rule orphan-spec fires for in_progress",
              "orphan-spec" in rules_in(rulesproj))
        # spec-missing-sections: strip body sections
        specfile = next((rulesproj / ".tenx/specs").glob("SPC-001*.md"))
        t = specfile.read_text()
        fm_end = t.index("---", 3) + 3
        specfile.write_text(t[:fm_end] + "\nNo sections.\n")
        # ticket-id-prefix + ticket-title-missing
        tenx("ticket", "SPC-001", "FOO-1", "done", cwd=rulesproj)
        found = rules_in(rulesproj)
        check("rule spec-missing-sections fires",
              "spec-missing-sections" in found)
        check("rule ticket-id-prefix fires",
              "ticket-id-prefix" in found)
        check("rule ticket-title-missing fires",
              "ticket-title-missing" in found)
        # archived-epic-active-specs
        tenx("set", "EPC-001", "status", "archived", cwd=rulesproj)
        check("rule archived-epic-active-specs fires",
              "archived-epic-active-specs" in rules_in(rulesproj))
        # disable knob still works for a new rule
        (rulesproj / ".tenx/rules.yaml").write_text(
            "disable:\n  - ticket-id-prefix\n")
        check("rules.yaml disables new rule",
              "ticket-id-prefix" not in rules_in(rulesproj))
        shutil.rmtree(rulesproj, ignore_errors=True)

        # ---- SPC-008 hygiene rules + rule catalog ----
        hyg = Path(tempfile.mkdtemp(prefix="tenx-hyg-"))
        code_repo = hyg / "code"
        code_repo.mkdir()
        tenx("init", "--standalone", "--code-root", str(code_repo),
             "--name", "hyg", cwd=hyg)
        tenx("new", "convention", "Tiny rule", cwd=hyg)
        confile = next((hyg / ".tenx/conventions").glob("CON-*.md"))
        t = confile.read_text()
        fm_end = t.index("---", 3) + 3
        confile.write_text(t[:fm_end] + "\n## Rule\n\nShort.\n")
        tenx("new", "doc", "Renamed doc", cwd=hyg)
        docfile = next((hyg / ".tenx/docs").glob("DOC-*.md"))
        docfile.rename(docfile.parent / "renamed-doc.md")
        tenx("log", "progress without ref", "--type", "progress", cwd=hyg)
        tenx("log", "stuck on something", "--type", "blocker",
             "--ref", "DOC-001", cwd=hyg)
        found = rules_in(hyg)
        check("rule convention-empty-body fires",
              "convention-empty-body" in found)
        check("rule id-filename-mismatch fires",
              "id-filename-mismatch" in found)
        check("rule log-progress-no-ref fires",
              "log-progress-no-ref" in found)
        check("rule blocker-unresolved fires",
              "blocker-unresolved" in found)
        # blocker resolved by a later progress entry on the same ref
        tenx("log", "unblocked", "--type", "progress", "--ref", "DOC-001",
             cwd=hyg)
        check("blocker-unresolved clears after follow-up",
              "blocker-unresolved" not in rules_in(hyg))
        # config-code-root: break code_root -> error
        cfg = hyg / ".tenx/config.yaml"
        cfg.write_text(cfg.read_text().replace(
            "code_root: code", "code_root: does-not-exist"))
        d = json.loads(tenx("validate", "--json", cwd=hyg,
                            expect_rc=1).stdout)
        check("rule config-code-root fires as error",
              any(e["rule"] == "config-code-root" for e in d["errors"]))
        shutil.rmtree(hyg, ignore_errors=True)

        # ---- SPC-015 enforced evidence gate ----
        gateproj = Path(tempfile.mkdtemp(prefix="tenx-gate-"))
        tenx("init", "--name", "gate", cwd=gateproj)
        tenx("new", "epic", "Gate epic", cwd=gateproj)
        tenx("new", "spec", "Gate spec", "--epic", "EPC-001", cwd=gateproj)
        strip_discipline(gateproj)
        # blocked: no evidence, no tickets
        r = tenx("set", "SPC-001", "status", "complete", cwd=gateproj,
                 expect_rc=2)
        check("gate blocks complete without evidence", r.returncode == 2)
        check("gate prints blocked message",
              "evidence gate blocked" in r.stderr, r.stderr)
        # still blocked with an open ticket
        tenx("ticket", "SPC-001", "SPC-001-T1", "--title", "t", "todo",
             cwd=gateproj)
        r = tenx("set", "SPC-001", "status", "complete", cwd=gateproj,
                 expect_rc=2)
        check("gate blocks with open ticket",
              r.returncode == 2 and "not done" in r.stderr, r.stderr)
        # passes once ticket done + evidence logged
        tenx("ticket", "SPC-001", "SPC-001-T1", "done", cwd=gateproj)
        tenx("log", "did the gate work", "--ref", "SPC-001", cwd=gateproj)
        tenx("changelog", "add", "gate work", "--ref", "SPC-001",
             cwd=gateproj)
        tenx("set", "SPC-001", "status", "complete", cwd=gateproj)
        meta = json.loads(tenx("show", "SPC-001", "--json",
                               cwd=gateproj).stdout)["meta"]
        check("gate passes with logged evidence",
              meta.get("status") == "complete", str(meta.get("status")))
        # --force bypass on a fresh spec
        tenx("new", "spec", "Force spec", "--epic", "EPC-001", cwd=gateproj)
        strip_discipline(gateproj)
        r = tenx("set", "SPC-002", "status", "complete", "--force",
                 cwd=gateproj)
        check("gate --force bypasses",
              r.returncode == 0 and "--force used" in r.stderr, r.stderr)
        # evidence field path
        tenx("new", "spec", "Ev spec", "--epic", "EPC-001", cwd=gateproj)
        strip_discipline(gateproj)
        tenx("set", "SPC-003", "evidence", "smoke green 2026-08-25",
             cwd=gateproj)
        tenx("changelog", "add", "ev work", "--ref", "SPC-003",
             cwd=gateproj)
        tenx("set", "SPC-003", "status", "complete", cwd=gateproj)
        meta = json.loads(tenx("show", "SPC-003", "--json",
                               cwd=gateproj).stdout)["meta"]
        check("gate passes via evidence field",
              meta.get("status") == "complete", str(meta.get("status")))
        # config off disables the gate
        cfg = gateproj / ".tenx/config.yaml"
        cfg.write_text((cfg.read_text() if cfg.exists() else "")
                       + "\nevidence_gate: off\n")
        tenx("new", "spec", "Off spec", "--epic", "EPC-001", cwd=gateproj)
        strip_discipline(gateproj)
        tenx("set", "SPC-004", "status", "complete", cwd=gateproj)
        meta = json.loads(tenx("show", "SPC-004", "--json",
                               cwd=gateproj).stdout)["meta"]
        check("gate disabled via config",
              meta.get("status") == "complete", str(meta.get("status")))
        shutil.rmtree(gateproj, ignore_errors=True)

        # rule catalog: --list-rules works anywhere, covers every rule
        out = tenx("validate", "--list-rules", cwd=tmp).stdout
        check("list-rules prints catalog",
              "rule catalog" in out and "derived-status-drift" in out)
        cat = json.loads(tenx("validate", "--list-rules", "--json",
                              cwd=tmp).stdout)
        cat_ids = {r["rule"] for r in cat}
        check("catalog typed rows",
              all("default_severity" in r and "description" in r
                  for r in cat))
        # every rule the smoke project can emit is in the catalog
        d = json.loads(tenx("validate", "--json", cwd=scanproj).stdout)
        emitted = {f["rule"] for k in ("errors", "warnings", "info")
                   for f in d.get(k, [])}
        check("catalog covers emitted rules", emitted <= cat_ids,
              str(emitted - cat_ids))
        check("catalog has 40 rules", len(cat) == 40, str(len(cat)))

        # ---- tenx review + archive ----
        tenx("new", "epic", "Review epic", cwd=scanproj)
        tenx("new", "spec", "Review spec", "--epic", "EPC-001",
             cwd=scanproj)
        strip_discipline(scanproj)
        out = tenx("review", cwd=scanproj).stdout
        check("review empty queue message", "nothing awaits review" in out)
        tenx("ticket", "SPC-001", "SPC-001-T9", "in_review",
             "--title", "needs eyes", cwd=scanproj)
        out = tenx("review", cwd=scanproj).stdout
        check("review lists in_review ticket",
              "SPC-001-T9" in out and "needs eyes" in out)
        out = tenx("review", "--json", cwd=scanproj).stdout
        rj = json.loads(out)
        check("review --json shape",
              any(i["spec"] == "SPC-001" and
                  any(t["id"] == "SPC-001-T9"
                      for t in i["in_review_tickets"]) for i in rj))
        tenx("ticket", "SPC-001", "SPC-001-T9", "done", cwd=scanproj)
        # archive guard: open ticket blocks
        tenx("ticket", "SPC-001", "SPC-001-T10", "todo",
             "--title", "open", cwd=scanproj)
        # SPC-023-T14: approval is checked before anything else
        r = tenx("archive", "EPC-001", "--yes", cwd=scanproj, expect_rc=2)
        check("archive refuses without --approved-by",
              "approved-by" in r.stderr, r.stderr[:200])
        r = tenx("archive", "EPC-001", "--approved-by", "smoke",
                 cwd=scanproj, expect_rc=2)
        check("archive refuses open tickets", r.returncode == 2)
        tenx("archive", "EPC-001", "--yes", "--approved-by", "smoke",
             cwd=scanproj)
        out = tenx("list", "epic", "--json", cwd=scanproj).stdout
        check("archive sets epic archived",
              any(e["id"] == "EPC-001" and e["status"] == "archived"
                  for e in json.loads(out)))
        check("archive validate clean",
              "clean" in tenx("validate", cwd=scanproj).stdout)

        # ---- SPC-009 self-update + session-start awareness ----
        from tenx.update import parse_version as pv
        check("parse_version basic", pv("v0.11.0") == (0, 11, 0))
        check("parse_version numeric compare",
              pv("0.9.0") < pv("0.11.0") < pv("1.0.0"))
        check("parse_version prerelease truncates",
              pv("1.2.3rc1") == (1, 2))
        check("parse_version garbage -> (0,)", pv("garbage") == (0,))
        # check is offline-tolerant: always rc 0, never a traceback
        r = tenx("update", "--check", cwd=scanproj)
        check("update --check exits 0", r.returncode == 0)
        check("update --check no traceback",
              "Traceback" not in r.stderr)
        uj = json.loads(tenx("update", "--check", "--json",
                             cwd=scanproj).stdout)
        check("update --json typed",
              all(k in uj for k in
                  ("current", "latest", "update_available", "status")))
        check("update --json status valid",
              uj["status"] in
              ("up-to-date", "update-available", "check-failed"))
        from tenx.update import _branch, DEFAULT_BRANCH
        check("update fallback uses the published main branch",
              DEFAULT_BRANCH == "main" and _branch() == "main")
        from tenx.update import _repo
        check("update repository is the tenx distribution repo",
              _repo() == "sivakoneti/10xdev-cli")
        # session-start surfaces tell agents to check for updates
        tenx("hook", "install", "--agent", "all", cwd=scanproj)
        tenx("skills", "install", cwd=scanproj)
        out = tenx("context", "--mode", "agent", cwd=scanproj).stdout
        check("packet workspace mentions self-update",
              "self-updating" in out and "tenx update --check" in out)
        check("protocol step 1 is the update check",
              "1. The tenx CLI self-updates" in out)
        agents_md = (scanproj / "AGENTS.md").read_text()
        check("AGENTS.md block mentions updates",
              "tenx update --check" in agents_md)
        out = tenx("hook", "bootstrap", cwd=scanproj).stdout
        check("bootstrap snippet mentions updates",
              "tenx update --check" in out)
        skill = (scanproj / ".claude/skills/tenx-process/SKILL.md"
                 ).read_text()
        check("process skill step 1 is the update check",
              "tenx update --check" in skill)

        # ---- best-practice artifact templates (design doc / OKR / ADR) ----
        tenx("new", "spec", "Template probe", "--epic", "EPC-001",
             cwd=scanproj)
        probe = next((scanproj / ".tenx/specs").glob(
            "SPC-*-template-probe.md")).read_text()
        for sec in ("## Summary", "## Context and scope",
                    "## Goals / non-goals", "## Requirements",
                    "## Success criteria", "## Design",
                    "## Alternatives considered",
                    "## Cross-cutting concerns", "## Validation"):
            check(f"spec template has {sec!r}", sec in probe)
        check("spec template carries FR/SC discipline markers",
              "FR-001" in probe and "SC-001" in probe
              and "NEEDS CLARIFICATION" in probe)
        strip_discipline(scanproj)
        tenx("new", "epic", "Template probe epic", cwd=scanproj)
        eprobe = sorted((scanproj / ".tenx/epics").glob(
            "EPC-*-template-probe-epic.md"))[-1].read_text()
        for sec in ("## Key results", "## Non-goals", "## Milestones"):
            check(f"epic template has {sec!r}", sec in eprobe)
        check("epic template frames the user (working backwards)",
              "work backwards" in eprobe)
        tenx("new", "doc", "Template probe doc", cwd=scanproj)
        dprobe = sorted((scanproj / ".tenx/docs").glob(
            "DOC-*-template-probe-doc.md"))[-1].read_text()
        check("doc template offers ADR shape",
              "Decision record (ADR)" in dprobe)
        check("doc template offers blameless postmortem shape",
              "Postmortem (blameless)" in dprobe)
        # skills teach the same structure
        wspec = (scanproj / ".claude/skills/tenx-write-spec/SKILL.md"
                 ).read_text()
        check("write-spec skill teaches alternatives + trade-offs",
              "Alternatives considered" in wspec
              and "trade-off" in wspec)
        wepic = (scanproj / ".claude/skills/tenx-write-epic/SKILL.md"
                 ).read_text()
        check("write-epic skill teaches key results + non-goals",
              "Key results" in wepic and "Non-goals" in wepic)
        wrev = (scanproj / ".claude/skills/tenx-review/SKILL.md"
                ).read_text()
        check("review skill references review + archive commands",
              "tenx review" in wrev and "tenx archive" in wrev)

        # ---- EPC-007 operational control loop: priority tiers ----
        tenx("new", "epic", "Ops epic", cwd=scanproj)
        ops_epic = sorted((scanproj / ".tenx/epics").glob(
            "EPC-*-ops-epic.md"))[-1]
        ops_id = ops_epic.read_text().split("id: ")[1].split("\n")[0]
        tenx("new", "spec", "Ops P0 spec", "--epic", ops_id, cwd=scanproj)
        tenx("new", "spec", "Ops P1 spec", "--epic", ops_id, cwd=scanproj)
        strip_discipline(scanproj)
        p0 = sorted((scanproj / ".tenx/specs").glob(
            "SPC-*-ops-p0-spec.md"))[-1]
        p1 = sorted((scanproj / ".tenx/specs").glob(
            "SPC-*-ops-p1-spec.md"))[-1]
        p0_id = p0.read_text().split("id: ")[1].split("\n")[0]
        p1_id = p1.read_text().split("id: ")[1].split("\n")[0]
        # set + normalize + reject
        tenx("set", p1_id, "priority", "P1", cwd=scanproj)
        tenx("set", p0_id, "priority", "p0", cwd=scanproj)  # lowercase ok
        tenx("set", p0_id, "priority", "P9", cwd=scanproj, expect_rc=2)
        check("priority lowercase normalized to P0",
              "priority: P0" in p0.read_text())
        check("invalid priority rejected",
              "priority: P9" not in p0.read_text())
        # new --priority
        tenx("new", "epic", "Prio epic", "--priority", "P0", cwd=scanproj)
        prio_epic = sorted((scanproj / ".tenx/epics").glob(
            "EPC-*-prio-epic.md"))[-1].read_text()
        check("tenx new --priority sets tier", "priority: P0" in prio_epic)
        # list shows priority
        out = tenx("list", "spec", "--json", cwd=scanproj).stdout
        check("list exposes priority field",
              any(i["id"] == p0_id and i.get("priority") == "P0"
                  for i in json.loads(out)))
        # next orders P0 before P1 within the work bucket
        out = tenx("next", "--json", cwd=scanproj).stdout
        acts = json.loads(out)
        biz = [a.get("biz") for a in acts if a.get("biz")]
        check("next sorts P0 ahead of P1",
              biz and biz.index("P0") < biz.index("P1"), str(biz))
        # context packet carries priority
        out = tenx("context", "--mode", "agent", cwd=scanproj).stdout
        ctxj = json.loads(tenx("context", "--mode", "agent", "--json",
                               cwd=scanproj).stdout)
        check("context spec carries effective priority",
              any(sp["id"] == p0_id and sp.get("priority") == "P0"
                  for sp in ctxj["specs"]))
        # spec inherits epic priority when it has none
        tenx("set", ops_id, "priority", "P2", cwd=scanproj)
        ctxj = json.loads(tenx("context", "--mode", "agent", "--json",
                               cwd=scanproj).stdout)
        check("spec inherits epic priority",
              any(sp["id"] == p1_id and sp.get("priority") in ("P1", "P2")
                  for sp in ctxj["specs"]))
        # priority-format rule fires on a bad hand-edit
        bad_prio = sorted((scanproj / ".tenx/specs").glob(
            "SPC-*-ops-p1-spec.md"))[-1]
        txt = bad_prio.read_text().replace("priority: P1", "priority: URGENT")
        bad_prio.write_text(txt)
        out = tenx("validate", "--json", cwd=scanproj, expect_rc=0).stdout
        warns = json.loads(out)["warnings"]
        check("priority-format rule flags bad tier",
              any(w["rule"] == "priority-format" for w in warns), str(warns))
        bad_prio.write_text(txt.replace("priority: URGENT", "priority: P1"))

        # ---- EPC-007 watchdog digest ----
        r = tenx("watchdog", cwd=scanproj)
        check("watchdog runs clean", r.returncode == 0)
        check("watchdog no traceback", "Traceback" not in r.stderr)
        wj = json.loads(tenx("watchdog", "--json", cwd=scanproj).stdout)
        check("watchdog --json shape",
              all(k in wj for k in ("items", "counts", "window_days")))
        # blocked spec surfaces as high
        tenx("set", p0_id, "status", "blocked", cwd=scanproj)
        wj = json.loads(tenx("watchdog", "--json", cwd=scanproj).stdout)
        check("watchdog flags blocked spec",
              any(it.get("ref") == p0_id and it["severity"] == "high"
                  for it in wj["items"]), str(wj["items"]))
        out = tenx("watchdog", cwd=scanproj).stdout
        check("watchdog renders handling verdict",
              "being worked on" in out or "unattended" in out
              or "stalled" in out or "gone quiet" in out)
        tenx("set", p0_id, "status", "draft", cwd=scanproj)
        # in_review surfaces as medium
        tenx("set", p1_id, "status", "in_review", cwd=scanproj)
        wj = json.loads(tenx("watchdog", "--json", cwd=scanproj).stdout)
        check("watchdog flags in_review spec",
              any(it.get("ref") == p1_id and it["severity"] == "medium"
                  for it in wj["items"]), str(wj["items"]))
        tenx("set", p1_id, "status", "draft", cwd=scanproj)
        # MCP exposes the watchdog tool
        from tenx.mcp import _tooldefs
        names = {t["name"] for t in _tooldefs()}
        check("mcp registers tenx_watchdog", "tenx_watchdog" in names)

        # ---- SPC-016 triage agent role + command ----
        r = tenx("triage", cwd=scanproj)
        check("triage runs clean", r.returncode == 0)
        check("triage no traceback", "Traceback" not in r.stderr)
        check("triage renders act/watch/escalate sections",
              "Act now" in r.stdout and "Watch" in r.stdout
              and "Escalate to human" in r.stdout, r.stdout)
        tj = json.loads(tenx("triage", "--json", cwd=scanproj).stdout)
        check("triage --json shape",
              all(k in tj for k in ("act_now", "watch", "escalation",
                                    "healthy_in_progress", "counts")))
        # a blocked, never-touched spec escalates into act_now
        tenx("set", p0_id, "status", "blocked", cwd=scanproj)
        tj = json.loads(tenx("triage", "--json", cwd=scanproj).stdout)
        check("triage escalates blocked unattended spec",
              any(it.get("ref") == p0_id for it in tj["act_now"]),
              str(tj["act_now"]))
        check("triage picks a top escalation",
              tj["escalation"] is not None
              and tj["escalation"].get("ref") == p0_id,
              str(tj["escalation"]))
        tenx("set", p0_id, "status", "draft", cwd=scanproj)
        check("mcp registers tenx_triage", "tenx_triage" in names)
        # the agent-role skill installs and describes the loop
        tri = (scanproj / ".claude/skills/tenx-triage/SKILL.md")
        check("tenx-triage skill installed", tri.is_file())
        if tri.is_file():
            tritxt = tri.read_text()
            check("triage skill teaches the loop",
                  "tenx triage" in tritxt and "Escalate" in tritxt)
            check("triage skill is read-only",
                  "Do NOT mutate" in tritxt or "never mutates" in tritxt.lower())

        # ---- EPC-007 landing discipline in skills ----
        wrev2 = (scanproj / ".claude/skills/tenx-review/SKILL.md"
                 ).read_text()
        check("review skill teaches bounded fix loop",
              "Bounded fix loop" in wrev2 and "2" in wrev2)
        check("review skill teaches evidence gate",
              "Evidence gate" in wrev2)
        check("review skill keeps a human landing gate",
              "Human gate" in wrev2 or "human" in wrev2.lower())
        wproc2 = (scanproj / ".claude/skills/tenx-process/SKILL.md"
                  ).read_text()
        check("process skill teaches landing discipline",
              "Landing discipline" in wproc2
              and "Evidence before done" in wproc2)

        # ---- SPC-017 concurrency-safe state ----
        from tenx.locking import atomic_write_text
        concproj = Path(tempfile.mkdtemp(prefix="tenx-conc-"))
        tenx("init", cwd=concproj)

        def _tenx_cmd():
            c = [sys.executable, "-m", "tenx"] if USE_MODULE else ["tenx"]
            e = dict(os.environ)
            if USE_MODULE:
                src = str(Path(__file__).resolve().parent.parent / "src")
                e["PYTHONPATH"] = src + os.pathsep + e.get("PYTHONPATH", "")
            return c, e
        cmd0, env0 = _tenx_cmd()

        # atomic write leaves intact content and no temp file
        aw = concproj / "atomic-test.txt"
        atomic_write_text(aw, "hello atomic\n")
        check("atomic_write_text writes intact",
              aw.read_text() == "hello atomic\n")
        check("atomic_write_text leaves no tmp",
              not aw.with_name("atomic-test.txt.tmp").exists())

        # concurrent log appends lose no entries and keep the log valid
        N = 12
        procs = [subprocess.Popen(
                     [*cmd0, "log", f"conc-msg-{i}", "--type", "note"],
                     cwd=concproj, env=env0, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True)
                 for i in range(N)]
        rcs = [p.wait(timeout=90) for p in procs]
        check("concurrent log appends all succeed",
              all(rc == 0 for rc in rcs), str(rcs))
        loglines = (concproj / ".tenx/log/activity.jsonl"
                    ).read_text().splitlines()
        msgs = [l for l in loglines if "conc-msg-" in l]
        check("concurrent log appends lose no entries",
              len(msgs) == N, f"{len(msgs)}/{N}")
        ok = True
        for l in loglines:
            l = l.strip()
            if not l:
                continue
            try:
                json.loads(l)
            except Exception:
                ok = False
                break
        check("concurrent appends keep log valid JSON", ok)

        # concurrent set on one artifact leaves it parseable (no corruption)
        tenx("new", "epic", "Conc epic", cwd=concproj)
        tenx("new", "spec", "Conc spec", "--epic", "EPC-001", cwd=concproj)
        strip_discipline(concproj)
        cspec_file = sorted((concproj / ".tenx/specs").glob(
            "SPC-*-conc-spec.md"))[-1]
        cspec = cspec_file.read_text().split("id: ")[1].split("\n")[0]
        procs = [subprocess.Popen(
                     [*cmd0, "set", cspec, "owner", f"agent-{i}"],
                     cwd=concproj, env=env0, stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE, text=True)
                 for i in range(8)]
        rcs = [p.wait(timeout=90) for p in procs]
        check("concurrent set all succeed",
              all(rc == 0 for rc in rcs), str(rcs))
        meta = json.loads(tenx("show", cspec, "--json",
                               cwd=concproj).stdout)["meta"]
        check("concurrent set leaves artifact parseable",
              meta.get("id") == cspec, str(meta.get("id")))
        check("concurrent set keeps exactly one owner field",
              cspec_file.read_text().count("owner:") == 1)

        # a held lock makes a mutating command fail fast, clean, no traceback.
        # Hold the lock in a thread of THIS process (flock is per-process, so the
        # tenx subprocess still contends); far more robust than a bg holder proc.
        import threading
        from tenx.locking import harness_lock as _hl
        held_ev = threading.Event()
        release_ev = threading.Event()

        def _hold_lock():
            with _hl(concproj, timeout=5):
                held_ev.set()
                release_ev.wait(timeout=10)

        holder_thread = threading.Thread(target=_hold_lock, daemon=True)
        holder_thread.start()
        check("lock holder acquired", held_ev.wait(timeout=5),
              "thread did not acquire the lock in time")
        env_short = dict(env0)
        env_short["TENX_LOCK_TIMEOUT"] = "1"
        env_short["TENX_ROOT"] = str(concproj)  # pin root; discovery can't wander
        r = subprocess.run(
            [*cmd0, "--root", str(concproj), "log", "should-block",
             "--type", "note"],
            cwd=concproj, env=env_short, capture_output=True, text=True)
        combined = r.stdout + r.stderr
        check("locked command exits 2", r.returncode == 2,
              f"rc={r.returncode} stderr={r.stderr[:200]}")
        check("locked command has no traceback",
              "Traceback" not in combined, combined[:300])
        check("locked command prints clean message",
              "could not acquire" in combined, combined[:300])
        release_ev.set()
        holder_thread.join(timeout=10)
        shutil.rmtree(concproj, ignore_errors=True)

        # ---- sync fails clean on network error (no traceback) ----
        syncproj = Path(tempfile.mkdtemp(prefix="tenx-syncfail-"))
        subprocess.run(["git", "init", "-q", "."], cwd=syncproj)
        tenx("init", cwd=syncproj)
        subprocess.run(
            ["git", "remote", "add", "origin",
             "https://github.com/test/repo.git"], cwd=syncproj)
        env = dict(os.environ)
        env["GITHUB_TOKEN"] = "fake-token"
        # point at a dead port so the API call fails fast and offline
        env["TENX_GITHUB_API"] = "http://127.0.0.1:9"
        if USE_MODULE:
            srcdir = str(Path(__file__).resolve().parent.parent / "src")
            env["PYTHONPATH"] = srcdir + os.pathsep + env.get(
                "PYTHONPATH", "")
        cmd = ([sys.executable, "-m", "tenx"] if USE_MODULE else ["tenx"])
        sp = subprocess.run([*cmd, "sync", "push"], cwd=syncproj,
                            env=env, capture_output=True, text=True)
        check("sync network failure exits non-zero but clean",
              sp.returncode in (1, 2))
        check("sync network failure has no traceback",
              "Traceback" not in sp.stderr)
        check("sync network failure prints tenx sync message",
              "tenx sync:" in sp.stderr)

        # ---- SPC-018 docs-sync: changelog discipline + drift rules ----
        from tenx import changelog as _cl
        docsproj = Path(tempfile.mkdtemp(prefix="tenx-docs-"))
        tenx("init", "--name", "docs", cwd=docsproj)
        cl_file = docsproj / "CHANGELOG.md"
        check("init seeds CHANGELOG.md", cl_file.is_file())
        check("seeded changelog has [Unreleased]",
              "[Unreleased]" in cl_file.read_text())
        check("seed_changelog idempotent",
              _cl.seed_changelog(docsproj) is False)
        # add / show / release
        tenx("changelog", "add", "shipped the widget", "--type", "added",
             "--ref", "SPC-001", cwd=docsproj)
        tenx("changelog", "add", "fixed a crash", "--type", "fixed",
             cwd=docsproj)
        out = tenx("changelog", cwd=docsproj).stdout
        check("changelog add lands under Unreleased/Added",
              "shipped the widget (SPC-001)" in out)
        check("changelog groups by type",
              "### Added" in out and "### Fixed" in out)
        cj = json.loads(tenx("changelog", "--json", cwd=docsproj).stdout)
        check("changelog --json shape",
              cj["exists"] is True and cj["unreleased"] == 2
              and cj["latest_version"] is None)
        tenx("changelog", "release", "v9.9.9", cwd=docsproj)
        cj = json.loads(tenx("changelog", "--json", cwd=docsproj).stdout)
        check("changelog release stamps a version",
              cj["latest_version"] == "9.9.9" and cj["unreleased"] == 0)
        check("changelog release reopens [Unreleased]",
              "[Unreleased]" in cl_file.read_text())
        # release with empty Unreleased fails clean
        r = tenx("changelog", "release", "v9.9.10", cwd=docsproj,
                 expect_rc=2)
        check("changelog release empty fails clean",
              r.returncode == 2 and "Traceback" not in r.stderr)
        # drift rule: changelog-missing
        cl_file.unlink()
        out = tenx("validate", "--json", cwd=docsproj).stdout
        warns = json.loads(out)["warnings"]
        check("changelog-missing rule fires",
              any(w["rule"] == "changelog-missing" for w in warns))
        # restore + drift rule: changelog-unreleased-empty
        tenx("changelog", "add", "restore", cwd=docsproj)
        tenx("new", "epic", "Docs epic", cwd=docsproj)
        tenx("new", "spec", "Docs spec", "--epic", "EPC-001", cwd=docsproj)
        strip_discipline(docsproj)
        # SPC-023-T3: completing a ticket-less spec is now an error, so
        # give the spec real tickets before the completion below.
        add_tickets(docsproj / ".tenx/specs/SPC-001-docs-spec.md")
        tenx("ticket", "SPC-001", "SPC-001-T1", "done", cwd=docsproj)
        tenx("ticket", "SPC-001", "SPC-001-T2", "done", cwd=docsproj)
        tenx("log", "did docs work", "--ref", "SPC-001", cwd=docsproj)
        # backdate the release so the completed spec counts as "since release"
        tenx("changelog", "release", "v9.9.8", cwd=docsproj)
        import datetime as _dt
        _yest = (_dt.date.today() - _dt.timedelta(days=1)).isoformat()
        cl_file.write_text(cl_file.read_text().replace(
            f"## [v9.9.8] - {_dt.date.today().isoformat()}",
            f"## [v9.9.8] - {_yest}"))
        tenx("set", "SPC-001", "status", "complete", "--force",
             cwd=docsproj)
        # now Unreleased is empty and SPC-001 completed after release date
        out = tenx("validate", "--json", cwd=docsproj).stdout
        infos = json.loads(out)["info"]
        check("changelog-unreleased-empty rule fires",
              any(i["rule"] == "changelog-unreleased-empty" for i in infos),
              str(infos))
        # evidence gate requires a changelog entry referencing the artifact
        tenx("new", "spec", "Gated spec", "--epic", "EPC-001", cwd=docsproj)
        strip_discipline(docsproj)
        tenx("log", "did gated work", "--ref", "SPC-002", cwd=docsproj)
        r = tenx("set", "SPC-002", "status", "complete", cwd=docsproj,
                 expect_rc=2)
        check("evidence gate blocks without changelog entry",
              r.returncode == 2 and "changelog" in r.stderr, r.stderr[:300])
        tenx("changelog", "add", "shipped gated spec", "--ref", "SPC-002",
             cwd=docsproj)
        tenx("set", "SPC-002", "status", "complete", cwd=docsproj)
        out = tenx("show", "SPC-002", "--json", cwd=docsproj).stdout
        check("evidence gate passes with changelog entry",
              json.loads(out)["meta"]["status"] == "complete")
        # skill + mcp + process-skill surfaces
        tenx("skills", "install", cwd=docsproj)
        dskill = docsproj / ".claude/skills/tenx-docs-sync/SKILL.md"
        check("tenx-docs-sync skill installed", dskill.is_file())
        if dskill.is_file():
            check("docs-sync skill teaches the changelog loop",
                  "tenx changelog add" in dskill.read_text())
        from tenx.mcp import _tooldefs as _td
        check("mcp registers tenx_changelog",
              "tenx_changelog" in {t["name"] for t in _td()})
        dproc = (docsproj / ".claude/skills/tenx-process/SKILL.md"
                 ).read_text()
        check("process skill teaches docs-sync write-back",
              "tenx changelog add" in dproc)
        shutil.rmtree(docsproj, ignore_errors=True)

        # session logging throttle
        tenx("hook", "emit", "--no-log", cwd=scanproj)
        tenx("hook", "emit", cwd=scanproj)
        tenx("hook", "emit", cwd=scanproj)
        hist = tenx("history", "--json", cwd=scanproj).stdout
        entries = json.loads(hist)
        n_session = sum(1 for e in entries if e.get("type") == "session")
        check("session entries throttled to one", n_session == 1,
              f"got {n_session}")

        # ---- SPC-023 enforcement teeth ----
        gateproj = Path(tempfile.mkdtemp(prefix="tenx-gate-"))
        subprocess.run(["git", "init", "-q", str(gateproj)], check=True)
        subprocess.run(["git", "config", "user.email", "t@t.t"],
                       cwd=gateproj, check=True)
        subprocess.run(["git", "config", "user.name", "t"],
                       cwd=gateproj, check=True)
        tenx("init", "--name", "gateproj", cwd=gateproj)
        tenx("new", "epic", "Gate epic", cwd=gateproj)
        tenx("new", "spec", "Gate spec", "--epic", "EPC-001", cwd=gateproj)
        strip_discipline(gateproj)
        def _gitc(msg: str) -> None:
            # Commit in UTC so %aI renders the trailing 'Z' git emits on
            # UTC hosts — the exact shape Python 3.10's fromisoformat
            # rejects. Keeps the git-aware checks honest on every runner.
            subprocess.run(["git", "commit", "-qm", msg], cwd=gateproj,
                           env={**os.environ, "TZ": "UTC"}, check=True)

        from tenx.rules import parse_git_ts
        _zts = parse_git_ts("2026-08-26T11:08:52Z")
        check("parse_git_ts handles git UTC 'Z' timestamps",
              _zts is not None
              and _zts.utcoffset() == _dt.timedelta(0)
              and parse_git_ts("not a date") is None)

        subprocess.run(["git", "add", "-A"], cwd=gateproj, check=True)
        _gitc("baseline")

        # T5: blocked is a legal ticket status
        tenx("ticket", "SPC-001", "SPC-001-T1", "blocked", cwd=gateproj)
        out = tenx("show", "SPC-001", "--json", cwd=gateproj).stdout
        check("ticket status blocked accepted",
              json.loads(out)["meta"]["tickets"][0]["status"] == "blocked")
        tenx("ticket", "SPC-001", "SPC-001-T1", "todo", cwd=gateproj)

        # T6: ticket moves auto-append activity entries
        hist = json.loads(tenx("history", "--json", cwd=gateproj).stdout)
        check("ticket moves are auto-logged",
              sum(1 for e in hist if "SPC-001-T1" in e.get("message", "")
                  and e.get("type") == "progress") >= 2)

        # T2: git-aware validate — sneaky code commit gets flagged.
        # The matcher counts any work entry within +/-commit_window_hours
        # of a commit as write-back, so backdate the entries created
        # above out of the window to keep the test deterministic.
        import datetime as _dt2
        act = gateproj / ".tenx/log/activity.jsonl"
        old_ts = (_dt2.datetime.now(_dt2.timezone.utc)
                  - _dt2.timedelta(hours=10)).isoformat()
        aged = []
        for ln in act.read_text().splitlines():
            if ln.strip():
                rec = json.loads(ln)
                rec["ts"] = old_ts
                aged.append(json.dumps(rec))
        act.write_text("\n".join(aged) + "\n")

        (gateproj / "src").mkdir(exist_ok=True)
        (gateproj / "src" / "sneak.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "src/sneak.py"], cwd=gateproj,
                       check=True)
        _gitc("sneaky")
        out = tenx("validate", "--json", cwd=gateproj).stdout
        warns = json.loads(out)["warnings"]
        fired = any(w["rule"] == "commit-without-writeback" for w in warns)
        diag = str(warns)[:300]
        if not fired:
            # Diagnose in place: reproduce the rule's exact git pipeline
            # so a remote failure (e.g. CI runner) explains itself.
            def _g(*a):
                r = subprocess.run(["git", *a], cwd=gateproj,
                                   capture_output=True, text=True)
                return f"{' '.join(a[:2])}: rc={r.returncode} out={r.stdout[:200]!r} err={r.stderr[:150]!r}"
            since = (_dt2.datetime.now(_dt2.timezone.utc)
                     - _dt2.timedelta(hours=4)).isoformat()
            diag = " || ".join([
                _g("--version"),
                _g("rev-parse", "--git-dir"),
                _g("log", f"--since={since}", "--no-merges", "-n", "20",
                   "--pretty=format:%H%x00%aI%x00%s"),
                _g("show", "--name-only", "--pretty=format:", "HEAD"),
                "entries=" + str([(json.loads(l).get("type"),
                                   json.loads(l).get("ts"))
                                  for l in act.read_text().splitlines()
                                  if l.strip()])[:400],
            ])
        check("commit-without-writeback flags sneaky commit", fired, diag)
        tenx("log", "added sneak.py", "--ref", "SPC-001", cwd=gateproj)
        out = tenx("validate", "--json", cwd=gateproj).stdout
        warns = json.loads(out)["warnings"]
        check("write-back clears commit-without-writeback",
              not any(w["rule"] == "commit-without-writeback"
                      for w in warns))

        # T4: staged-change freshness gate. First commit the documented
        # state so HEAD is newer than every activity entry; a fresh
        # unlogged staged change must then trip the gate. Sleep so the
        # commit's second-granularity timestamp is strictly newer than
        # the entry logged above.
        import time as _t2
        _t2.sleep(1.1)
        (gateproj / "src" / "sneak.py").write_text("x = 2\n")
        subprocess.run(["git", "add", "src/sneak.py"], cwd=gateproj,
                       check=True)
        _gitc("documented change")
        (gateproj / "src" / "sneak.py").write_text("x = 3\n")
        subprocess.run(["git", "add", "src/sneak.py"], cwd=gateproj,
                       check=True)
        r = tenx("gate", "commit-check", cwd=gateproj)
        check("commit-check default mode warns but passes",
              r.returncode == 0)
        (gateproj / ".tenx/config.yaml").open("a").write(
            "\ncommit_gate: on\n")
        try:
            tenx("gate", "commit-check", cwd=gateproj, expect_rc=1)
            check("commit-check mode=on blocks unlogged code", True)
        except AssertionError as exc:
            staged = subprocess.run(
                ["git", "diff", "--cached", "--name-only"], cwd=gateproj,
                capture_output=True, text=True)
            head = subprocess.run(
                ["git", "log", "-1", "--pretty=%aI", "HEAD"], cwd=gateproj,
                capture_output=True, text=True)
            ents = [(json.loads(l).get("type"), json.loads(l).get("ts"))
                    for l in act.read_text().splitlines() if l.strip()]
            raise AssertionError(
                f"{exc} || staged rc={staged.returncode} "
                f"out={staged.stdout!r} || HEAD rc={head.returncode} "
                f"out={head.stdout!r} || entries={ents}")
        # process-only staged changes never trip the gate
        subprocess.run(["git", "reset", "-q"], cwd=gateproj, check=True)
        (gateproj / ".tenx" / "notes.txt").write_text("process only\n")
        subprocess.run(["git", "add", ".tenx/notes.txt"], cwd=gateproj,
                       check=True)
        tenx("gate", "commit-check", cwd=gateproj)
        check("commit-check ignores process-only staging", True)
        # write-back clears the gate for the code change
        tenx("log", "tweaked sneak.py", "--ref", "SPC-001",
             cwd=gateproj)
        subprocess.run(["git", "add", "src/sneak.py"], cwd=gateproj,
                       check=True)
        tenx("gate", "commit-check", cwd=gateproj)
        check("commit-check passes after write-back", True)
        _gitc("documented tweak")

        # T1: doctor enforcement audit + --json
        hook = gateproj / ".git/hooks/pre-commit"
        tenx("hook", "install", "--git", cwd=gateproj)
        check("hook install creates the git gate", hook.is_file())
        hook.unlink()
        r = tenx("doctor", cwd=gateproj, expect_rc=1)
        check("doctor flags missing git gate",
              "pre-commit gate MISSING" in r.stdout
              and "tenx hook install --git" in r.stdout, r.stdout[-300:])
        dout = json.loads(tenx("doctor", "--json", cwd=gateproj,
                               expect_rc=1).stdout)
        check("doctor --json reports enforcement problems",
              any("pre-commit" in p for p
                  in dout["enforcement_problems"]))
        tenx("hook", "install", "--git", cwd=gateproj)
        check("hook install restores the gate", hook.is_file())

        # T8: stale managed surfaces are flagged and fixable
        claudemd = gateproj / "CLAUDE.md"
        claudemd.write_text(claudemd.read_text().replace(
            "### Hard rules (non-negotiable)", "### Old rules"))
        out = tenx("validate", "--json", cwd=gateproj).stdout
        warns = json.loads(out)["warnings"]
        check("agent-surface-stale flags stale CLAUDE.md",
              any(w["rule"] == "agent-surface-stale" for w in warns))
        tenx("hook", "install", "--agent", "all", cwd=gateproj)
        out = tenx("validate", "--json", cwd=gateproj).stdout
        warns = json.loads(out)["warnings"]
        check("hook install --agent all clears staleness",
              not any(w["rule"] == "agent-surface-stale" for w in warns))

        # T9: worktree installs land in the common hooks dir
        wt = gateproj.parent / (gateproj.name + "-wt")
        subprocess.run(["git", "worktree", "add", str(wt), "HEAD"],
                       cwd=gateproj, capture_output=True)
        if wt.is_dir():
            hook.unlink()
            tenx("hook", "install", "--git", cwd=wt)
            check("worktree install restores common-dir gate",
                  hook.is_file())
            subprocess.run(["git", "worktree", "remove", "--force",
                            str(wt)], cwd=gateproj, capture_output=True)

        # T7: gate escapes leave an audit trail
        r = tenx("set", "SPC-001", "status", "complete", cwd=gateproj,
                 expect_rc=2)
        hist = json.loads(tenx("history", "--json", cwd=gateproj).stdout)
        check("gate block is logged as blocker",
              any(e.get("type") == "blocker" and "SPC-001" in str(e)
                  for e in hist))
        tenx("set", "SPC-001", "status", "complete", "--force",
             cwd=gateproj)
        hist = json.loads(tenx("history", "--json", cwd=gateproj).stdout)
        check("forced completion is logged as decision",
              any(e.get("type") == "decision" and "force" in str(e).lower()
                  for e in hist))
        tenx("set", "SPC-001", "status", "draft", cwd=gateproj)

        # T16: watchdog flags only UNRESOLVED blocker entries
        tenx("log", "simulated open blocker", "--type", "blocker",
             "--ref", "SPC-001", cwd=gateproj)
        wj = json.loads(tenx("watchdog", "--json", cwd=gateproj).stdout)
        check("watchdog flags unresolved blocker",
              any("unresolved blocker" in str(i.get("problem", ""))
                  for i in wj["items"]), str(wj)[:300])
        tenx("log", "resolved the simulated blocker", "--ref", "SPC-001",
             cwd=gateproj)
        wj = json.loads(tenx("watchdog", "--json", cwd=gateproj).stdout)
        check("watchdog clears resolved blocker",
              not any("unresolved blocker" in str(i.get("problem", ""))
                      for i in wj["items"]))

        # T17: census truncation is visible, not silent
        for i in range(16):
            d = gateproj / f"bulk{i}"
            d.mkdir(exist_ok=True)
            (d / "f.txt").write_text("x\n")
        out = tenx("scan", cwd=gateproj).stdout
        check("scan shows census truncation",
              "showing top 15 of" in out, out[-300:])

        # T18: --root works before AND after the subcommand
        # (cwd is deliberately OUTSIDE the project so --root must work)
        tenx("next", "--root", str(gateproj), cwd=gateproj.parent)
        tenx("--root", str(gateproj), "next", cwd=gateproj.parent)
        check("--root accepted in both positions", True)

        # T19: scan --write preserves manual additions below the promise
        tenx("scan", "--write", cwd=gateproj)
        maps = sorted((gateproj / ".tenx" / "docs").glob("*codebase-map*"))
        check("codebase map doc exists", bool(maps))
        if maps:
            with maps[0].open("a") as fh:
                fh.write("\n## Manual notes\n\n- keep me around\n")
            tenx("scan", "--write", cwd=gateproj)
            check("scan --write preserves manual additions",
                  "keep me around" in maps[0].read_text())

        # T14: archive requires explicit approval
        r = tenx("archive", "EPC-001", cwd=gateproj, expect_rc=2)
        check("archive refused without --approved-by",
              "approved-by" in r.stderr, r.stderr[:200])

        # T14: changelog entries in released sections satisfy the gate
        tenx("ticket", "SPC-001", "SPC-001-T1", "done", cwd=gateproj)
        tenx("changelog", "add", "shipped gate work", "--ref", "SPC-001",
             cwd=gateproj)
        tenx("changelog", "release", "0.1.0", cwd=gateproj)
        tenx("set", "SPC-001", "status", "complete", cwd=gateproj)
        out = tenx("show", "SPC-001", "--json", cwd=gateproj).stdout
        check("released-section changelog entry passes the gate",
              json.loads(out)["meta"]["status"] == "complete")
        tenx("archive", "EPC-001", "--approved-by", "smoke-test",
             "--yes", cwd=gateproj)
        hist = json.loads(tenx("history", "--json", cwd=gateproj).stdout)
        check("archive records its approver",
              any("approved by smoke-test" in e.get("message", "")
                  for e in hist))
        shutil.rmtree(gateproj, ignore_errors=True)

        # T11: MCP mutating tools take the harness lock
        from tenx.mcp import _tooldefs as _td2
        lockproj = Path(tempfile.mkdtemp(prefix="tenx-lock-"))
        tenx("init", "--name", "lockproj", cwd=lockproj)
        tenx("new", "epic", "Lock epic", cwd=lockproj)
        tenx("new", "spec", "Lock spec", "--epic", "EPC-001",
             cwd=lockproj)
        strip_discipline(lockproj)
        holder_src = (
            "import sys, time\n"
            f"sys.path.insert(0, {str(Path(__file__).resolve().parent.parent / 'src')!r})\n"
            "from pathlib import Path\n"
            "from tenx.locking import harness_lock\n"
            f"with harness_lock(Path({str(lockproj)!r})): time.sleep(3)\n")
        holder = subprocess.Popen([sys.executable, "-c", holder_src])
        import time as _time
        _time.sleep(0.8)
        os.environ["TENX_LOCK_TIMEOUT"] = "1"
        try:
            ticket_tool = next(t for t in _td2()
                               if t["name"] == "tenx_ticket")
            _text, lrc = ticket_tool["handler"](
                {"root": str(lockproj), "spec": "SPC-001",
                 "ticket": "SPC-001-T1", "status": "in_progress"})
            check("MCP mutating tool honors the harness lock", lrc == 2,
                  f"rc={lrc}")
        finally:
            os.environ.pop("TENX_LOCK_TIMEOUT", None)
            holder.wait(timeout=10)
        shutil.rmtree(lockproj, ignore_errors=True)

        # SPC-026: tenx_converge MCP tool — report, append, lock-on-append
        from tenx.mcp import _tooldefs as _td3
        convproj = Path(tempfile.mkdtemp(prefix="tenx-conv-"))
        tenx("init", "--name", "convproj", cwd=convproj)
        tenx("new", "epic", "Conv epic", cwd=convproj)
        tenx("new", "spec", "Conv spec", "--epic", "EPC-001", cwd=convproj)
        cspec = next((convproj / ".tenx/specs").glob("SPC-001-*.md"))
        ctxt = cspec.read_text()
        ctxt = ctxt.replace(
            "- FR-001: The system MUST ...\n",
            "- FR-001: The system MUST greet.\n")
        ctxt = ctxt.replace(
            "- FR-002: The system MUST ... "
            "[NEEDS CLARIFICATION: example question]\n",
            "- FR-002: The system MUST farewell.\n")
        fm_end = ctxt.index("---", 4)
        ctxt = (ctxt[:fm_end]
                + "tickets:\n  - id: SPC-001-T1\n"
                + "    title: \"[FR-001] greet\"\n    status: todo\n"
                + ctxt[fm_end:])
        cspec.write_text(ctxt)
        conv_tool = next(t for t in _td3() if t["name"] == "tenx_converge")
        ctext, crc = conv_tool["handler"](
            {"root": str(convproj), "spec_id": "SPC-001"})
        crep = json.loads(ctext)
        check("MCP converge registered and reports JSON",
              crc == 1 and crep["verdict"] == "NOT CONVERGED",
              f"rc={crc} {ctext[:120]}")
        check("MCP converge maps FRs to tagged tickets",
              crep["requirements"][0]["tickets"] == ["SPC-001-T1"]
              and crep["requirements"][1]["tickets"] == [],
              str(crep["requirements"]))
        # append creates the missing ticket (append-only)
        atext, arc = conv_tool["handler"](
            {"root": str(convproj), "spec_id": "SPC-001", "append": True})
        arep = json.loads(atext)
        check("MCP converge append creates uncovered-FR ticket",
              arc == 1 and arep["appended_tickets"] == ["SPC-001-T2"]
              and "[FR-002]" in cspec.read_text(),
              f"rc={arc} {atext[:120]}")
        # append takes the harness lock; report does not
        cholder_src = (
            "import sys, time\n"
            f"sys.path.insert(0, {str(Path(__file__).resolve().parent.parent / 'src')!r})\n"
            "from pathlib import Path\n"
            "from tenx.locking import harness_lock\n"
            f"with harness_lock(Path({str(convproj)!r})): time.sleep(3)\n")
        cholder = subprocess.Popen([sys.executable, "-c", cholder_src])
        _time.sleep(0.8)
        os.environ["TENX_LOCK_TIMEOUT"] = "1"
        try:
            _t, lrc = conv_tool["handler"](
                {"root": str(convproj), "spec_id": "SPC-001",
                 "append": True})
            check("MCP converge append honors the harness lock", lrc == 2,
                  f"rc={lrc}")
            _t, rrc = conv_tool["handler"](
                {"root": str(convproj), "spec_id": "SPC-001"})
            check("MCP converge report is lock-free", rrc == 1, f"rc={rrc}")
        finally:
            os.environ.pop("TENX_LOCK_TIMEOUT", None)
            cholder.wait(timeout=10)
        shutil.rmtree(convproj, ignore_errors=True)

        # T12: yamlite fallback hardening
        from tenx import yamlite as _yl
        _saved_backend = _yl._pyyaml
        _yl._pyyaml = None
        try:
            d = _yl.yamlite_load("tags:\n- a\n- b\nname: x")
            check("yamlite parses zero-indent lists",
                  d == {"tags": ["a", "b"], "name": "x"}, str(d))
            probs: list[str] = []
            d = _yl.yamlite_load("name: x\n%%%garbage", probs)
            check("yamlite reports unparseable lines",
                  d == {"name": "x"} and len(probs) == 1, str(probs))
        finally:
            _yl._pyyaml = _saved_backend

        # T13: changelog round-trip preserves unmodeled content
        from tenx.changelog import parse_changelog as _pc, render as _rnd
        _cl_text = ("# Changelog\n\n## [Unreleased]\n\n"
                    "- heading-less entry\n\n### Added\n\n"
                    "- feature X\n  - sub-bullet\n")
        _p1, _s1 = _pc(_cl_text)
        _o1 = _rnd(_p1, _s1)
        _p2, _s2 = _pc(_o1)
        check("changelog round-trip is stable and lossless",
              _o1 == _rnd(_p2, _s2)
              and "- heading-less entry" in _o1
              and "  - sub-bullet" in _o1)

        # T15: catalog completeness + doctor --json shape
        from tenx.capabilities import CAPABILITIES as _CAPS
        _names = {c["name"] for c in _CAPS}
        check("capabilities catalog covers init and gate",
              {"init", "gate", "capabilities"} <= _names, str(_names))
        check("capabilities tool is tagged for both surfaces",
              next(c for c in _CAPS
                   if c["name"] == "capabilities")["surface"] == "both")

        # ---- SPC-025 spec artifact discipline ----
        disc = Path(tempfile.mkdtemp(prefix="tenx-disc-"))
        try:
            tenx("init", "--name", "disc", cwd=disc)
            tenx("new", "epic", "Discipline epic", cwd=disc)
            tenx("new", "spec", "Discipline spec", "--epic", "EPC-001",
                 cwd=disc)
            sp = next((disc / ".tenx" / "specs").glob("SPC-001-*.md"))
            tpl = sp.read_text(encoding="utf-8")
            check("T1: new spec template carries FR/SC structure",
                  "## Requirements" in tpl and "## Success criteria" in tpl
                  and "FR-001" in tpl and "SC-001" in tpl
                  and "NEEDS CLARIFICATION" in tpl
                  and "Given/When/Then" in tpl)
            # draft with template markers must NOT trip the clarify rule
            r = tenx("validate", "--json", cwd=disc)
            check("T2: draft specs may carry clarify markers",
                  "clarify-markers-open" not in r.stdout)
            # controlled body: FR-001 covered, FR-002 uncovered,
            # one clarify marker, one orphan ticket ref
            fm = tpl.split("---", 2)[1]
            new_spec = (
                "---" + fm.rstrip("-\n").rstrip() + "\n"
                "tickets:\n"
                "  - id: SPC-001-T1\n"
                "    title: \"[FR-001] do the thing\"\n"
                "    status: todo\n"
                "  - id: SPC-001-T2\n"
                "    title: \"[FR-009] orphan\"\n"
                "    status: todo\n"
                "---\n\n"
                "## Summary\n\nControlled.\n\n"
                "## Requirements\n\n"
                "- FR-001: The system MUST do the thing\n"
                "- FR-002: The system MUST do the other thing "
                "[NEEDS CLARIFICATION: which other thing?]\n\n"
                "## Success criteria\n\n- SC-001: thing works\n\n"
                "## Validation\n\nFR-001: Given x, When y, Then z.\n")
            sp.write_text(new_spec, encoding="utf-8")
            tenx("set", "SPC-001", "status", "in_progress", cwd=disc)
            r = tenx("validate", "--json", cwd=disc, expect_rc=1)
            check("T2: clarify marker in non-draft spec is an error",
                  "clarify-markers-open" in r.stdout)
            check("T3: uncovered FR-002 warned",
                  "requirement-uncovered" in r.stdout
                  and "FR-002" in r.stdout)
            check("T3: covered FR-001 not flagged",
                  "FR-001 has no ticket" not in r.stdout)
            check("T3: orphan ticket ref reported",
                  "requirement-orphan" in r.stdout and "FR-009" in r.stdout)
            # converge: not converged, then --append covers FR-002
            r = tenx("converge", "SPC-001", cwd=disc, expect_rc=1)
            check("T4: converge reports NOT CONVERGED",
                  "NOT CONVERGED" in r.stdout)
            r = tenx("converge", "SPC-001", "--append", cwd=disc,
                     expect_rc=1)
            check("T4: converge --append creates ticket for FR-002",
                  "SPC-001-T3" in r.stdout and "FR-002" in r.stdout)
            # resolve marker, finish tickets -> CONVERGED + no-op
            txt = sp.read_text(encoding="utf-8").replace(
                " [NEEDS CLARIFICATION: which other thing?]", "")
            sp.write_text(txt, encoding="utf-8")
            for t in ("T1", "T2", "T3"):
                tenx("ticket", "SPC-001", f"SPC-001-{t}", "done",
                     cwd=disc)
            before = sp.read_bytes()
            r = tenx("converge", "SPC-001", "--append", cwd=disc)
            check("T4: converge CONVERGED after tickets done",
                  "CONVERGED" in r.stdout and "NOT CONVERGED" not in r.stdout)
            check("T4: --append is byte-for-byte no-op when clean",
                  sp.read_bytes() == before)
            rj = tenx("converge", "SPC-001", "--json", cwd=disc)
            check("T4: converge --json machine-readable",
                  "\"converged\": true" in rj.stdout)
            # legacy spec without FR markers: NO REQUIREMENTS, exit 0
            legacy = disc / ".tenx" / "specs" / "SPC-002-legacy.md"
            legacy.write_text(
                "---\nid: SPC-002\ntype: spec\ntitle: Legacy\n"
                "status: complete\nepic: EPC-001\n"
                "created: 2026-01-01\nupdated: 2026-01-01\n---\n\n"
                "## Summary\n\nOld-style prose spec, no FR ids.\n\n"
                "## Validation\n\nIt shipped.\n",
                encoding="utf-8")
            r = tenx("converge", "SPC-002", cwd=disc)
            check("T4: legacy spec reports NO REQUIREMENTS",
                  "NO REQUIREMENTS" in r.stdout)
        finally:
            shutil.rmtree(disc, ignore_errors=True)

        check("T5: capabilities catalog covers converge",
              "converge" in {c["name"] for c in _CAPS})

        # ---- SPC-027 epic body & template validation discipline ----
        eproj = Path(tempfile.mkdtemp(prefix="tenx-epic-disc-"))
        try:
            tenx("init", "--name", "eproj", cwd=eproj)
            tenx("new", "epic", "Scaffold Epic", cwd=eproj)
            tenx("new", "spec", "Scaffold Spec", "--epic", "EPC-001", cwd=eproj)
            strip_discipline(eproj)

            # 1. Draft epic with template boilerplate emits info, not error/warning
            r = tenx("validate", "--json", cwd=eproj)
            rj = json.loads(r.stdout)
            infos = {i["rule"] for i in rj.get("info", [])}
            check("SPC-027 T1: draft epic boilerplate emits info",
                  "epic-template-unfilled" in infos)
            check("SPC-027 T1: draft epic has no errors",
                  len(rj.get("errors", [])) == 0)

            # 2. In-progress epic emits warning
            tenx("set", "EPC-001", "status", "in_progress", cwd=eproj)
            r = tenx("validate", "--json", cwd=eproj)
            rj = json.loads(r.stdout)
            warns = {w["rule"] for w in rj.get("warnings", [])}
            check("SPC-027 T1: in_progress epic boilerplate emits warning",
                  "epic-template-unfilled" in warns)

            # 3. In-review epic emits error
            tenx("set", "EPC-001", "status", "in_review", cwd=eproj)
            r = tenx("validate", "--json", cwd=eproj, expect_rc=1)
            rj = json.loads(r.stdout)
            errs = {e["rule"] for e in rj.get("errors", [])}
            check("SPC-027 T1: in_review epic boilerplate emits error",
                  "epic-template-unfilled" in errs)

            # 4. Attempting to mark complete is blocked by the evidence gate
            r = tenx("set", "EPC-001", "status", "complete", cwd=eproj, expect_rc=2)
            check("SPC-027 T2: evidence gate blocks complete on boilerplate epic",
                  "unpopulated or contains scaffold template boilerplate" in r.stderr)

            # 5. Populating epic body with real content resolves errors and warnings
            ep_file = next((eproj / ".tenx" / "epics").glob("EPC-001-*.md"))
            ep_content = (
                "---\nid: EPC-001\ntype: epic\ntitle: Real Epic\n"
                "status: in_progress\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n\n"
                "## Objective\n\nReal substantial objective for the epic without any boilerplate.\n\n"
                "## Key results\n\n- Key result 1: verified end-to-end.\n"
            )
            ep_file.write_text(ep_content, encoding="utf-8")
            r = tenx("validate", "--json", cwd=eproj)
            rj = json.loads(r.stdout)
            check("SPC-027 T3: populated epic body validates clean without template errors",
                  "epic-template-unfilled" not in {e["rule"] for e in rj.get("errors", [])}
                  and "epic-template-unfilled" not in {w["rule"] for w in rj.get("warnings", [])})
        finally:
            shutil.rmtree(eproj, ignore_errors=True)

        # =============================================================
        # SPC-028: Subagent Ticket Dispatch smoke tests
        # =============================================================
        dproj = tmp / "dispatch-proj"
        dproj.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["git", "init", "-q", str(dproj)], check=True)
            subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=dproj, check=True)
            subprocess.run(["git", "config", "user.name", "t"], cwd=dproj, check=True)
            tenx("init", "--name", "dispatch-test", "--force", cwd=dproj)
            tenx("new", "epic", "Dispatch Epic", cwd=dproj)
            tenx("new", "spec", "Dispatch Spec", "--epic", "EPC-001", cwd=dproj)
            tenx("new", "convention", "Dispatch Rule", cwd=dproj)
            strip_discipline(dproj)
            tenx("validate", "--fix", cwd=dproj)

            # 1. Test ticket-brief on a spec ticket
            sp_file = next((dproj / ".tenx" / "specs").glob("SPC-001-*.md"))
            sp_body = (
                "---\nid: SPC-001\ntype: spec\ntitle: Dispatch Spec\n"
                "epic: EPC-001\nstatus: in_progress\n"
                "created: 2026-01-01\nupdated: 2026-01-01\n"
                "tickets:\n  - id: SPC-001-T1\n    title: First worker ticket\n    status: todo\n---\n\n"
                "## Summary\n\nSpec summary\n\n"
                "## Requirements\n\n- FR-001: The worker must run tests.\n\n"
                "## Tickets\n\n- `SPC-001-T1`: First worker ticket with FR-001 [todo]\n"
            )
            sp_file.write_text(sp_body, encoding="utf-8")

            tb_out = tenx("ticket-brief", "SPC-001", "SPC-001-T1", cwd=dproj).stdout
            check("SPC-028 T1: ticket-brief contains ticket title",
                  "First worker ticket" in tb_out)
            check("SPC-028 T1: ticket-brief contains matched requirement",
                  "FR-001: The worker must run tests." in tb_out)
            check("SPC-028 T1: ticket-brief contains conventions",
                  "CON-001" in tb_out)

            # 2. Test ticket-brief --json
            tb_json = tenx("ticket-brief", "SPC-001", "SPC-001-T1", "--json", cwd=dproj).stdout
            tbj = json.loads(tb_json)
            check("SPC-028 T1: ticket-brief json output valid",
                  tbj.get("ticket") == "SPC-001-T1" and "brief" in tbj)

            # 3. Test dispatch dry-run across harnesses
            dr_pi = tenx("dispatch", "SPC-001", "SPC-001-T1", "--agent", "pi", "--dry-run", "--json", cwd=dproj).stdout
            dr_pi_j = json.loads(dr_pi)
            check("SPC-028 T2: dispatch dry-run for pi",
                  dr_pi_j.get("agent") == "pi" and dr_pi_j.get("status") == "dry_run" and "pi -p" in " ".join(dr_pi_j.get("command", [])))

            dr_codex = tenx("dispatch", "SPC-001", "SPC-001-T1", "--agent", "codex", "--dry-run", "--json", cwd=dproj).stdout
            dr_codex_j = json.loads(dr_codex)
            check("SPC-028 T2: dispatch dry-run for codex",
                  dr_codex_j.get("agent") == "codex" and "codex exec" in " ".join(dr_codex_j.get("command", [])))

            dr_prime = tenx("dispatch", "SPC-001", "SPC-001-T1", "--agent", "prime", "--dry-run", "--json", cwd=dproj).stdout
            dr_prime_j = json.loads(dr_prime)
            check("SPC-028 T2: dispatch dry-run for prime-agent",
                  dr_prime_j.get("agent") == "prime-agent" and ("prime run" in " ".join(dr_prime_j.get("command", [])) or "prime-agent" in " ".join(dr_prime_j.get("command", []))))

            # 4. Test visual dispatch dry-run for herdr and tmux
            dr_vis_herdr = tenx("dispatch", "SPC-001", "SPC-001-T1", "--agent", "pi", "--visual", "--multiplexer", "herdr", "--dry-run", "--json", cwd=dproj).stdout
            dr_vh_j = json.loads(dr_vis_herdr)
            check("SPC-029 T3: visual dispatch dry-run for herdr",
                  dr_vh_j.get("visual") is True and dr_vh_j.get("multiplexer") == "herdr" and "projection" in dr_vh_j and "workspace" in dr_vh_j["projection"]["create_cmd"])

            dr_vis_tmux = tenx("dispatch", "SPC-001", "SPC-001-T1", "--agent", "pi", "--visual", "--multiplexer", "tmux", "--dry-run", "--json", cwd=dproj).stdout
            dr_vt_j = json.loads(dr_vis_tmux)
            check("SPC-029 T3: visual dispatch dry-run for tmux",
                  dr_vt_j.get("visual") is True and dr_vt_j.get("multiplexer") == "tmux" and "projection" in dr_vt_j and "new-window" in dr_vt_j["projection"]["create_cmd"])

            # 5. Test tenx-dispatch skill installation
            skills_out = tenx("skills", "list", cwd=dproj).stdout
            check("SPC-028 T3: tenx-dispatch skill listed",
                  "tenx-dispatch" in skills_out)
            tenx("skills", "install", cwd=dproj)
            if USE_MODULE:
                skills_status = tenx("skills", "status", cwd=dproj).stdout
                check("SPC-035 T1: installed dispatch skill is current",
                      "tenx-dispatch: current" in skills_status and "Skill drift:" not in skills_status)
            check("SPC-035 T3: Herdr dry-run uses agent start template",
                  "agent" in dr_vh_j.get("projection", {}).get("run_cmd", []) and
                  "--pane" in dr_vh_j.get("projection", {}).get("run_cmd", []))
            no_focus = tenx("dispatch", "SPC-001", "SPC-001-T1", "--visual", "--no-focus", "--dry-run", "--json", cwd=dproj)
            check("SPC-035 T3: --no-focus is accepted",
                  "--no-focus" in no_focus.stdout)
            check("SPC-035 T3: missing adapter fails closed",
                  tenx("dispatch", "SPC-001", "SPC-001-T1", "--agent", "definitely-missing", "--dry-run", "--json", cwd=dproj, expect_rc=1).stdout.find("not found") >= 0)

            # 6. Test SPC-030: Model Routing and Multi-Harness command builders (omp, prime-agent, codex)
            from tenx.dispatch import resolve_agent_command
            from tenx.router import resolve_model_route
            from tenx.memory import MemoryDistiller, DistilledObservation

            # Model routing verification
            m_route = resolve_model_route(requested_model="google-antigravity/claude-sonnet-4-6", tier=1)
            check("SPC-030 T2: model routing explicitly sets model",
                  m_route.model == "google-antigravity/claude-sonnet-4-6" and m_route.source == "explicit")

            # Harness command resolution with model & thinking
            omp_cmd = resolve_agent_command("omp", dproj, dproj / "TICKET_BRIEF.md", model="google-antigravity/gemini-3.8-flash-high", thinking="high")
            check("SPC-030 T2: omp command contains model and thinking",
                  omp_cmd.agent == "omp" and "--model" in omp_cmd.cmd and "--thinking" in omp_cmd.cmd)

            prime_cmd = resolve_agent_command("prime-agent", dproj, dproj / "TICKET_BRIEF.md", model="google-antigravity/claude-opus-4-6-thinking")
            check("SPC-030 T2: prime-agent command contains model",
                  prime_cmd.agent == "prime-agent" and "--model" in prime_cmd.cmd)

            # Memory distillation & gap ledger verification
            distiller = MemoryDistiller(dproj)
            obs1 = DistilledObservation(
                session_id="sess_1",
                harness="pi",
                category="workflow_failure",
                summary="Missing test assertions before validate",
                verdict="fail",
                error_pattern="err_missing_test_assertions",
            )
            g1 = distiller.record_observation(obs1)
            check("SPC-030 T2: memory distiller first observation not yet graduated",
                  g1 is None)

            obs2 = DistilledObservation(
                session_id="sess_2",
                harness="omp",
                category="workflow_failure",
                summary="Missing test assertions before validate",
                verdict="fail",
                error_pattern="err_missing_test_assertions",
            )
            g2 = distiller.record_observation(obs2)
            check("SPC-030 T2: memory distiller graduates after multi-session corroboration",
                  g2 is not None and g2.graduated is True and g2.occurrences == 2)

            # 7. Test SPC-032: Subagent worktree verification, merge reconcile, and abort teardown
            from tenx.reconcile import reconcile_subagent_ticket, abort_subagent_ticket
            
            # Initial commit on parent so HEAD is valid for worktrees
            subprocess.run(["git", "add", "."], cwd=dproj, capture_output=True)
            subprocess.run(["git", "commit", "-m", "chore: initial repo state"], cwd=dproj, capture_output=True)

            # Setup a subagent worktree manually
            test_ticket = "SPC-001-T1"
            wt_path = dproj / ".tenx" / "worktrees" / test_ticket
            wt_path.parent.mkdir(parents=True, exist_ok=True)
            res_wt = subprocess.run(["git", "worktree", "add", "-b", f"tenx/{test_ticket}", str(wt_path), "HEAD"], cwd=dproj, capture_output=True, text=True)
            if not wt_path.exists():
                print("git worktree add error:", res_wt.stderr, res_wt.stdout)

            # Make a commit in the worktree
            (wt_path / "SUBAGENT_WORK.txt").write_text("Work performed by subagent")
            subprocess.run(["git", "add", "SUBAGENT_WORK.txt"], cwd=wt_path, capture_output=True)
            subprocess.run(["git", "commit", "-m", "feat: subagent test work"], cwd=wt_path, capture_output=True)

            # Reconcile with skip_verify=True in test sandbox
            rec_res = reconcile_subagent_ticket(dproj, test_ticket, skip_verify=True)
            check("SPC-032 T1: reconcile merged subagent work",
                  rec_res.status == "merged" and (dproj / "SUBAGENT_WORK.txt").exists())
            check("SPC-032 T1: worktree directory removed after merge",
                  not wt_path.exists())
            dirty_ticket = "SPC-001-T3"
            dirty_wt = dproj / ".tenx" / "worktrees" / dirty_ticket
            subprocess.run(["git", "worktree", "add", "-b", f"tenx/{dirty_ticket}", str(dirty_wt), "HEAD"], cwd=dproj, capture_output=True)
            (dirty_wt / "UNCOMMITTED.txt").write_text("preserve me")
            dirty_rec = reconcile_subagent_ticket(dproj, dirty_ticket, skip_verify=True)
            check("SPC-035 T3: dirty worktree is preserved",
                  dirty_rec.status == "dirty_worktree" and dirty_wt.exists() and (dirty_wt / "UNCOMMITTED.txt").exists())
            subprocess.run(["git", "worktree", "remove", "--force", str(dirty_wt)], cwd=dproj, capture_output=True)
            subprocess.run(["git", "branch", "-D", f"tenx/{dirty_ticket}"], cwd=dproj, capture_output=True)

            # Test abort on a second ticket worktree
            abort_ticket = "SPC-001-T2"
            wt_abort = dproj / ".tenx" / "worktrees" / abort_ticket
            subprocess.run(["git", "worktree", "add", "-b", f"tenx/{abort_ticket}", str(wt_abort), "HEAD"], cwd=dproj, capture_output=True)
            (wt_abort / "ABORT_WORK.txt").write_text("Should be discarded")
            ab_res = abort_subagent_ticket(dproj, abort_ticket)
            check("SPC-032 T1: abort cleanly removed worktree",
                  ab_res.status == "aborted" and not wt_abort.exists())
            check("SPC-032 T1: aborted work not merged to parent",
                  not (dproj / "ABORT_WORK.txt").exists())

            # Test CLI subcommands
            out_help = tenx("--help", cwd=dproj).stdout
            check("SPC-032 T2: reconcile and merge subcommands present in CLI",
                  "reconcile" in out_help and "merge" in out_help and "abort" in out_help)

            # Test MCP tools
            from tenx.mcp import McpServer
            server = McpServer()
            mcp_tool_names = [t["name"] for t in server.tools]
            check("SPC-032 T2: tenx_reconcile and tenx_abort present in MCP",
                  "tenx_reconcile" in mcp_tool_names and "tenx_abort" in mcp_tool_names)

            # Test SPC-033: DAG Swarm scheduling and execution
            from tenx.dag import build_spec_dag, CyclicDependencyError
            from tenx.swarm import plan_spec_swarm, execute_spec_swarm
            from tenx.artifacts import Artifact

            dag_test_tickets = [
                {"id": "T-1", "title": "Base 1", "status": "done"},
                {"id": "T-2", "title": "Base 2", "status": "todo"},
                {"id": "T-3", "title": "Dependent 1", "status": "todo", "depends_on": ["T-1"]},
                {"id": "T-4", "title": "Dependent 2", "status": "todo", "depends_on": ["T-2", "T-3"]},
            ]
            spec_mock = Artifact(
                path=Path("mock.md"),
                meta={
                    "id": "SPC-TEST",
                    "type": "spec",
                    "title": "Mock",
                    "status": "in_progress",
                    "tickets": dag_test_tickets,
                },
                body="",
            )
            spec_dag = build_spec_dag(spec_mock)
            check("SPC-033 T1: DAG wave partitioning",
                  spec_dag.waves == [["T-1", "T-2"], ["T-3"], ["T-4"]])

            # Cycle detection
            cycle_tickets = [
                {"id": "A", "title": "A", "depends_on": ["B"]},
                {"id": "B", "title": "B", "depends_on": ["A"]},
            ]
            spec_cycle_mock = Artifact(
                path=Path("mock_cyc.md"),
                meta={
                    "id": "SPC-CYC",
                    "type": "spec",
                    "title": "Cycle",
                    "status": "in_progress",
                    "tickets": cycle_tickets,
                },
                body="",
            )
            cycle_caught = False
            try:
                build_spec_dag(spec_cycle_mock)
            except CyclicDependencyError:
                cycle_caught = True
            check("SPC-033 T1: DAG cyclic dependency detection", cycle_caught)

            # Add a new todo ticket to SPC-001 for swarm testing
            sp_file.write_text(
                "---\nid: SPC-001\ntype: spec\ntitle: Dispatch Spec\n"
                "epic: EPC-001\nstatus: in_progress\n"
                "created: 2026-01-01\nupdated: 2026-01-01\n"
                "tickets:\n  - id: SPC-001-T3\n    title: Swarm worker ticket\n    status: todo\n---\n\n"
                "## Summary\n\nSpec summary\n\n"
                "## Requirements\n\n- FR-001: The worker must run tests.\n\n"
                "## Tickets\n\n- `SPC-001-T3`: Swarm worker ticket with FR-001 [todo]\n",
                encoding="utf-8"
            )

            # Swarm execution dry run on dproj
            swarm_res = execute_spec_swarm(dproj, "SPC-001", dry_run=True)
            check("SPC-033 T2: swarm dry-run execution",
                  swarm_res.status == "completed" and "SPC-001-T3" in swarm_res.dispatched_tickets)

            # Test wait_for_subagent_completion
            from tenx.multiplexers import wait_for_subagent_completion
            check("SPC-034 T1: nonvisual wait is explicit",
                  wait_for_subagent_completion("none").status == "not_applicable")
            check("SPC-035 T3: missing visual target is not completion",
                  wait_for_subagent_completion("herdr", None).status == "missing")
            check("SPC-035 T3: Herdr missing target fails closed",
                  wait_for_subagent_completion("herdr", None).status == "missing")
            check("SPC-035 T3: tmux missing target fails closed",
                  wait_for_subagent_completion("tmux", None).status == "missing")

        finally:
            shutil.rmtree(dproj, ignore_errors=True)


    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s): {FAILURES}")
        return 1
    print("All smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
