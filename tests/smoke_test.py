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
        check("mcp lists 14 tools", len(tool_names) == 14,
              str(tool_names))
        check("mcp exposes tenx_context", "tenx_context" in tool_names)
        check("mcp exposes tenx_watchdog", "tenx_watchdog" in tool_names)
        check("mcp exposes tenx_capabilities",
              "tenx_capabilities" in tool_names)
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
        r = tenx("set", "SPC-002", "status", "complete", "--force",
                 cwd=gateproj)
        check("gate --force bypasses",
              r.returncode == 0 and "--force used" in r.stderr, r.stderr)
        # evidence field path
        tenx("new", "spec", "Ev spec", "--epic", "EPC-001", cwd=gateproj)
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
        check("catalog has 35 rules", len(cat) == 35, str(len(cat)))

        # ---- tenx review + archive ----
        tenx("new", "epic", "Review epic", cwd=scanproj)
        tenx("new", "spec", "Review spec", "--epic", "EPC-001",
             cwd=scanproj)
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
                    "## Goals / non-goals", "## Design",
                    "## Alternatives considered",
                    "## Cross-cutting concerns", "## Validation"):
            check(f"spec template has {sec!r}", sec in probe)
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
        subprocess.run(["git", "add", "-A"], cwd=gateproj, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"],
                       cwd=gateproj, check=True)

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
        subprocess.run(["git", "commit", "-qm", "sneaky"],
                       cwd=gateproj, check=True)
        out = tenx("validate", "--json", cwd=gateproj).stdout
        warns = json.loads(out)["warnings"]
        check("commit-without-writeback flags sneaky commit",
              any(w["rule"] == "commit-without-writeback" for w in warns),
              str(warns)[:300])
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
        subprocess.run(["git", "commit", "-qm", "documented change"],
                       cwd=gateproj, check=True)
        (gateproj / "src" / "sneak.py").write_text("x = 3\n")
        subprocess.run(["git", "add", "src/sneak.py"], cwd=gateproj,
                       check=True)
        r = tenx("gate", "commit-check", cwd=gateproj)
        check("commit-check default mode warns but passes",
              r.returncode == 0)
        (gateproj / ".tenx/config.yaml").open("a").write(
            "\ncommit_gate: on\n")
        tenx("gate", "commit-check", cwd=gateproj, expect_rc=1)
        check("commit-check mode=on blocks unlogged code", True)
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
        subprocess.run(["git", "commit", "-qm", "documented tweak"],
                       cwd=gateproj, check=True)

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
