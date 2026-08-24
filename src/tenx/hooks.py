"""Session-start hooks: install the context packet into agent runtimes.

Supported targets:

- claude   -> .claude/settings.json SessionStart hook (command output is
              injected into the session context)
- codex / opencode / generic
           -> managed block in AGENTS.md instructing the agent to run the
              packet command at session start
- gemini   -> managed block in GEMINI.md
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
    path.write_text(new_text, encoding="utf-8")
    return True, str(path)


def install(project_root: Path, agent: str) -> list[tuple[bool, str]]:
    results: list[tuple[bool, str]] = []
    if agent == "claude":
        results.append(install_claude_hook(project_root))
        results.append(install_md_block(project_root, "CLAUDE.md"))
    elif agent == "codex":
        results.append(install_md_block(project_root, "AGENTS.md"))
    elif agent == "opencode":
        results.append(install_md_block(project_root, "AGENTS.md"))
    elif agent == "gemini":
        results.append(install_md_block(project_root, "GEMINI.md"))
    elif agent == "all":
        results.append(install_claude_hook(project_root))
        results.append(install_md_block(project_root, "AGENTS.md"))
        results.append(install_md_block(project_root, "CLAUDE.md"))
        results.append(install_md_block(project_root, "GEMINI.md"))
    else:
        raise ValueError(f"unknown agent target: {agent}")
    return results
