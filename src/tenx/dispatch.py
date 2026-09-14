"""Subagent Ticket Dispatch: brief generation, worktree isolation, and execution.

Provides zero-token context slicing, git worktree lifecycle management,
and headless agent execution across supported harnesses.
Zero runtime dependencies (Python stdlib only, adhering to CON-002).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import Harness, load_harness
from .discovery import code_root
from .multiplexers import (
    MultiplexerTarget,
    ProjectionPlan,
    detect_multiplexer,
    plan_visual_projection,
)


TICKET_BRIEF_TEMPLATE = """# TICKET EXECUTION BRIEF — {spec_id} / {ticket_id}: {ticket_title}

You are executing a single isolated ticket from the tenx context base.
Work autonomously, verify your changes with tests and validation, and record
progress before completion.

## Task
- Spec: `{spec_id}` ({spec_title})
- Ticket ID: `{ticket_id}`
- Title: {ticket_title}
- Ticket Description:
{ticket_desc}

## Relevant Requirements from Spec
{requirements_block}

## Conventions to Follow
{conventions_block}

## Work & Landing Discipline
1. Implement the solution in this workspace.
2. Run local tests: make sure test coverage passes cleanly.
3. Keep frontmatter, ticket status, and activity log up to date:
   `tenx ticket {spec_id} {ticket_id} in_progress`
   `tenx ticket {spec_id} {ticket_id} done`
   `tenx log "Implemented {ticket_id}: <summary>" --ref {spec_id}`
4. Run `tenx validate`: it MUST pass with 0 errors before declaring done.
5. Exit cleanly when complete.
"""


def extract_ticket_info(spec, ticket_id: str) -> dict[str, Any] | None:
    """Find ticket metadata and markdown body from a loaded Spec."""
    meta_ticket = None
    for t in spec.tickets:
        if t.get("id") == ticket_id:
            meta_ticket = t
            break
    if not meta_ticket:
        return None

    # Try to extract the description under ## Tickets in spec.body
    body = spec.body or ""
    # Matches starting from - `TICKET_ID`: or - TICKET_ID: until the next ticket bullet or section heading
    pattern = rf"(?:^|\n)-\s+`?{re.escape(ticket_id)}`?:?\s*(.*?)(?=\n-\s+`?[A-Za-z0-9_-]+-T\d+`?|\n## |\Z)"
    match = re.search(pattern, body, re.DOTALL)
    desc = match.group(1).strip() if match else meta_ticket.get("title", "")

    return {
        "id": ticket_id,
        "title": meta_ticket.get("title", ""),
        "status": meta_ticket.get("status", "todo"),
        "description": desc or meta_ticket.get("title", ""),
    }



def extract_spec_requirements(spec, ticket_title: str, ticket_desc: str) -> str:
    """Extract requirements from spec body that match ticket references."""
    body = spec.body or ""
    # Find all FR-### referenced in ticket title or description
    combined = f"{ticket_title} {ticket_desc}"
    refs = set(re.findall(r"FR-\d{3}", combined))

    req_section = ""
    req_match = re.search(r"## Requirements\s*\n(.*?)(?=\n## |\Z)", body, re.DOTALL)
    if req_match:
        lines = []
        for line in req_match.group(1).splitlines():
            line_str = line.strip()
            if not line_str or not line_str.startswith("-"):
                continue
            fr_match = re.search(r"(FR-\d{3})", line_str)
            if fr_match:
                fr_id = fr_match.group(1)
                if not refs or fr_id in refs:
                    lines.append(line_str)
        if lines:
            req_section = "\n".join(lines)

    if not req_section:
        req_section = "- Follow the specifications and functional requirements in the parent spec."
    return req_section


def get_conventions_summary(harness: Harness) -> str:
    """Read convention index or list key conventions."""
    index_file = harness.root / "conventions" / "INDEX.md"
    if index_file.is_file():
        try:
            content = index_file.read_text(encoding="utf-8").strip()
            if content:
                lines = [l for l in content.splitlines() if l.strip()]
                return "\n".join(lines[:15])
        except Exception:
            pass

    # If INDEX.md doesn't exist yet or is empty, list convention artifacts
    convs = harness.by_type("convention")
    if convs:
        return "\n".join(f"- **{c.id}** — {c.title}" for c in convs)

    return "- Refer to `.tenx/conventions/INDEX.md` and follow all project conventions."




def build_ticket_brief(harness: Harness, spec, ticket_id: str, project_root: Path) -> str:
    """Build a standalone markdown brief for one ticket."""
    t_info = extract_ticket_info(spec, ticket_id)
    if not t_info:
        raise ValueError(f"Ticket {ticket_id} not found in spec {spec.meta.get('id')}")

    req_block = extract_spec_requirements(spec, t_info["title"], t_info["description"])
    conv_block = get_conventions_summary(harness)

    return TICKET_BRIEF_TEMPLATE.format(
        spec_id=spec.meta.get("id", "?"),
        spec_title=spec.meta.get("title", ""),
        ticket_id=ticket_id,
        ticket_title=t_info["title"],
        ticket_desc=t_info["description"],
        requirements_block=req_block,
        conventions_block=conv_block,
    )


# ------------------------------------------------------------- runner

@dataclass(frozen=True)
class AgentCommand:
    agent: str
    cmd: list[str]
    is_headless: bool
    notes: str = ""


def resolve_agent_command(agent: str, worktree_dir: Path, brief_path: Path) -> AgentCommand:
    """Resolve headless CLI command for given harness."""
    agent_norm = agent.lower().strip()
    brief_rel = brief_path.name

    if agent_norm in ("codex", "codex-cli"):
        prompt = (
            f"Read `{brief_rel}` and implement the ticket completely. "
            "Run tests and `tenx validate` before finishing."
        )
        return AgentCommand(
            agent="codex",
            cmd=["codex", "exec", "--dangerously-bypass-approvals-and-sandbox",
                 "-C", str(worktree_dir), prompt],
            is_headless=True,
            notes="Codex CLI headless execution"
        )
    elif agent_norm in ("prime", "prime-agent"):
        prompt = (
            f"Read `{brief_rel}` and implement the ticket completely. "
            "Run tests and `tenx validate` before finishing."
        )
        return AgentCommand(
            agent="prime-agent",
            cmd=["prime", "run", "-C", str(worktree_dir), prompt],
            is_headless=True,
            notes="Prime Agent headless execution"
        )
    elif agent_norm in ("pi", "pi-agent"):
        prompt = (
            f"Read `{brief_rel}` and implement the ticket completely. "
            "Run tests and `tenx validate` before finishing."
        )
        return AgentCommand(
            agent="pi",
            cmd=["pi", "-p", "--cwd", str(worktree_dir), prompt],
            is_headless=True,
            notes="Pi coding agent headless mode"
        )
    elif agent_norm in ("claude", "claude-code"):
        prompt = (
            f"Read `{brief_rel}` and implement the ticket completely. "
            "Run tests and `tenx validate` before finishing."
        )
        return AgentCommand(
            agent="claude",
            cmd=["claude", "-p", prompt],
            is_headless=True,
            notes="Claude Code print/headless mode"
        )
    elif agent_norm in ("dsh", "deepseek-harness"):
        prompt = (
            f"Read `{brief_rel}` and implement the ticket completely. "
            "Run tests and `tenx validate` before finishing."
        )
        return AgentCommand(
            agent="dsh",
            cmd=["dsh", "run", "--workdir", str(worktree_dir), prompt],
            is_headless=True,
            notes="DeepSeek Harness run"
        )
    else:
        # Generic fallback
        prompt = (
            f"Read `{brief_rel}` and implement the ticket completely. "
            "Run tests and `tenx validate` before finishing."
        )
        return AgentCommand(
            agent=agent,
            cmd=[agent, "-p", prompt] if shutil.which(agent) else ["echo", f"Agent binary '{agent}' not found on PATH"],
            is_headless=True,
            notes="Generic CLI adapter fallback"
        )


def setup_worktree(project_root: Path, ticket_id: str) -> Path:
    """Create a git worktree for the ticket under .tenx/worktrees/<TICKET>."""
    worktrees_dir = project_root / ".tenx" / "worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    target_dir = worktrees_dir / ticket_id
    branch_name = f"tenx/{ticket_id}"

    if target_dir.exists():
        return target_dir

    # Check git availability
    if not shutil.which("git"):
        raise RuntimeError("git binary not found on PATH")

    # Check if branch exists
    res = subprocess.run(
        ["git", "branch", "--list", branch_name],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    branch_exists = bool(res.stdout.strip())

    cmd = ["git", "worktree", "add"]
    if branch_exists:
        cmd.extend([str(target_dir), branch_name])
    else:
        cmd.extend(["-b", branch_name, str(target_dir)])

    run = subprocess.run(cmd, cwd=str(project_root), capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(f"Failed to create git worktree: {run.stderr.strip() or run.stdout.strip()}")

    return target_dir


def dispatch_ticket(
    project_root: Path,
    spec_id: str,
    ticket_id: str,
    agent: str = "pi",
    dry_run: bool = False,
    timeout: int | None = 600,
    visual: bool = False,
    multiplexer: str = "auto",
    focus: bool = False,
) -> dict[str, Any]:
    """Execute a ticket in an isolated git worktree with the specified agent."""
    harness = load_harness(project_root)
    spec = harness.get(spec_id)
    if not spec or spec.type != "spec":
        return {"status": "error", "error": f"Spec '{spec_id}' not found"}

    t_info = extract_ticket_info(spec, ticket_id)
    if not t_info:
        return {"status": "error", "error": f"Ticket '{ticket_id}' not found in '{spec_id}'"}

    brief_content = build_ticket_brief(harness, spec, ticket_id, project_root)
    worktree_path = project_root / ".tenx" / "worktrees" / ticket_id
    brief_file = worktree_path / "TICKET_BRIEF.md"
    agent_cmd = resolve_agent_command(agent, worktree_path, brief_file)

    mux_target = detect_multiplexer(preference="none" if not visual else multiplexer)
    projection = plan_visual_projection(mux_target, ticket_id, worktree_path, agent_cmd.cmd, focus=focus) if visual else None

    if dry_run:
        res = {
            "status": "dry_run",
            "spec_id": spec_id,
            "ticket_id": ticket_id,
            "worktree_path": str(worktree_path),
            "branch": f"tenx/{ticket_id}",
            "agent": agent_cmd.agent,
            "command": agent_cmd.cmd,
            "brief_preview": brief_content[:400] + "...",
            "visual": visual,
            "multiplexer": mux_target.name,
        }
        if projection:
            res["projection"] = {
                "multiplexer": projection.multiplexer,
                "summary": projection.summary,
                "create_cmd": projection.create_cmd,
                "run_cmd": projection.run_cmd,
            }
        return res

    # Setup worktree
    try:
        wt_dir = setup_worktree(project_root, ticket_id)
    except Exception as e:
        return {"status": "error", "error": f"Worktree creation failed: {e}"}

    # Write brief
    wt_brief = wt_dir / "TICKET_BRIEF.md"
    wt_brief.write_text(brief_content, encoding="utf-8")

    # If visual projection is requested, launch through multiplexer
    if visual and projection:
        # Create multiplexer container (workspace or window)
        try:
            res_mux = subprocess.run(projection.create_cmd, capture_output=True, text=True, timeout=10)
            if res_mux.returncode != 0:
                return {
                    "status": "error",
                    "spec_id": spec_id,
                    "ticket_id": ticket_id,
                    "error": f"Multiplexer creation failed ({projection.multiplexer}): {res_mux.stderr.strip() or res_mux.stdout.strip()}",
                }

            # If multiplexer is herdr, extract root_pane pane_id from json response or query it to run agent
            if projection.multiplexer == "herdr":
                pane_id = None
                try:
                    out_json = json.loads(res_mux.stdout)
                    pane_id = out_json.get("result", {}).get("root_pane", {}).get("pane_id")
                except Exception:
                    pass

                agent_cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in agent_cmd.cmd)
                if pane_id:
                    subprocess.run(["herdr", "pane", "run", pane_id, agent_cmd_str], capture_output=True, text=True, timeout=10)
                else:
                    # Fallback if parsing failed
                    subprocess.run(["herdr", "pane", "run", agent_cmd_str], capture_output=True, text=True, timeout=10)
            elif projection.run_cmd:
                subprocess.run(projection.run_cmd, capture_output=True, text=True, timeout=10)

            return {
                "status": "dispatched",
                "spec_id": spec_id,
                "ticket_id": ticket_id,
                "worktree_path": str(wt_dir),
                "branch": f"tenx/{ticket_id}",
                "agent": agent_cmd.agent,
                "visual": True,
                "multiplexer": projection.multiplexer,
                "projection_summary": projection.summary,
                "notes": f"Running visually in {projection.multiplexer} ({projection.summary})",
            }
        except Exception as e:
            return {
                "status": "error",
                "spec_id": spec_id,
                "ticket_id": ticket_id,
                "error": f"Multiplexer execution failed: {e}",
            }

    # Execute headless agent command
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(wt_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "status": "completed" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "spec_id": spec_id,
            "ticket_id": ticket_id,
            "worktree_path": str(wt_dir),
            "branch": f"tenx/{ticket_id}",
            "stdout": proc.stdout[-2000:] if proc.stdout else "",
            "stderr": proc.stderr[-2000:] if proc.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "spec_id": spec_id,
            "ticket_id": ticket_id,
            "worktree_path": str(wt_dir),
            "branch": f"tenx/{ticket_id}",
            "error": f"Execution timed out after {timeout} seconds",
        }
    except Exception as e:
        return {
            "status": "error",
            "spec_id": spec_id,
            "ticket_id": ticket_id,
            "worktree_path": str(wt_dir),
            "branch": f"tenx/{ticket_id}",
            "error": str(e),
        }
