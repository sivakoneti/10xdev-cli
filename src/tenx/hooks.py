"""Session-start hooks: install the context packet into agent runtimes.

Two injection tiers:

1. Forced injection — the harness runs a command and injects stdout:
   - claude   -> .claude/settings.json SessionStart hook

2. Auto-loaded instruction files — the harness reads these at session
   start; the managed block instructs the agent to run the packet:
   - codex / opencode / zed / most generic agents -> AGENTS.md
   - gemini    -> GEMINI.md
   - cursor    -> .cursor/rules/tenx.mdc (alwaysApply rule)
   - cline     -> .clinerules/tenx.md
   - windsurf  -> .windsurfrules
   - copilot   -> .github/copilot-instructions.md
   - continue  -> .continuerules

Any other harness works too: the CLI is plain shell + stdout, so any agent
with a terminal tool can run `tenx context --mode agent` on demand.
"""

from __future__ import annotations

import json
from pathlib import Path

MANAGED_BEGIN = "<!-- tenx:begin (managed block — do not edit by hand) -->"
MANAGED_END = "<!-- tenx:end -->"

HOOK_COMMAND = "tenx context --mode agent"

AGENT_MD_BLOCK = f"""{MANAGED_BEGIN}
## Project context — tenx meta-harness

This project keeps its context base in `.tenx/` (epics, specs, conventions,
docs, activity log). At the start of every session, before planning or
writing code:

1. Run `{HOOK_COMMAND}` and read the whole packet.
2. Follow the operating protocol printed at the end of that packet.
3. Read `.tenx/conventions/INDEX.md` and every convention it lists.

Useful: `tenx next` (what to work on), `tenx show <ID>` (full artifact),
`tenx log "msg" --ref <ID>` (write back), `tenx validate` (self drift).

Updates: the tenx CLI self-updates. Run `tenx update --check` at session
start; if a newer version exists, tell the human and suggest
`tenx update` to install it.
{MANAGED_END}"""


def _merge_json_file(path: Path, updater) -> tuple[bool, str]:
    data = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False, f"{path} contains invalid JSON; fix it first"
    changed = updater(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed, str(path)


def install_claude_hook(project_root: Path) -> tuple[bool, str]:
    settings = project_root / ".claude" / "settings.json"

    def updater(data: dict) -> bool:
        hooks = data.setdefault("hooks", {})
        session_start = hooks.setdefault("SessionStart", [])
        for matcher in session_start:
            for h in matcher.get("hooks", []):
                if "tenx context" in str(h.get("command", "")):
                    return False  # already installed
        session_start.append({
            "hooks": [{"type": "command", "command": HOOK_COMMAND}],
        })
        return True

    return _merge_json_file(settings, updater)


def install_md_block(project_root: Path, filename: str = "AGENTS.md") -> tuple[bool, str]:
    path = project_root / filename
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if MANAGED_BEGIN in text and MANAGED_END in text:
        pre, _, post = text.partition(MANAGED_BEGIN)
        _, _, post = post.partition(MANAGED_END)
        new_text = pre + AGENT_MD_BLOCK + post
        if new_text == text:
            return False, str(path)
    else:
        sep = "\n\n" if text.strip() else ""
        new_text = text.rstrip() + sep + AGENT_MD_BLOCK + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_text, encoding="utf-8")
    return True, str(path)


CURSOR_RULE = f"""---
description: tenx meta-harness — run the context packet before any work
globs:
alwaysApply: true
---

{AGENT_MD_BLOCK}
"""


def install_managed_file(project_root: Path, relpath: str,
                         content: str | None = None) -> tuple[bool, str]:
    """Write a fully-managed file (overwritten on every install)."""
    path = project_root / relpath
    text = content if content is not None else AGENT_MD_BLOCK + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return False, str(path)
    path.write_text(text, encoding="utf-8")
    return True, str(path)


def install_cursor_rule(project_root: Path) -> tuple[bool, str]:
    return install_managed_file(project_root, ".cursor/rules/tenx.mdc",
                                CURSOR_RULE)


def install_cline_rule(project_root: Path) -> tuple[bool, str]:
    return install_managed_file(project_root, ".clinerules/tenx.md")


BOOTSTRAP_SNIPPET = """This project uses the tenx meta-harness: a structured context base in
`.tenx/` (epics, specs, conventions, docs, activity log).

MANDATORY at session start, before planning or writing any code:
run `tenx context --mode agent` and read the entire packet it prints.
It lists what we are building, the active specs, conventions, recent
activity, and the operating protocol. Follow that protocol.

Write-back contract: after significant work, record it —
`tenx log "<what changed>" --ref <ID>`, move tickets with
`tenx ticket <SPEC> <TICKET> <status>`, and run `tenx validate` before
finishing. The harness is the source of truth; keep it honest.

Updates: the tenx CLI self-updates. At session start run
`tenx update --check`; if it reports a newer version, tell the human
and suggest `tenx update` to install it."""


def bootstrap_snippet() -> str:
    """The universal one-block bootstrap for ANY harness.

    Paste this into any agent harness's system prompt, custom
    instructions, or session-start config. It only assumes the harness
    can run shell commands and read their output.
    """
    return BOOTSTRAP_SNIPPET


def _install_instruction_file(target: Path, rel: str) -> tuple[bool, str]:
    """Engine: install the managed block into one auto-loaded file.

    File-kind handling is by path shape, not by harness name:
    - *.mdc                     -> Cursor rule with alwaysApply frontmatter
    - .clinerules/*, .kiro/*    -> fully managed standalone file
    - anything else             -> managed block merged into the file
    """
    if rel.endswith(".mdc"):
        return install_managed_file(target, rel, CURSOR_RULE)
    if rel.startswith(".clinerules/") or rel.startswith(".kiro/"):
        return install_managed_file(target, rel)
    return install_md_block(target, rel)


def install_adapter(target: Path, adapter) -> list[tuple[bool, str]]:
    """Engine: install one adapter purely from its declared fields."""
    results: list[tuple[bool, str]] = []
    if adapter.hook == "claude-settings":
        results.append(install_claude_hook(target))
    for rel in adapter.instruction_files:
        results.append(_install_instruction_file(target, rel))
    return results


def install(project_root: Path, agent: str,
            target_root: Path | None = None) -> list[tuple[bool, str]]:
    """Install hooks into target_root (default: the code root).

    agent: an adapter id, "all" (every adapter, deduped), or "detected"
    (only adapters whose binary is on PATH, plus the generic AGENTS.md
    fallback).
    """
    from .adapters import ADAPTERS, detect_adapters, get_adapter
    from .discovery import code_root

    target = target_root or code_root(project_root)
    if agent == "all":
        selected = list(ADAPTERS)
    elif agent == "detected":
        found = detect_adapters()
        selected = [a for a in ADAPTERS if found.get(a.id)]
        generic = get_adapter("generic")
        if generic is not None:
            selected.append(generic)
    else:
        adapter = get_adapter(agent)
        if adapter is None:
            raise ValueError(
                f"unknown agent target: {agent} "
                f"(try one of the adapter ids, 'all', or 'detected')")
        selected = [adapter]

    # dedupe: hooks once, instruction files once each
    results: list[tuple[bool, str]] = []
    done_hook = False
    done_files: set[str] = set()
    for adapter in selected:
        if adapter.hook and not done_hook:
            results.append(install_claude_hook(target))
            done_hook = True
        for rel in adapter.instruction_files:
            if rel in done_files:
                continue
            done_files.add(rel)
            results.append(_install_instruction_file(target, rel))
    return results
