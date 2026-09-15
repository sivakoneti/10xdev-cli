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

- Scope: tenx governs codebase engineering (code, architecture, tests, docs).
  Operational execution (running pipelines, workflows, scripts, generating
  media/assets) runs directly without creating or updating tenx artifacts.
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
  echo "tenx pre-commit gate: WARNING - no tenx CLI found; skipping gate." >&2
  exit 0  # tenx not installed here; never block a commit for that
fi

# SPC-023-T9: a hung or broken tenx must not wedge commits. Use a timeout
# when available and fail OPEN (with a visible warning) on timeout/start
# failure; only a real validate/gate verdict blocks.
RUN=""
if command -v timeout >/dev/null 2>&1; then
  RUN="timeout 60"
fi

out="$($RUN $TENX validate 2>&1)"
rc=$?
if [ $rc -eq 124 ] || [ $rc -eq 125 ] || [ $rc -eq 126 ] || [ $rc -eq 127 ]; then
  echo "tenx pre-commit gate: WARNING - tenx validate timed out or could not" >&2
  echo "run (rc=$rc); failing open. Check `tenx doctor`." >&2
  exit 0
fi
if [ $rc -ne 0 ]; then
  echo "tenx pre-commit gate: BLOCKED - tenx validate reports errors." >&2
  printf '%s\n' "$out" >&2
  echo "Fix the errors, or (with explicit operator approval) git commit --no-verify." >&2
  exit 1
fi

# SPC-023-T4: staged code must have write-back behind it.
# Mode comes from commit_gate in .tenx/config.yaml (on|warn|off, default warn).
$RUN $TENX gate commit-check
rc=$?
if [ $rc -eq 124 ] || [ $rc -eq 125 ] || [ $rc -eq 126 ] || [ $rc -eq 127 ]; then
  echo "tenx pre-commit gate: WARNING - tenx gate commit-check timed out or" >&2
  echo "could not run (rc=$rc); failing open. Check `tenx doctor`." >&2
  exit 0
fi
if [ $rc -ne 0 ]; then
  echo "tenx pre-commit gate: BLOCKED - staged code has no write-back." >&2
  echo "Log your work (tenx log ... --ref <ID>), or (with explicit operator" >&2
  echo "approval) git commit --no-verify." >&2
  exit 1
fi
exit 0
"""


def find_stale_surfaces(code_root: Path) -> list[str]:
    """SPC-023-T8: managed instruction files whose block predates the
    shipped template. Shared by `tenx doctor` and the
    `agent-surface-stale` validate rule. Returns repo-relative paths."""
    def managed_region(text: str) -> str | None:
        if MANAGED_BEGIN not in text or MANAGED_END not in text:
            return None
        start = text.index(MANAGED_BEGIN)
        end = text.index(MANAGED_END, start) + len(MANAGED_END)
        return text[start:end]

    stale: list[str] = []
    block_files = ("AGENTS.md", "CLAUDE.md", "GEMINI.md",
                   ".clinerules/tenx.md", ".windsurfrules",
                   ".github/copilot-instructions.md", ".continuerules",
                   ".kiro/steering/tenx.md", "CONVENTIONS.md", "QWEN.md")
    for rel in block_files:
        p = code_root / rel
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        region = managed_region(text)
        if region is not None and region != AGENT_MD_BLOCK:
            stale.append(rel)
    cursor = code_root / ".cursor" / "rules" / "tenx.mdc"
    if cursor.is_file() and cursor.read_text(
            encoding="utf-8", errors="replace") != CURSOR_RULE:
        stale.append(".cursor/rules/tenx.mdc")
    return stale


def _find_git_dir(start: Path) -> Path | None:
    """Walk up from start to find a directory containing a `.git` dir.

    Handles linked worktrees: their `.git` is a FILE containing
    `gitdir: <path>`. Hooks live in the common dir, so follow the
    worktree's `commondir` pointer when present — installing into the
    per-worktree dir would leave the gate silently inactive.
    """
    cur = start.resolve()
    for cand in [cur, *cur.parents]:
        candidate = cand / ".git"
        if candidate.is_dir():
            return candidate
        if candidate.is_file():
            try:
                line = candidate.read_text(
                    encoding="utf-8", errors="replace").strip()
            except OSError:
                return None
            if line.startswith("gitdir:"):
                gd = Path(line.split(":", 1)[1].strip())
                if not gd.is_absolute():
                    gd = cand / gd
                gd = gd.resolve()
                if gd.is_dir():
                    common = gd / "commondir"
                    if common.is_file():
                        try:
                            cd = Path(common.read_text(
                                encoding="utf-8").strip())
                            if not cd.is_absolute():
                                cd = gd / cd
                            cd = cd.resolve()
                            if cd.is_dir():
                                return cd
                        except OSError:
                            pass
                    return gd
            return None
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

DSH_PRESET_META = """name: tenx — Meta-Harness Engineering Agent
description: >-
  tenx's own engineering agent — context-as-code for AI coding agents.
  tenx turns any project into a context base of structured markdown
  (epics, specs, conventions, docs) that keeps agents briefed, on-rails,
  and accountable across sessions. This agent embodies that process by
  construction: it boots on the session-start context packet, tracks work
  in epics/specs/tickets, writes back with `tenx log`, and never calls
  work done until `tenx validate` passes with evidence — backed by the
  tenx git pre-commit gate as a non-bypassable backstop.
order: 1
"""

DSH_PRESET_PACKAGE = """{
  "name": "dsh-preset-tenx",
  "type": "module",
  "private": true
}
"""

# NOTE: plain string (not f-string) so DSH's {{model}}/{{cwd}} survive as-is.
DSH_PRESET_CORDIS = """# The `tenx` agent preset: a tenx process-compliant coding agent.
# Derived from the shipped `standard` preset with tenx hard-rules persona,
# tenx-aware plan mode, and bundled tenx skills via customSkillDirs.
#
# This file is an AGENT-PLANE composition. The roster mounts it ONCE under a
# standing scope; every session naming it joins by scope parentage, so the
# tools and prompt sections registered here cover each joined agent while a
# session's own state stays keyed per Session/Agent inside the plugins. The
# host composition (`base.cordis.yml` + `web.cordis.yml`) keeps everything a
# preset must not own: the registries themselves, the sandbox and approval
# stack, persistence, and the model route.
#
# A service row here MUST sit inside a group carrying an `isolate` realm.
# Without one it publishes into the root realm, where it is process-global —
# another preset publishing the same name collides, and a host reader would
# resolve one preset's instance for every session; `dsh-agent-presets` rejects
# that at mount. `true` means an entry-local realm: this standing mount's own
# private instance, apart from every other preset's. (A shared label does NOT
# pool instances — `provide()` throws on the second registration under the
# same realm symbol; labels join REALMS, and are not what this file needs.)

# ── identity ────────────────────────────────────────────────────────────────

# The preset's own persona, shadowing the deployment default for this agent.
# `{{model}}` and `{{cwd}}` resolve from the agent's own route and workspace.
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

# `shell-env` stays in the HOST composition: `apps/cli/src/web.ts` injects it to
# publish `DSH_WEB_URL`/`DSH_WEB_MODE`, and a host row that injects a service is
# the criterion for host-plane ownership — injection resolves before any session
# exists, so there is no agent to key by. Behind a preset realm those variables
# never reached the model's shell at all. Both shell tools consume the host
# registry from here; their executors (`bash-sandbox`/`pwsh-sandbox`) are
# host-plane too.
- id: tool-bash
  name: '@deepseek-ai/dsh-tool-bash'
  disabled: !!js process.platform === 'win32'

- id: tool-pwsh
  name: '@deepseek-ai/dsh-tool-pwsh'
  disabled: !!js process.platform !== 'win32'

# ── filesystem ──────────────────────────────────────────────────────────────

# Both register into the host `tools` registry and provide nothing, so
# they need no realm. The `fs` service and its policy stay in the host.
- id: tool-fs
  name: '@deepseek-ai/dsh-tool-fs'

- id: tool-fs-search
  name: '@deepseek-ai/dsh-tool-fs-search'
  config:
    sampleOverCapGlobResults: false

# ── background jobs ────────────────────────────────────────────────────────

# Only the model-facing controls. The task REGISTRY stays on the host plane:
# its producers sit outside any realm this file could put it in — `tool-bash`
# above resolves it with `ctx.get`, and an entry-local realm here is invisible
# to every sibling row, so `run_in_background` would answer "background jobs
# unavailable" while these controls sat in the catalog. The registry is keyed by
# owning agent anyway, so one host instance serves every session. What a preset
# chooses is whether its agent can collect and stop background work at all.
- id: tool-jobs
  name: '@deepseek-ai/dsh-tool-jobs'

# ── skills ──────────────────────────────────────────────────────────────────

# The skill REGISTRY lives in the host composition and is layered per scope:
# these rows register into THIS preset's layer of it, so they need no realm.
# `skill-filesystem` contributes local-root discovery for agents on this preset, and
# `tool-skill` gives them the catalog and loader; the merged catalog also
# carries whatever the deployment registered globally (repository plugins).
- id: skill-filesystem
  name: '@deepseek-ai/dsh-skill-filesystem'
  config:
    customSkillDirs:
      - !!js "process.getBuiltinModule('node:url').fileURLToPath(new URL('skills/', baseUrl))"


- id: tool-skill
  name: '@deepseek-ai/dsh-tool-skill'

# ── goals ───────────────────────────────────────────────────────────────────

# Only the model-facing tool. The goal SERVICE, its session driver, and the
# `/goal` command stay on the host plane: the Gateway serves the goal domain as
# Remote endpoints whose receiver comes from a generated descriptor, so it
# resolves `goals` on the host and an entry-local realm here would hide it. The
# registry is keyed by session anyway, so one host instance serves every
# session. What a preset chooses is whether its agent can call the goal tool.
- id: tool-goal
  name: '@deepseek-ai/dsh-tool-goal'

# ── plan mode ───────────────────────────────────────────────────────────────

# Plan state is per-agent by nature, so an entry-local realm is not a
# workaround here — it is the correct lifetime.
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

# `compaction-basic` reads `toolResultPrune` through `ctx.get`, so the pruner must
# share this realm rather than sit outside it.
#
# `tokenMeter` is deliberately NOT in this realm: the meter stays on the HOST
# plane, and the rows here resolve that one instance. It takes no configuration,
# keys every fold by Session, and owns the context-meter projection units the
# browser reads for every session — behind a realm those units would come and go
# with whichever presets happen to be mounted. What a preset chooses is whether
# its agent compacts at all, which is `compaction-basic` below.
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

# The `subagents` registry and its spawn/fork backends live in the HOST
# composition: the registry is a process singleton whose cross-session queries
# the api-proxy serves to the browser, and a provider name may only be
# registered once. This preset contributes the delegation TOOLS, which resolve
# that host registry.
#
# `workflows` is different — nothing outside an agent reads it — so every row
# that reaches it shares one entry-local realm here, and a consumer left
# outside would resolve a host registry this preset does not populate.
#
# `tool-subagent-report` is host-plane for the same reason as the registry,
# not because a preset may not want it: it registers a CONTINUABLE SETUP on
# that singleton rather than a tool this agent calls, and the setup list is
# not scope-aware — one copy per mounted preset means every child gets
# `report` registered once per live session, which throws on the second.
- id: delegation
  name: cordis:group
  group: true
  isolate:
    workflowEngine: true
  config:
    - id: tool-subagent-control
      name: '@deepseek-ai/dsh-tool-subagent-control'

    - id: tool-subagent-list-agents
      name: '@deepseek-ai/dsh-tool-subagent-control/list-agents'

    - id: tool-subagent
      name: '@deepseek-ai/dsh-tool-subagent'
      config:
        provider: spawn
        toolName: subagent
        backgroundMode: continuable

    - id: tool-subagent-fork
      name: '@deepseek-ai/dsh-tool-subagent'
      config:
        provider: fork
        toolName: subagent_fork
        backgroundMode: continuable

    # Production dsh does not install these optional providers. Install the
    # matching Bundle in this Profile and restart the Host, then copy this
    # preset and remove `disabled` from the matching tool row. Host availability
    # alone grants no tool.
    - id: tool-subagent-codex
      name: '@deepseek-ai/dsh-tool-subagent'
      disabled: true
      config:
        provider: codex
        toolName: subagent_codex
        backgroundMode: one-shot
        maxDepth: provider-managed

    - id: tool-subagent-claude-code
      name: '@deepseek-ai/dsh-tool-subagent'
      disabled: true
      config:
        provider: claude-code
        toolName: subagent_claude_code
        backgroundMode: one-shot
        maxDepth: provider-managed

    - id: workflow-worker-thread
      name: '@deepseek-ai/dsh-workflow-worker-thread'
      config:
        provider: spawn

    - id: tool-workflow
      name: '@deepseek-ai/dsh-tool-workflow'

    - id: tool-ralph
      name: '@deepseek-ai/dsh-tool-ralph'
      config:
        subagentProvider: spawn
        maxRounds: 64

# ── remaining model-facing rows ─────────────────────────────────────────────

- id: tool-ask-user
  name: '@deepseek-ai/dsh-tool-ask-user'

- id: tool-todo
  name: '@deepseek-ai/dsh-tool-todo'
  config:
    allowParallelInProgress: true

# The `web` service and its search provider stay in the host composition; only
# the model-facing tool is per-session.
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
- Scope: tenx governs codebase engineering. Operational execution (running
  pipelines, scripts, tools, generating assets) runs directly without tenx.
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
