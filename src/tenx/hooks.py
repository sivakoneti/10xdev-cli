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

from .locking import atomic_write_text

MANAGED_BEGIN = "<!-- tenx:begin (managed block — do not edit by hand) -->"
MANAGED_END = "<!-- tenx:end -->"

HOOK_COMMAND = "tenx context --mode agent"

AGENT_MD_BLOCK = f"""{MANAGED_BEGIN}
## Project context — tenx meta-harness

This project keeps its context base in `.tenx/` (epics, specs, conventions,
docs, activity log). At the start of every session, before planning or
writing code:

1. Run `tenx update --check` (non-blocking; if a newer tenx exists, tell the
   human and suggest `tenx update`).
2. Run `{HOOK_COMMAND}` and read the whole packet.
3. Follow the operating protocol printed at the end of that packet.
4. Read `.tenx/conventions/INDEX.md` and every convention it lists.

### Hard rules (non-negotiable)

- Track work in the harness: before non-trivial changes, find or create the
  epic+spec (`tenx next`, `tenx show <ID>`); move tickets with
  `tenx ticket <SPEC> <TICKET> <status>`.
- Write back as you go: `tenx log "<what changed>" --ref <ID>`.
- Before you call ANY work done, `tenx validate` MUST pass with 0 errors and
  the spec must have evidence. Never mark work complete otherwise.
- Never archive, merge, or delete without explicit human/operator approval.
- A git pre-commit hook enforces this: commits are rejected while
  `tenx validate` reports errors. Do not bypass it with `--no-verify`
  unless the human explicitly says to.

Useful: `tenx next` (what to work on), `tenx show <ID>` (full artifact),
`tenx log "msg" --ref <ID>` (write back), `tenx validate` (self drift),
`tenx watchdog` / `tenx triage` (what needs attention).
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
    atomic_write_text(path, json.dumps(data, indent=2) + "\n")
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
    atomic_write_text(path, new_text)
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
    atomic_write_text(path, text)
    return True, str(path)


def install_cursor_rule(project_root: Path) -> tuple[bool, str]:
    return install_managed_file(project_root, ".cursor/rules/tenx.mdc",
                                CURSOR_RULE)


def install_cline_rule(project_root: Path) -> tuple[bool, str]:
    return install_managed_file(project_root, ".clinerules/tenx.md")


# ── SPC-020: git-layer enforcement (the universal, harness-agnostic gate) ──

GIT_HOOK_MARKER = "# tenx-managed-pre-commit"

GIT_HOOK_SCRIPT = f"""#!/bin/sh
{GIT_HOOK_MARKER} — enforces the tenx process gate at commit time.
# Runs `tenx validate` and blocks the commit while it reports errors.
# Works for EVERY agent harness because all of them commit through git.
# Managed by tenx: refresh with `tenx hook install --git`. Bypass only with
# `git commit --no-verify` and explicit operator approval.

if command -v tenx >/dev/null 2>&1; then
  TENX="tenx"
elif command -v python3 >/dev/null 2>&1 && python3 -c "import tenx" >/dev/null 2>&1; then
  TENX="python3 -m tenx"
else
  exit 0  # tenx not installed here; never block a commit for that
fi

out="$($TENX validate 2>&1)"
rc=$?
if [ $rc -ne 0 ]; then
  echo "tenx pre-commit gate: BLOCKED - tenx validate reports errors." >&2
  printf '%s\n' "$out" >&2
  echo "Fix the errors, or (with explicit operator approval) git commit --no-verify." >&2
  exit 1
fi
exit 0
"""


def _find_git_dir(start: Path) -> Path | None:
    """Walk up from start to find a directory containing a `.git` dir."""
    cur = start.resolve()
    for cand in [cur, *cur.parents]:
        if (cand / ".git").is_dir():
            return cand / ".git"
    return None


def install_git_hook(project_root: Path) -> tuple[bool, str]:
    """Install a tenx-managed pre-commit hook that runs `tenx validate`.

    Blocks the commit only on errors (warnings/info pass). Idempotent; never
    clobbers a pre-existing non-tenx hook.
    """
    git_dir = _find_git_dir(project_root)
    if git_dir is None:
        return False, "no git repository found; skipped pre-commit hook"
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-commit"
    if hook.is_file():
        existing = hook.read_text(encoding="utf-8")
        if GIT_HOOK_MARKER in existing:
            if existing == GIT_HOOK_SCRIPT:
                return False, str(hook)
        else:
            return False, (f"{hook} exists and is not tenx-managed; "
                           "leaving it alone")
    atomic_write_text(hook, GIT_HOOK_SCRIPT)
    hook.chmod(0o755)
    return True, str(hook)


# ── SPC-019: DSH agent preset (persona-mandated tenx loop) ─────────────────

DSH_PRESET_META = """name: tenx - Process-Compliant Coding Agent
description: >-
  A coding agent that follows the tenx meta-harness process by construction.
  Its persona mandates the tenx loop: read the context packet at session
  start, track work in epics/specs/tickets, write back with tenx log, and
  never call work done until `tenx validate` passes with evidence. Pairs with
  the tenx git pre-commit gate for a non-bypassable backstop.
order: 1
"""

DSH_PRESET_PACKAGE = """{
  "name": "dsh-preset-tenx",
  "type": "module",
  "private": true
}
"""

# NOTE: plain string (not f-string) so DSH's {{model}}/{{cwd}} survive as-is.
DSH_PRESET_CORDIS = """# The `tenx` agent preset: a coding agent that follows the tenx meta-harness
# process by construction. Modeled on the DSH standard/web-researcher presets;
# the persona is the enforcement core.

# ── identity ────────────────────────────────────────────────────────────────

- id: persona
  name: '@deepseek-ai/dsh-persona'
  config:
    text: >-
      You are a tenx process-compliant coding agent powered by the {{model}}
      model, working from {{cwd}}. This project is governed by the tenx
      meta-harness in .tenx/. HARD RULES, non-negotiable:
      1. At session start run `tenx update --check` (non-blocking), then
      `tenx context --mode agent`, and read the whole packet before any work.
      2. Track all non-trivial work in the harness: find or create the
      epic+spec, and move tickets with `tenx ticket <SPEC> <TICKET> <status>`.
      3. Write back as you go: `tenx log "<what changed>" --ref <ID>`.
      4. Before calling ANY work done, `tenx validate` MUST pass with 0 errors
      and the spec must have evidence. Never mark work complete otherwise.
      5. Never archive, merge, or delete without explicit operator approval.
      A git pre-commit hook enforces rule 4 at commit time; do not bypass it
      with --no-verify unless the operator explicitly says so.

- id: agent-instructions
  name: '@deepseek-ai/dsh-agent-instructions'
  config:
    maxBytes: 65536

# ── shell ───────────────────────────────────────────────────────────────────

- id: tool-bash
  name: '@deepseek-ai/dsh-tool-bash'
  disabled: !!js process.platform === 'win32'

- id: tool-pwsh
  name: '@deepseek-ai/dsh-tool-pwsh'
  disabled: !!js process.platform !== 'win32'

# ── filesystem ──────────────────────────────────────────────────────────────

- id: tool-fs
  name: '@deepseek-ai/dsh-tool-fs'

- id: tool-fs-search
  name: '@deepseek-ai/dsh-tool-fs-search'
  config:
    sampleOverCapGlobResults: false

# ── background jobs ────────────────────────────────────────────────────────

- id: tool-jobs
  name: '@deepseek-ai/dsh-tool-jobs'

# ── skills (bundled tenx skills live in this preset's skills/ dir) ─────────

- id: skill-filesystem
  name: '@deepseek-ai/dsh-skill-filesystem'
  config:
    customSkillDirs:
      - !!js "process.getBuiltinModule('node:url').fileURLToPath(new URL('skills/', baseUrl))"

- id: tool-skill
  name: '@deepseek-ai/dsh-tool-skill'

# ── goals ───────────────────────────────────────────────────────────────────

- id: tool-goal
  name: '@deepseek-ai/dsh-tool-goal'

# ── plan mode ───────────────────────────────────────────────────────────────

- id: planning
  name: cordis:group
  group: true
  isolate:
    planMode: true
  config:
    - id: plan-mode
      name: '@deepseek-ai/dsh-plan-mode'
      config:
        section: |
              You are in plan mode. Before coding, read the tenx context
              packet (`tenx context --mode agent`), identify the epic/spec
              this work belongs to, and produce a plan that ends with a
              passing `tenx validate` and a write-back (`tenx log --ref`).

# ── compaction ──────────────────────────────────────────────────────────────

- id: compaction
  name: cordis:group
  group: true
  isolate:
    compaction: true
    toolResultPruner: true
  config:
    - id: compaction-basic
      name: '@deepseek-ai/dsh-compaction-basic'

    - id: command-compact
      name: '@deepseek-ai/dsh-command-compact'

    - id: tool-result-pruner
      name: '@deepseek-ai/dsh-compaction-tool-result-pruner'
      config:
        thresholdChars: 8192
        headChars: 4096
        tailChars: 1024

# ── delegation and workflows ────────────────────────────────────────────────

- id: delegation
  name: cordis:group
  group: true
  isolate:
    workflowEngine: true
  config:
    - id: tool-subagent-control
      name: '@deepseek-ai/dsh-tool-subagent-control'

    - id: tool-subagent
      name: '@deepseek-ai/dsh-tool-subagent'
      config:
        provider: spawn
        toolName: subagent
        backgroundMode: continuable

    - id: tool-workflow
      name: '@deepseek-ai/dsh-tool-workflow'

# ── remaining model-facing rows ─────────────────────────────────────────────

- id: tool-ask-user
  name: '@deepseek-ai/dsh-tool-ask-user'

- id: tool-todo
  name: '@deepseek-ai/dsh-tool-todo'
  config:
    allowParallelInProgress: true

- id: tool-web
  name: '@deepseek-ai/dsh-tool-web'
  config:
    fetch: false
    searchTimeoutMs: 60000
"""


def install_dsh_preset(project_root: Path) -> tuple[bool, str]:
    """Write the tenx DSH agent preset so DSH can mount it.

    Prefers the live DSH preset dir (~/.dsh/.agent-presets/tenx) so it is
    immediately mountable; falls back to <project>/.dsh-preset/tenx when DSH
    is not installed. Bundles the tenx skills into the preset's skills/ dir.
    """
    from .skills import install_skills

    home_dsh = Path.home() / ".dsh"
    if (home_dsh / ".agent-presets").is_dir():
        base = home_dsh / ".agent-presets" / "tenx"
        note = "mounted under ~/.dsh/.agent-presets/tenx"
    else:
        base = project_root / ".dsh-preset" / "tenx"
        note = ("DSH not found; wrote to .dsh-preset/tenx — copy it to "
                "~/.dsh/.agent-presets/tenx to mount")

    files = {
        "preset.yml": DSH_PRESET_META,
        "package.json": DSH_PRESET_PACKAGE,
        "agent.cordis.yml": DSH_PRESET_CORDIS,
    }
    changed = False
    for name, content in files.items():
        p = base / name
        if not (p.is_file() and p.read_text(encoding="utf-8") == content):
            p.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(p, content)
            changed = True
    # bundle the tenx skills so the preset is self-contained
    install_skills(base / "skills")
    return changed, f"{base} ({note})"


# ── hook dispatch ───────────────────────────────────────────────────────────

def _install_hook(target: Path, hook: str) -> tuple[bool, str]:
    if hook == "claude-settings":
        return install_claude_hook(target)
    if hook == "dsh-preset":
        return install_dsh_preset(target)
    return False, f"unknown hook type: {hook}"


BOOTSTRAP_SNIPPET = """This project uses the tenx meta-harness: a structured context base in
`.tenx/` (epics, specs, conventions, docs, activity log).

MANDATORY at session start, before planning or writing any code:
run `tenx context --mode agent` and read the entire packet it prints.
It lists what we are building, the active specs, conventions, recent
activity, and the operating protocol. Follow that protocol.

HARD RULES (non-negotiable):
- Track work in the harness: before non-trivial changes, find or create the
  epic+spec; move tickets with `tenx ticket <SPEC> <TICKET> <status>`.
- Write back as you go: `tenx log "<what changed>" --ref <ID>`.
- Before calling ANY work done, `tenx validate` MUST pass with 0 errors and
  the spec must have evidence. Never mark work complete otherwise.
- Never archive, merge, or delete without explicit human/operator approval.
- A git pre-commit hook rejects commits while `tenx validate` has errors;
  do not bypass it with `--no-verify` unless the human explicitly says so.

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
    if adapter.hook:
        results.append(_install_hook(target, adapter.hook))
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
    from .adapters import ADAPTERS, detect_adapters, get_adapter, resolve_agent_alias
    from .discovery import code_root

    agent = resolve_agent_alias(agent)
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
    done_hooks: set[str] = set()
    done_files: set[str] = set()
    for adapter in selected:
        if adapter.hook and adapter.hook not in done_hooks:
            results.append(_install_hook(target, adapter.hook))
            done_hooks.add(adapter.hook)
        for rel in adapter.instruction_files:
            if rel in done_files:
                continue
            done_files.add(rel)
            results.append(_install_instruction_file(target, rel))
    return results
