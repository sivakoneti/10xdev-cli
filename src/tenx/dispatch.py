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
    position_herdr_workspace_below_parent,
)
from .subagent_state import brief_path as state_brief_path
from .subagent_state import write_receipt
from .router import resolve_model_route


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


def _herdr_agent_kind(agent: str) -> str | None:
    """Return Herdr's recognized kind for a supported dispatch harness."""
    return {
        "omp": "omp",
        "oh-my-pi": "omp",
        "pi": "pi",
        "pi-agent": "pi",
        "codex": "codex",
        "codex-cli": "codex",
    }.get(agent.lower().strip())


def _run_herdr_command(args: list[str], timeout: int = 15) -> dict[str, Any]:
    """Run one official Herdr CLI command and normalize its JSON/error result."""
    try:
        proc = subprocess.run(
            ["herdr", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": f"Herdr command failed to run: {exc}"}
    if proc.returncode != 0:
        return {
            "ok": False,
            "error": proc.stderr.strip() or proc.stdout.strip() or
            f"Herdr command exited {proc.returncode}",
        }
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"Herdr returned invalid JSON: {exc}"}
    if not isinstance(payload, dict) or payload.get("error"):
        return {"ok": False, "error": payload.get("error") if isinstance(payload, dict) else "Herdr returned an invalid response"}
    return {"ok": True, "payload": payload}


def _start_herdr_agent(
    brief_path: Path,
    ticket_id: str,
    agent: str,
    model: str | None,
    thinking: str | None,
    pane_id: str,
    workspace_id: str | None,
    timeout: int,
) -> dict[str, Any]:
    """Start and prompt a recognized agent through Herdr's agent surface."""
    kind = _herdr_agent_kind(agent)
    if not kind:
        return {"ok": False, "error": f"Herdr does not recognize agent kind '{agent}'"}
    name = "tenx_" + re.sub(r"[^a-z0-9_-]", "_", ticket_id.lower())[:24]
    start_args = [
        "agent", "start", name, "--kind", kind, "--pane", pane_id,
        "--timeout", str(timeout * 1000),
    ]
    native_args: list[str] = []
    if model and kind in ("omp", "pi", "codex", "grok"):
        native_args.extend(["--model", model])
    if thinking and kind in ("omp", "pi"):
        native_args.extend(["--thinking", thinking])
    if thinking and kind == "grok":
        native_args.extend(["--reasoning-effort", thinking])
    if native_args:
        start_args.extend(["--", *native_args])
    started = _run_herdr_command(start_args, timeout=timeout + 5)
    if not started["ok"]:
        return started
    agent_payload = started["payload"].get("result", {}).get("agent", {})
    prompt = (
        f"Read {brief_path} and implement this ticket completely. "
        "Run the exact tests and tenx validate required by the brief. "
        "Record progress and stop cleanly when complete."
    )
    prompted = _run_herdr_command(
        ["agent", "prompt", name, prompt, "--wait", "--timeout", str(timeout * 1000)],
        timeout=timeout + 5,
    )
    if not prompted["ok"]:
        return {"ok": False, "error": prompted["error"], "agent_name": name}
    inspected = _run_herdr_command(["agent", "get", name], timeout=15)
    if not inspected["ok"]:
        return {"ok": False, "error": inspected["error"], "agent_name": name}
    current = inspected["payload"].get("result", {}).get("agent", {})
    status = current.get("agent_status")
    if status == "blocked":
        return {
            "ok": False,
            "error": "Herdr agent is blocked; inspect agent output before retrying",
            "agent_name": name,
            "agent_status": status,
        }
    if status not in ("idle", "done"):
        return {
            "ok": False,
            "error": f"Herdr agent did not reach a settled state (status: {status or 'unknown'})",
            "agent_name": name,
            "agent_status": status,
        }
    return {
        "ok": True,
        "agent_name": name,
        "agent": agent_payload,
        "agent_status": status,
        "workspace_id": workspace_id,
        "pane_id": pane_id,
    }
def resolve_agent_command(
    agent: str,
    worktree_dir: Path,
    brief_path: Path,
    model: Optional[str] = None,
    thinking: Optional[str] = None,
    interactive: bool = False,
) -> AgentCommand:
    """Resolve CLI command for given harness and model.
    
    If interactive is True (e.g. visual projection in Herdr/tmux), launches
    the full TUI session so users see live conversation, streaming thoughts,
    and tool executions, exactly like firstmate.
    """
    agent_norm = agent.lower().strip()
    brief_ref = str(brief_path)
    prompt = (
        f"Read {brief_ref} and implement the ticket completely. "
        "Run tests and tenx validate before finishing."
    )

    if agent_norm in ("codex", "codex-cli"):
        if interactive:
            cmd = ["codex", "--dangerously-bypass-approvals-and-sandbox", "-C", str(worktree_dir)]
        else:
            cmd = ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-C", str(worktree_dir)]
        if model:
            cmd.extend(["--model", model])
        cmd.append(prompt)
        return AgentCommand(
            agent="codex",
            cmd=cmd,
            is_headless=not interactive,
            notes="Codex CLI interactive TUI" if interactive else "Codex CLI headless execution"
        )
    elif agent_norm in ("omp", "oh-my-pi"):
        cmd = ["omp"]
        if not interactive:
            cmd.append("-p")
        else:
            cmd.append("--auto-approve")
        cmd.extend(["--cwd", str(worktree_dir)])
        if model:
            cmd.extend(["--model", model])
        if thinking:
            cmd.extend(["--thinking", thinking])
        cmd.append(prompt)
        return AgentCommand(
            agent="omp",
            cmd=cmd,
            is_headless=not interactive,
            notes="Oh My Pi interactive TUI" if interactive else "Oh My Pi agent execution"
        )
    elif agent_norm in ("pi", "pi-agent"):
        cmd = ["pi"]
        if not interactive:
            cmd.append("-p")
        else:
            cmd.extend(["--tui-mode", "regular"])
        if model:
            cmd.extend(["--model", model])
        if thinking:
            cmd.extend(["--thinking", thinking])
        cmd.append(prompt)
        return AgentCommand(
            agent="pi",
            cmd=cmd,
            is_headless=not interactive,
            notes="Pi coding agent interactive TUI" if interactive else "Pi coding agent headless mode"
        )
    elif agent_norm in ("prime", "prime-agent"):
        cmd = ["prime-agent"]
        if not interactive:
            cmd.append("-p")
        cmd.extend(["--cwd", str(worktree_dir)])
        if model:
            cmd.extend(["--model", model])
        if thinking:
            cmd.extend(["--thinking", thinking])
        cmd.append(prompt)
        return AgentCommand(
            agent="prime-agent",
            cmd=cmd,
            is_headless=not interactive,
            notes="Prime Agent interactive TUI" if interactive else "Prime Agent execution"
        )
    elif agent_norm in ("grok",):
        if not shutil.which("grok"):
            raise RuntimeError("Agent binary 'grok' not found on PATH")
        cmd = ["grok"]
        if not interactive:
            cmd.extend(["--single", prompt])
        else:
            cmd.append(prompt)
        if model:
            cmd.extend(["--model", model])
        if thinking:
            cmd.extend(["--reasoning-effort", thinking])
        return AgentCommand(
            agent="grok",
            cmd=cmd,
            is_headless=not interactive,
            notes="Grok Build interactive TUI" if interactive else "Grok Build headless execution",
        )
    elif agent_norm in ("claude", "claude-code"):
        if not shutil.which("claude"):
            raise RuntimeError("Agent binary 'claude' not found on PATH")
        cmd = ["claude"]
        if not interactive:
            cmd.append("-p")
        if model:
            cmd.extend(["--model", model])
        cmd.append(prompt)
        return AgentCommand(
            agent="claude",
            cmd=cmd,
            is_headless=not interactive,
            notes="Claude Code interactive TUI" if interactive else "Claude Code headless execution",
        )
    elif agent_norm in ("dsh", "deepseek-harness"):
        if not shutil.which("dsh"):
            raise RuntimeError("Agent binary 'dsh' not found on PATH")
        cmd = ["dsh", "headless", prompt]
        return AgentCommand(
            agent="dsh",
            cmd=cmd,
            is_headless=True,
            notes="DeepSeek Harness headless execution",
        )
    else:
        if not shutil.which(agent):
            raise RuntimeError(f"Agent binary '{agent}' not found on PATH")
        cmd = [agent, prompt] if interactive else [agent, "-p", prompt]
        return AgentCommand(
            agent=agent,
            cmd=cmd,
            is_headless=not interactive,
            notes="Generic CLI adapter fallback",
        )


def setup_worktree(project_root: Path, ticket_id: str) -> Path:
    """Create a git worktree for the ticket under .tenx/worktrees/<TICKET>."""
    worktrees_dir = project_root / ".tenx" / "worktrees"
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    target_dir = worktrees_dir / ticket_id
    branch_name = f"tenx/{ticket_id}"

    if target_dir.exists():
        registered = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )
        if registered.returncode == 0 and f"worktree {target_dir}" in registered.stdout:
            return target_dir
        raise RuntimeError(f"Dispatch path exists but is not a registered worktree: {target_dir}")

    # Check git availability
    if not shutil.which("git"):
        raise RuntimeError("git binary not found on PATH")

    # Resolve parent checkout HEAD commit to ensure strict baseline isolation
    rev_res = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    parent_commit = rev_res.stdout.strip() if rev_res.returncode == 0 else "HEAD"

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
        # Branch explicitly from the parent's current checkout HEAD commit
        cmd.extend(["-b", branch_name, str(target_dir), parent_commit])

    run = subprocess.run(cmd, cwd=str(project_root), capture_output=True, text=True)
    if run.returncode != 0:
        raise RuntimeError(f"Failed to create git worktree: {run.stderr.strip() or run.stdout.strip()}")

    return target_dir


def dispatch_ticket(
    project_root: Path,
    spec_id: str,
    ticket_id: str,
    agent: str = "pi",
    model: Optional[str] = None,
    thinking: Optional[str] = None,
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

    # Resolve model route via Bifrost and Agent Anti-Gravity
    model_route = resolve_model_route(requested_model=model, tier=2)
    active_model = model_route.model

    brief_content = build_ticket_brief(harness, spec, ticket_id, project_root)
    worktree_path = project_root / ".tenx" / "worktrees" / ticket_id
    brief_file = state_brief_path(project_root, ticket_id)
    try:
        agent_cmd = resolve_agent_command(
            agent, worktree_path, brief_file, model=active_model,
            thinking=thinking, interactive=visual,
        )
    except RuntimeError as exc:
        return {"status": "error", "error": str(exc), "spec_id": spec_id, "ticket_id": ticket_id}

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
            "model": active_model,
            "model_route": {
                "model": model_route.model,
                "provider": model_route.provider,
                "tier": model_route.tier,
                "source": model_route.source,
                "live": model_route.is_live,
            },
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

    if visual and projection and projection.multiplexer == "herdr" and not mux_target.is_active:
        return {
            "status": "error",
            "spec_id": spec_id,
            "ticket_id": ticket_id,
            "error": "Herdr visual dispatch requires HERDR_ENV=1 and an active Herdr CLI; read skill://herdr and run from a Herdr-managed pane",
        }

    # Setup worktree
    try:
        wt_dir = setup_worktree(project_root, ticket_id)
    except Exception as e:
        return {"status": "error", "error": f"Worktree creation failed: {e}"}

    # Keep launch instructions outside the worktree so reconcile can reject
    # every real uncommitted change without special-casing the brief.
    wt_brief = state_brief_path(project_root, ticket_id)
    wt_brief.parent.mkdir(parents=True, exist_ok=True)
    wt_brief.write_text(brief_content, encoding="utf-8")

    # If visual projection is requested, launch through the official
    # multiplexer surface and require a verified agent receipt.
    if visual and projection:
        try:
            if projection.multiplexer == "herdr":
                res_mux = subprocess.run(projection.create_cmd, capture_output=True, text=True, timeout=10)
                if res_mux.returncode != 0:
                    return {
                        "status": "error",
                        "spec_id": spec_id,
                        "ticket_id": ticket_id,
                        "error": f"Multiplexer creation failed ({projection.multiplexer}): {res_mux.stderr.strip() or res_mux.stdout.strip()}",
                    }
            if projection.multiplexer == "herdr":
                if os.environ.get("HERDR_ENV") != "1":
                    return {
                        "status": "error",
                        "spec_id": spec_id,
                        "ticket_id": ticket_id,
                        "error": "Herdr visual dispatch requires HERDR_ENV=1; read skill://herdr and run from a Herdr-managed pane",
                    }
                try:
                    out_json = json.loads(res_mux.stdout)
                    res_payload = out_json.get("result", {})
                    child_ws_id = res_payload.get("workspace", {}).get("workspace_id")
                    pane_id = res_payload.get("root_pane", {}).get("pane_id")
                except (AttributeError, json.JSONDecodeError) as exc:
                    return {
                        "status": "error",
                        "spec_id": spec_id,
                        "ticket_id": ticket_id,
                        "error": f"Herdr workspace creation returned invalid JSON: {exc}",
                    }
                if not child_ws_id or not pane_id:
                    return {
                        "status": "error",
                        "spec_id": spec_id,
                        "ticket_id": ticket_id,
                        "error": "Herdr workspace creation did not return both workspace_id and root pane_id",
                    }
                sock_path = os.environ.get("HERDR_SOCKET_PATH") or str(Path.home() / ".config" / "herdr" / "herdr.sock")
                if os.path.exists(sock_path):
                    position_herdr_workspace_below_parent(sock_path, child_ws_id)
                receipt = {
                    "status": "starting",
                    "spec_id": spec_id,
                    "ticket_id": ticket_id,
                    "worktree_path": str(wt_dir),
                    "branch": f"tenx/{ticket_id}",
                    "multiplexer": "herdr",
                    "workspace_id": child_ws_id,
                    "pane_id": pane_id,
                    "agent": agent_cmd.agent,
                    "brief_path": str(wt_brief),
                }
                write_receipt(project_root, ticket_id, receipt)
                started = _start_herdr_agent(
                    brief_path=wt_brief,
                    ticket_id=ticket_id,
                    agent=agent_cmd.agent,
                    model=active_model,
                    thinking=thinking,
                    pane_id=pane_id,
                    workspace_id=child_ws_id,
                    timeout=timeout or 600,
                )
                if not started["ok"]:
                    receipt.update({"status": "error", "error": started["error"], "agent_name": started.get("agent_name")})
                    write_receipt(project_root, ticket_id, receipt)
                    return {**receipt, "stderr": started["error"]}
                receipt.update({
                    "status": "completed" if started.get("agent_status") in ("idle", "done") else "dispatched",
                    "agent_name": started["agent_name"],
                    "agent_status": started.get("agent_status"),
                })
                write_receipt(project_root, ticket_id, receipt)
                return {
                    **receipt,
                    "visual": True,
                    "projection_summary": projection.summary,
                    "notes": f"Herdr agent settled in state {started.get('agent_status')}",
                }
            elif projection.multiplexer == "tmux":
                created = subprocess.run(projection.create_cmd, capture_output=True, text=True, timeout=10)
                if created.returncode != 0:
                    return {
                        "status": "error",
                        "spec_id": spec_id,
                        "ticket_id": ticket_id,
                        "worktree_path": str(wt_dir),
                        "error": created.stderr.strip() or created.stdout.strip() or "tmux window creation failed",
                    }
                window_id, _, pane_id = created.stdout.strip().partition(":")
                receipt = {
                    "status": "dispatched",
                    "spec_id": spec_id,
                    "ticket_id": ticket_id,
                    "worktree_path": str(wt_dir),
                    "branch": f"tenx/{ticket_id}",
                    "multiplexer": "tmux",
                    "window_id": window_id,
                    "pane_id": pane_id or None,
                    "agent": agent_cmd.agent,
                    "brief_path": str(wt_brief),
                    "visual": True,
                    "projection_summary": projection.summary,
                }
                write_receipt(project_root, ticket_id, receipt)
                return receipt
        except Exception as exc:
            return {
                "status": "error",
                "spec_id": spec_id,
                "ticket_id": ticket_id,
                "error": f"Multiplexer execution failed: {exc}",
            }

    # Execute headless agent command
    try:
        proc = subprocess.run(
            agent_cmd.cmd,
            cwd=str(wt_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        receipt = {
            "status": "completed" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "spec_id": spec_id,
            "ticket_id": ticket_id,
            "worktree_path": str(wt_dir),
            "branch": f"tenx/{ticket_id}",
            "agent": agent_cmd.agent,
            "multiplexer": "none",
            "brief_path": str(wt_brief),
            "stdout": proc.stdout[-2000:] if proc.stdout else "",
            "stderr": proc.stderr[-2000:] if proc.stderr else "",
        }
        write_receipt(project_root, ticket_id, receipt)
        return receipt
    except subprocess.TimeoutExpired:
        receipt = {
            "status": "timeout",
            "spec_id": spec_id,
            "ticket_id": ticket_id,
            "worktree_path": str(wt_dir),
            "branch": f"tenx/{ticket_id}",
            "agent": agent_cmd.agent,
            "multiplexer": "none",
            "brief_path": str(wt_brief),
            "error": f"Execution timed out after {timeout} seconds",
        }
        write_receipt(project_root, ticket_id, receipt)
        return receipt
    except Exception as exc:
        receipt = {
            "status": "error",
            "spec_id": spec_id,
            "ticket_id": ticket_id,
            "worktree_path": str(wt_dir),
            "branch": f"tenx/{ticket_id}",
            "agent": agent_cmd.agent,
            "multiplexer": "none",
            "brief_path": str(wt_brief),
            "error": str(exc),
        }
        write_receipt(project_root, ticket_id, receipt)
        return receipt
