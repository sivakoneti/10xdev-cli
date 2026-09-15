"""Subagent worktree reconciliation, verification, git merge, and teardown."""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional

from tenx.activity import append_entry
from tenx.artifacts import load_harness, update_meta, Artifact
from tenx.multiplexers import _herdr_send_rpc


@dataclass
class ReconcileResult:
    status: str  # "merged", "verified_failed", "conflict", "aborted", "error"
    ticket_id: str
    spec_id: Optional[str] = None
    branch: Optional[str] = None
    worktree_path: Optional[str] = None
    verification_output: Optional[str] = None
    error: Optional[str] = None
    closed_workspaces: Optional[List[str]] = None


def _find_ticket_and_spec(project_root: Path, ticket_id: str) -> tuple[Optional[Artifact], Optional[Dict[str, Any]]]:
    """Find the spec and ticket dictionary matching ticket_id."""
    harness = load_harness(Path(project_root))
    for art in harness.artifacts:
        if art.type == "spec":
            for t in art.tickets:
                if t.get("id") == ticket_id:
                    return art, t
    return None, None


def _close_associated_herdr_workspaces(project_root: Path, ticket_id: str) -> List[str]:
    """Identify and close Herdr workspaces associated with this ticket worktree."""
    closed = []
    sock_path = os.environ.get("HERDR_SOCKET_PATH") or str(Path.home() / ".config" / "herdr" / "herdr.sock")
    if not os.path.exists(sock_path):
        return closed

    # List workspaces
    res = _herdr_send_rpc(sock_path, "workspace.list", {})
    if not res or "result" not in res:
        return closed

    workspaces = res["result"].get("workspaces", [])
    expected_wt = str(project_root / ".tenx" / "worktrees" / ticket_id)

    for ws in workspaces:
        ws_id = ws.get("workspace_id")
        label = ws.get("label", "")
        # Check label matching ticket_id or checkout_path matching worktree
        wt_info = ws.get("worktree", {})
        checkout = wt_info.get("checkout_path", "") if isinstance(wt_info, dict) else ""

        if ticket_id in label or (checkout and checkout == expected_wt):
            _herdr_send_rpc(sock_path, "workspace.close", {"workspace_id": ws_id})
            closed.append(ws_id)

    return closed


def _close_associated_tmux_windows(ticket_id: str) -> List[str]:
    """Close any tmux window matching ticket_id."""
    closed = []
    try:
        res = subprocess.run(["tmux", "list-windows", "-F", "#{window_id}:#{window_name}"], capture_output=True, text=True)
        if res.returncode == 0:
            for line in res.stdout.strip().splitlines():
                if ":" in line:
                    wid, wname = line.split(":", 1)
                    if ticket_id in wname:
                        subprocess.run(["tmux", "kill-window", "-t", wid], capture_output=True, text=True)
                        closed.append(wid)
    except Exception:
        pass
    return closed


def verify_subagent_worktree(worktree_dir: Path) -> tuple[bool, str]:
    """Run pre-landing verification inside the subagent worktree."""
    if not worktree_dir.exists():
        return False, f"Worktree directory {worktree_dir} does not exist"

    # Run tenx validate inside worktree
    env = os.environ.copy()
    env["PYTHONPATH"] = str(worktree_dir / "src")

    val_proc = subprocess.run(
        ["python3", "-m", "tenx.cli", "validate"],
        cwd=str(worktree_dir),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    if val_proc.returncode != 0:
        return False, f"tenx validate failed:\n{val_proc.stderr or val_proc.stdout}"

    # Check for tests/smoke_test.py or tests/
    smoke_script = worktree_dir / "tests" / "smoke_test.py"
    if smoke_script.exists():
        test_proc = subprocess.run(
            ["python3", str(smoke_script)],
            cwd=str(worktree_dir),
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )
        if test_proc.returncode != 0:
            return False, f"Tests failed:\n{test_proc.stderr or test_proc.stdout}"

    return True, "Pre-landing verification passed (tenx validate + tests clean)"


def reconcile_subagent_ticket(
    project_root: Path,
    ticket_id: str,
    skip_verify: bool = False,
) -> ReconcileResult:
    """Verify, merge, update ticket, and teardown subagent worktree."""
    wt_dir = project_root / ".tenx" / "worktrees" / ticket_id
    branch_name = f"tenx/{ticket_id}"

    # 1. Locate worktree
    if not wt_dir.exists():
        return ReconcileResult(
            status="error",
            ticket_id=ticket_id,
            error=f"No active worktree found for {ticket_id} at {wt_dir}",
        )

    # 2. Pre-landing verification
    if not skip_verify:
        passed, msg = verify_subagent_worktree(wt_dir)
        if not passed:
            return ReconcileResult(
                status="verified_failed",
                ticket_id=ticket_id,
                worktree_path=str(wt_dir),
                branch=branch_name,
                verification_output=msg,
                error="Pre-landing verification failed. Worktree preserved for inspection.",
            )

    # 3. Check current branch in parent project
    res_cur = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(project_root), capture_output=True, text=True)
    parent_branch = res_cur.stdout.strip()
    if not parent_branch or parent_branch == branch_name:
        return ReconcileResult(
            status="error",
            ticket_id=ticket_id,
            error=f"Cannot merge into current branch '{parent_branch}'",
        )

    # 4. Merge subagent branch into parent
    merge_proc = subprocess.run(
        ["git", "merge", branch_name, "-m", f"feat: merge subagent work for {ticket_id}"],
        cwd=str(project_root),
        capture_output=True,
        text=True,
    )
    if merge_proc.returncode != 0:
        return ReconcileResult(
            status="conflict",
            ticket_id=ticket_id,
            worktree_path=str(wt_dir),
            branch=branch_name,
            error=f"Merge conflict or failure:\n{merge_proc.stderr or merge_proc.stdout}",
        )

    # 5. Teardown multiplexer sessions
    closed_ws = _close_associated_herdr_workspaces(project_root, ticket_id)
    closed_tmux = _close_associated_tmux_windows(ticket_id)
    all_closed = closed_ws + closed_tmux

    # 6. Teardown git worktree and branch
    subprocess.run(["git", "worktree", "remove", "--force", str(wt_dir)], cwd=str(project_root), capture_output=True, text=True)
    subprocess.run(["git", "branch", "-D", branch_name], cwd=str(project_root), capture_output=True, text=True)

    # 7. Update ticket in spec to done
    spec, ticket_dict = _find_ticket_and_spec(project_root, ticket_id)
    spec_id = spec.id if spec else None
    if spec and ticket_dict:
        ticket_dict["status"] = "done"
        update_meta(spec, {"tickets": spec.tickets})

    # 8. Write back activity log evidence
    append_entry(
        project_root,
        f"Reconciled and merged subagent worktree for {ticket_id} into {parent_branch}",
        entry_type="progress",
        ref=ticket_id,
    )

    return ReconcileResult(
        status="merged",
        ticket_id=ticket_id,
        spec_id=spec_id,
        branch=branch_name,
        worktree_path=str(wt_dir),
        verification_output="Clean verification and merge",
        closed_workspaces=all_closed,
    )


def abort_subagent_ticket(
    project_root: Path,
    ticket_id: str,
) -> ReconcileResult:
    """Cleanly discard and teardown subagent worktree, branch, and multiplexer sessions."""
    wt_dir = project_root / ".tenx" / "worktrees" / ticket_id
    branch_name = f"tenx/{ticket_id}"

    # Teardown multiplexer sessions
    closed_ws = _close_associated_herdr_workspaces(project_root, ticket_id)
    closed_tmux = _close_associated_tmux_windows(ticket_id)
    all_closed = closed_ws + closed_tmux

    # Remove worktree if present
    if wt_dir.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(wt_dir)], cwd=str(project_root), capture_output=True, text=True)

    # Remove branch if present
    subprocess.run(["git", "branch", "-D", branch_name], cwd=str(project_root), capture_output=True, text=True)

    # Log abortion
    append_entry(
        project_root,
        f"Aborted and discarded subagent worktree for {ticket_id}",
        entry_type="progress",
        ref=ticket_id,
    )

    return ReconcileResult(
        status="aborted",
        ticket_id=ticket_id,
        branch=branch_name,
        worktree_path=str(wt_dir),
        closed_workspaces=all_closed,
    )
