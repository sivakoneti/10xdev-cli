"""Agent-harness adapter registry — adapters are data, not code.

Pattern borrowed from OpenDesign's agent-adapter layer
(docs/agent-adapters.md): one declarative record per harness, a generic
engine that reads the fields, and adding a harness = adding one entry.
No per-harness code paths.

Each adapter declares:
- bins: executables to probe on PATH (detection; first hit wins)
- instruction_files: auto-loaded files that receive the managed block
- hook: forced-injection mechanism name, or None
- skills_dir: project-relative native skills dir, or None

The engine (hooks.py) does install/detect uniformly from these fields.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field


@dataclass(frozen=True)
class HarnessAdapter:
    id: str
    name: str
    bins: tuple[str, ...] = ()
    instruction_files: tuple[str, ...] = ("AGENTS.md",)
    hook: str | None = None
    skills_dir: str | None = None
    notes: str = ""


# Catalog mirrors OpenDesign's BASE_AGENT_DEFS transport groups, mapped to
# tenx's integration surface (instruction file + optional forced hook).
ADAPTERS: list[HarnessAdapter] = [
    # --- forced-hook tier ---
    HarnessAdapter(
        id="claude", name="Claude Code", bins=("claude",),
        instruction_files=("CLAUDE.md",), hook="claude-settings",
        skills_dir=".claude/skills",
        notes="SessionStart hook injects the packet stdout"),

    # --- auto-loaded instruction files ---
    HarnessAdapter(id="codex", name="Codex CLI", bins=("codex",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="opencode", name="OpenCode",
                   bins=("opencode", "opencode-cli"),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="cursor", name="Cursor / cursor-agent",
                   bins=("cursor-agent", "cursor"),
                   instruction_files=("AGENTS.md",
                                      ".cursor/rules/tenx.mdc")),
    HarnessAdapter(id="gemini", name="Gemini CLI", bins=("gemini",),
                   instruction_files=("GEMINI.md",)),
    HarnessAdapter(id="cline", name="Cline", bins=(),
                   instruction_files=(".clinerules/tenx.md",),
                   notes="VS Code extension; no PATH binary"),
    HarnessAdapter(id="windsurf", name="Windsurf", bins=("windsurf",),
                   instruction_files=(".windsurfrules",)),
    HarnessAdapter(id="copilot", name="GitHub Copilot CLI",
                   bins=("copilot",),
                   instruction_files=(".github/copilot-instructions.md",)),
    HarnessAdapter(id="continue", name="Continue", bins=(),
                   instruction_files=(".continuerules",),
                   notes="IDE extension; no PATH binary"),
    HarnessAdapter(id="aider", name="Aider", bins=("aider",),
                   instruction_files=("CONVENTIONS.md",),
                   notes="auto-load via /read CONVENTIONS.md or "
                         ".aider.conf.yml read: key"),
    HarnessAdapter(id="amp", name="Amp", bins=("amp",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="qoder", name="Qoder CLI", bins=("qoder",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="qwen", name="Qwen Code", bins=("qwen",),
                   instruction_files=("QWEN.md", "AGENTS.md")),
    HarnessAdapter(id="grok", name="Grok CLI", bins=("grok",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="deepseek", name="DeepSeek CLI", bins=("deepseek",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="deepseek-harness", name="DeepSeek Harness (dsh)",
                   bins=("dsh",), instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="prime-agent", name="Prime Agent",
                   bins=("prime-agent", "prime"),
                   instruction_files=("AGENTS.md",),
                   notes="injects AGENTS.md into the system prompt"),
    HarnessAdapter(id="omp", name="Oh My Pie (omp)", bins=("omp",),
                   instruction_files=("AGENTS.md",),
                   notes="auto-discovers AGENTS.md into the system prompt; "
                         "forced tier via --append-system-prompt "
                         "'$(tenx hook bootstrap)'"),
    HarnessAdapter(id="antigravity", name="Google Antigravity (agy)",
                   bins=("agy", "antigravity"),
                   instruction_files=("GEMINI.md", "AGENTS.md"),
                   notes="Gemini-based CLI; reads GEMINI.md"),

    # --- ACP family (AGENTS.md fallback) ---
    HarnessAdapter(id="devin", name="Devin for Terminal", bins=("devin",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="hermes", name="Hermes", bins=("hermes",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="kimi", name="Kimi CLI", bins=("kimi",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="kiro", name="Kiro CLI", bins=("kiro",),
                   instruction_files=(".kiro/steering/tenx.md",
                                      "AGENTS.md")),
    HarnessAdapter(id="kilo", name="Kilo Code", bins=("kilo",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="vibe", name="Vibe CLI", bins=("vibe",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="vela", name="Vela (AMR)", bins=("vela",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="trae", name="Trae CLI", bins=("trae",),
                   instruction_files=("AGENTS.md",)),
    HarnessAdapter(id="pi", name="Pi", bins=("pi-agent", "pi"),
                   instruction_files=("AGENTS.md",)),

    # --- universal fallback ---
    HarnessAdapter(id="generic", name="Any AGENTS.md-reading harness",
                   bins=(), instruction_files=("AGENTS.md",),
                   notes="industry-standard fallback file"),
]

# boot-time invariant: no two adapters may share an id
_ids = {a.id for a in ADAPTERS}
assert len(_ids) == len(ADAPTERS), "duplicate adapter id"


def get_adapter(adapter_id: str) -> HarnessAdapter | None:
    for a in ADAPTERS:
        if a.id == adapter_id:
            return a
    return None


def adapter_ids() -> list[str]:
    return [a.id for a in ADAPTERS]


def detect_adapters() -> dict[str, str | None]:
    """Probe PATH for every adapter's bins. Fault-isolated per adapter.

    Returns {adapter_id: resolved_binary_or_None}.
    """
    found: dict[str, str | None] = {}
    for a in ADAPTERS:
        hit = None
        for b in a.bins:
            try:
                hit = shutil.which(b)
            except Exception:
                hit = None
            if hit:
                break
        found[a.id] = hit
    return found
