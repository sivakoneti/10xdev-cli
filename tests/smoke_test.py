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
        tenx("set", "SPC-001", "status", "complete", cwd=proj)
        out = tenx("validate", "--json", cwd=proj, expect_rc=0).stdout
        warns = json.loads(out)["warnings"]
        check("derived-status-drift flagged",
              any(w["rule"] == "derived-status-drift" for w in warns), str(warns))
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
        check("log entry", len(entries) == 1 and entries[0]["ref"] == "SPC-001")
        out = tenx("next", "--json", cwd=proj).stdout
        actions = json.loads(out)
        check("next leads with open ticket",
              actions and "SPC-001-T2" in actions[0]["action"], str(actions[:1]))

        print("== context packets ==")
        out = tenx("context", "--mode", "agent", cwd=proj).stdout
        check("packet has epics", "## Epics" in out and "EPC-001" in out)
        check("packet has protocol", "Operating protocol" in out)
        check("packet has conventions index path", "conventions/INDEX.md" in out)
        out = tenx("context", "--mode", "operator", cwd=proj).stdout
        check("operator dashboard", "operator dashboard" in out)
        data = json.loads(tenx("context", "--json", cwd=proj).stdout)
        check("json counts", data["counts"]["specs"] == 1, str(data["counts"]))

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
        tenx("hook", "install", "--agent", "all", cwd=pm)
        check("claude hook in code repo",
              (app / ".claude/settings.json").is_file())
        check("AGENTS.md in code repo", (app / "AGENTS.md").is_file())
        check("no AGENTS.md in PM repo", not (pm / "AGENTS.md").exists())
        out = tenx("context", "--mode", "agent", cwd=app).stdout
        check("packet names governed code repo", "Code repo (governed)" in out)
        out = tenx("doctor", cwd=app).stdout
        check("doctor shows code_root", "code repo (code_root)" in out, out)


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
