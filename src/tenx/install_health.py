"""Host tool-install health for dispatched subagents.

Worktree isolation covers the files a worker writes, not the host tool
environment it can reach. A worker that runs a package-manager install
re-points the operator's global tenx at the worktree, and teardown then
leaves the operator with a CLI that cannot start. Because a broken install
cannot report its own breakage, the check runs in the parent, against a
snapshot taken before the worker was launched (SPC-038).

Zero runtime dependencies (Python standard library only, CON-002).
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional



def tenx_source_path() -> Optional[str]:
    """Resolved path of the tenx package this process imported, or None."""
    spec = importlib.util.find_spec("tenx")
    if spec is None or not spec.origin:
        return None
    return spec.origin



def snapshot_host_install() -> dict[str, Any]:
    """Record what the host tenx install looked like, for later comparison."""
    return {"tenx_source": tenx_source_path(), "python": sys.executable}


def in_dispatch_worktree(source: Optional[str]) -> bool:
    """True when a resolved tenx path sits inside a dispatch worktree."""
    if not source:
        return False
    normalized = str(Path(source))
    return "/.tenx/worktrees/" in normalized or normalized.startswith(".tenx/worktrees/")


def recovery_instructions() -> str:
    """The command that restores a host tenx install, per the known story."""
    return ("  uv tool install --force git+https://github.com/sivakoneti/10xdev-cli.git\n"
            "  pipx install --force git+https://github.com/sivakoneti/10xdev-cli.git\n"
            "  (editable/local installs: `git pull` in the tenx source repo is enough)")


def check_host_install(snapshot: Optional[dict[str, Any]]) -> Optional[dict[str, str]]:
    """Report a host tenx install a dispatched worker damaged, or None.

    Two independent signals, because neither alone is sufficient. The
    snapshot comparison catches a source that moved, but only sees the
    interpreter this process runs in. Probing the installed command catches
    the real user-visible failure — `tenx` no longer starts — wherever that
    interpreter lives. A receipt written by an older tenx carries no snapshot
    and is treated as "nothing to compare" rather than as a failure.
    """
    return _snapshot_drift(snapshot) or probe_installed_cli()


def _snapshot_drift(snapshot: Optional[dict[str, Any]]) -> Optional[dict[str, str]]:
    """Compare the launch-time host install snapshot against the current one."""
    if not isinstance(snapshot, dict):
        return None
    recorded = snapshot.get("tenx_source")
    if not recorded:
        return None

    current = tenx_source_path()
    if current == recorded:
        return None
    if not Path(recorded).exists():
        return {
            "problem": f"the host tenx install pointed at {recorded}, which no longer exists",
            "cause": ("a dispatched worker installed from inside its worktree and the "
                      "worktree has since been removed"),
            "recovery": recovery_instructions(),
        }
    if current is None:
        return {
            "problem": "the host tenx package can no longer be imported",
            "cause": f"it resolved to {recorded} before teardown",
            "recovery": recovery_instructions(),
        }
    return {
        "problem": f"the host tenx install moved from {recorded} to {current}",
        "cause": "something reinstalled or re-pointed tenx during the dispatch",
        "recovery": recovery_instructions(),
    }


def probe_installed_cli(
    which: Optional[Callable[[str], Optional[str]]] = None,
    run: Optional[Callable[..., Any]] = None,
    timeout: int = 15,
) -> Optional[dict[str, str]]:
    """Report when the installed `tenx` command can no longer start.

    The snapshot comparison only sees the interpreter reconcile runs in; the
    damage a worker causes lands on whichever interpreter backs the globally
    installed CLI. The user-visible question — can the operator still run
    `tenx`? — has to be asked of that command directly.
    """
    which = which or shutil.which
    run = run or subprocess.run
    exe = which("tenx")
    if not exe:
        return None
    try:
        r = run([exe, "--version"], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    stderr = (getattr(r, "stderr", "") or "") + (getattr(r, "stdout", "") or "")
    if r.returncode == 0 and "No module named" not in stderr:
        return None
    detail = next((l.strip() for l in stderr.splitlines()
                   if "No module named" in l or l.strip().startswith("Error")), "")
    return {
        "problem": f"the installed `tenx` command no longer starts ({exe})",
        "cause": detail or f"`tenx --version` exited {r.returncode}",
        "recovery": recovery_instructions(),
    }
