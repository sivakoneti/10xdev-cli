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
from tenx.subagent_state import clear_receipt, read_receipt


@dataclass
class ReconcileResult:
    status: str  # merged, verified_failed, conflict, dirty_worktree, teardown_failed, aborted, error
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


def _close_herdr_workspace(workspace_id: str) -> tuple[List[str], List[str]]:
    sock_path = os.environ.get("HERDR_SOCKET_PATH") or str(Path.home() / ".config" / "herdr" / "herdr.sock")
    if not os.path.exists(sock_path):
        return [], [f"Herdr socket unavailable: {sock_path}"]
    response = _herdr_send_rpc(sock_path, "workspace.close", {"workspace_id": workspace_id})
    if not response or response.get("error"):
        detail = (response or {}).get("error", "workspace.close returned no response")
        return [], [f"{workspace_id}: {detail}"]
    return [workspace_id], []


def _close_tmux_window(window_id: str) -> tuple[List[str], List[str]]:
    proc = subprocess.run(
        ["tmux", "kill-window", "-t", window_id],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return [], [f"{window_id}: {proc.stderr.strip() or proc.stdout.strip()}"]
    return [window_id], []


def _close_dispatch_resources(project_root: Path, ticket_id: str) -> tuple[List[str], List[str]]:
    receipt = read_receipt(project_root, ticket_id)
    closed: List[str] = []
    errors: List[str] = []
    if receipt.get("multiplexer") == "herdr" and receipt.get("workspace_id"):
        ids, failures = _close_herdr_workspace(str(receipt["workspace_id"]))
        closed.extend(ids)
        errors.extend(failures)
    if receipt.get("multiplexer") == "tmux" and receipt.get("window_id"):
        ids, failures = _close_tmux_window(str(receipt["window_id"]))
        closed.extend(ids)
        errors.extend(failures)
    return closed, errors


def _worktree_is_dirty(worktree_dir: Path) -> tuple[bool, str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(worktree_dir),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return True, proc.stderr.strip() or proc.stdout.strip() or "git status failed"
    return bool(proc.stdout.strip()), proc.stdout.strip()


def _remove_worktree_and_branch(project_root: Path, worktree_dir: Path, branch_name: str, force: bool = False) -> List[str]:
    errors: List[str] = []
    if worktree_dir.exists():
        remove_cmd = ["git", "worktree", "remove"]
        if force:
            remove_cmd.append("--force")
        remove_cmd.append(str(worktree_dir))
        removed = subprocess.run(
            remove_cmd,
            cwd=str(project_root), capture_output=True, text=True,
        )
        if removed.returncode != 0:
            errors.append(f"worktree remove failed: {removed.stderr.strip() or removed.stdout.strip()}")
    branch = subprocess.run(
        ["git", "branch", "--list", branch_name],
        cwd=str(project_root), capture_output=True, text=True,
    )
    if branch.returncode == 0 and branch.stdout.strip():
        deleted = subprocess.run(
            ["git", "branch", "-D", branch_name],
            cwd=str(project_root), capture_output=True, text=True,
        )
        if deleted.returncode != 0:
            errors.append(f"branch delete failed: {deleted.stderr.strip() or deleted.stdout.strip()}")
    if worktree_dir.exists():
        errors.append(f"worktree still exists: {worktree_dir}")
    return errors


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

    dirty, dirty_output = _worktree_is_dirty(wt_dir)
    if dirty:
        return ReconcileResult(
            status="dirty_worktree",
            ticket_id=ticket_id,
            worktree_path=str(wt_dir),
            branch=branch_name,
            verification_output=dirty_output,
            error="Subagent worktree has uncommitted changes. Commit, inspect, or abort it before reconcile; worktree preserved.",
        )

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

    teardown_errors: List[str] = []
    closed_ws, close_errors = _close_dispatch_resources(project_root, ticket_id)
    teardown_errors.extend(close_errors)
    teardown_errors.extend(_remove_worktree_and_branch(project_root, wt_dir, branch_name))
    if teardown_errors:
        return ReconcileResult(
            status="teardown_failed",
            ticket_id=ticket_id,
            branch=branch_name,
            worktree_path=str(wt_dir),
            error="Merge succeeded, but teardown was incomplete: " + "; ".join(teardown_errors),
            closed_workspaces=closed_ws,
        )
    clear_receipt(project_root, ticket_id)

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
        closed_workspaces=closed_ws,
    )


def abort_subagent_ticket(
    project_root: Path,
    ticket_id: str,
) -> ReconcileResult:
    """Cleanly discard and teardown subagent worktree, branch, and multiplexer sessions."""
    wt_dir = project_root / ".tenx" / "worktrees" / ticket_id
    branch_name = f"tenx/{ticket_id}"

    teardown_errors: List[str] = []
    closed_ws, close_errors = _close_dispatch_resources(project_root, ticket_id)
    teardown_errors.extend(close_errors)
    teardown_errors.extend(_remove_worktree_and_branch(project_root, wt_dir, branch_name, force=True))
    if teardown_errors:
        return ReconcileResult(
            status="teardown_failed",
            ticket_id=ticket_id,
            branch=branch_name,
            worktree_path=str(wt_dir),
            error="Abort teardown was incomplete: " + "; ".join(teardown_errors),
            closed_workspaces=closed_ws,
        )
    clear_receipt(project_root, ticket_id)

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
        closed_workspaces=closed_ws,
    )
