"""Multiplexer detection and projection for subagent execution.

Supports visual task projection for:
- Herdr (workspace create --cwd <dir> --label <ticket> [--no-focus], with hierarchical sidenav positioning)
- tmux (new-window -c <dir> -n <ticket> <cmd>)

Strictly zero-runtime-dependencies (CON-002).
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class MultiplexerTarget:
    name: str  # "herdr", "tmux", "none"
    session: Optional[str] = None
    is_active: bool = False
    details: str = ""


def _herdr_send_rpc(socket_path: str, method: str, params: dict[str, Any], req_id: str = "tenx-rpc") -> Optional[dict[str, Any]]:
    """Send a single JSON-RPC request to Herdr Unix socket and return parsed response."""
    if not socket_path or not os.path.exists(socket_path):
        return None
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(3.0)
        sock.connect(socket_path)
        payload = json.dumps({"id": req_id, "method": method, "params": params}) + "\n"
        sock.sendall(payload.encode("utf-8"))
        raw = b""
        while b"\n" not in raw:
            chunk = sock.recv(65536)
            if not chunk:
                break
            raw += chunk
        sock.close()
        line = raw.decode("utf-8", "replace").split("\n")[0].strip()
        if not line:
            return None
        return json.loads(line)
    except Exception:
        return None


def position_herdr_workspace_below_parent(
    socket_path: str,
    child_workspace_id: str,
    parent_workspace_id: Optional[str] = None,
) -> bool:
    """Reposition newly created child workspace directly below parent in Herdr left sidebar.

    Uses protocol-16 `workspace.move` to keep subagent workspaces visually grouped
    under the active project instead of appending to the bottom of the list.
    """
    if not socket_path or not child_workspace_id:
        return False

    # 1. Query current workspace list
    res_list = _herdr_send_rpc(socket_path, "workspace.list", {})
    if not res_list or not isinstance(res_list.get("result"), dict):
        return False

    workspaces = res_list["result"].get("workspaces", [])
    if not workspaces or not isinstance(workspaces, list):
        return False

    # 2. Identify parent workspace index
    parent_id = parent_workspace_id or os.environ.get("HERDR_WORKSPACE_ID")
    parent_index = -1
    for idx, ws in enumerate(workspaces):
        # Match by parent_id if known, otherwise look for currently focused workspace
        if parent_id and ws.get("workspace_id") == parent_id:
            parent_index = idx
            break
        elif not parent_id and ws.get("focused"):
            parent_index = idx
            break

    if parent_index < 0:
        return False

    # Desired index is immediately after the parent
    desired_index = parent_index + 1

    # 3. Call workspace.move
    res_move = _herdr_send_rpc(
        socket_path,
        "workspace.move",
        {"workspace_id": child_workspace_id, "insert_index": desired_index},
    )
    if res_move and res_move.get("result", {}).get("type") == "workspace_list":
        return True
    return False


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
    socket_path: Optional[str] = None,
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
