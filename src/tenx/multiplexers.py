"""Multiplexer detection and projection for subagent execution.

Supports visual task projection for:
- Herdr (workspace create --cwd <dir> --label <ticket> [--no-focus])
- tmux (new-window -c <dir> -n <ticket> <cmd>)

Strictly zero-runtime-dependencies (CON-002).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class MultiplexerTarget:
    name: str  # "herdr", "tmux", "none"
    session: Optional[str] = None
    is_active: bool = False
    details: str = ""


def detect_multiplexer(preference: str = "auto") -> MultiplexerTarget:
    """Detect active terminal multiplexer or resolve user preference.

    Supported preferences:
    - "auto": Checks environment for Herdr, then tmux.
    - "herdr": Forces Herdr adapter.
    - "tmux": Forces tmux adapter.
    - "none": Disables multiplexer projection.
    """
    pref = (preference or "auto").lower().strip()
    if pref == "none":
        return MultiplexerTarget(name="none", details="multiplexer projection disabled")

    # Check Herdr
    herdr_env = os.environ.get("HERDR_ENV") == "1"
    herdr_session = os.environ.get("HERDR_SESSION")
    herdr_bin = shutil.which("herdr")

    if pref == "herdr":
        return MultiplexerTarget(
            name="herdr",
            session=herdr_session or "default",
            is_active=bool(herdr_bin),
            details=f"herdr binary {'found' if herdr_bin else 'not found'}"
        )

    # Check tmux
    tmux_env = os.environ.get("TMUX")
    tmux_bin = shutil.which("tmux")

    if pref == "tmux":
        return MultiplexerTarget(
            name="tmux",
            session=tmux_env,
            is_active=bool(tmux_bin),
            details=f"tmux binary {'found' if tmux_bin else 'not found'}"
        )

    # Auto detection: prefer Herdr if in Herdr, else tmux if in tmux
    if (herdr_env or herdr_session) and herdr_bin:
        return MultiplexerTarget(
            name="herdr",
            session=herdr_session or "default",
            is_active=True,
            details=f"active Herdr environment (session: {herdr_session or 'default'})"
        )

    if tmux_env and tmux_bin:
        return MultiplexerTarget(
            name="tmux",
            session=tmux_env,
            is_active=True,
            details="active tmux session"
        )

    # Fallback to available binaries if active
    if herdr_bin:
        # Check if herdr server is running
        try:
            res = subprocess.run(["herdr", "status"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and "status: running" in res.stdout:
                return MultiplexerTarget(
                    name="herdr",
                    session="default",
                    is_active=True,
                    details="running Herdr server detected"
                )
        except Exception:
            pass

    return MultiplexerTarget(name="none", details="no active terminal multiplexer detected")


@dataclass(frozen=True)
class ProjectionPlan:
    multiplexer: str
    create_cmd: list[str]
    run_cmd: list[str]
    summary: str


def plan_visual_projection(
    mux: MultiplexerTarget,
    ticket_id: str,
    worktree_dir: Path,
    agent_cmd: list[str],
    focus: bool = False,
) -> Optional[ProjectionPlan]:
    """Build projection commands for the given multiplexer."""
    if mux.name == "none":
        return None

    if mux.name == "herdr":
        # herdr workspace create --cwd <dir> --label <ticket> [--no-focus]
        create_args = [
            "herdr", "workspace", "create",
            "--cwd", str(worktree_dir),
            "--label", ticket_id,
        ]
        if not focus:
            create_args.append("--no-focus")

        # In Herdr, we can start the agent in the new workspace using herdr pane run or direct launch
        # We can construct the agent command string
        agent_cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in agent_cmd)
        run_args = ["herdr", "pane", "run", agent_cmd_str]

        return ProjectionPlan(
            multiplexer="herdr",
            create_cmd=create_args,
            run_cmd=run_args,
            summary=f"Herdr visual workspace '{ticket_id}' (cwd: {worktree_dir})"
        )

    elif mux.name == "tmux":
        agent_cmd_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in agent_cmd)
        create_args = [
            "tmux", "new-window",
            "-c", str(worktree_dir),
            "-n", ticket_id,
        ]
        if not focus:
            create_args.append("-d")
        create_args.append(agent_cmd_str)

        return ProjectionPlan(
            multiplexer="tmux",
            create_cmd=create_args,
            run_cmd=[],
            summary=f"tmux visual window '{ticket_id}' (cwd: {worktree_dir})"
        )

    return None
