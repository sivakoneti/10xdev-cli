"""tenx self-update: check for and apply CLI updates.

tenx is installed per-user as a standalone CLI (`uv tool install` /
`pipx install`), so existing installs do not pick up new features on
their own. This module lets any install check the upstream repo for a
newer version and upgrade in place.

Version source chain:
1. GitHub Releases API (latest published release tag) — the official
   channel once releases are cut.
2. Fallback: `pyproject.toml` on the default branch via
   raw.githubusercontent.com, so the check already works against master
   before any formal release is published.

Design rules:
- `check_update` never raises for network problems; it returns a result
  dict with `status == "check-failed"` so callers (agents at session
  start) are never blocked or crashed by being offline.
- The upgrade path detects the installer (uv / pipx) and runs the
  matching upgrade command; if it cannot detect one it prints manual
  instructions instead of guessing.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from typing import Any

DEFAULT_REPO = os.environ.get("TENX_UPDATE_REPO", "sivakoneti/10xdev-cli")
DEFAULT_BRANCH = os.environ.get("TENX_UPDATE_BRANCH", "main")
TIMEOUT = 10


class UpdateError(Exception):
    """Fatal problem with an upgrade attempt (never raised by checks)."""


def _repo() -> str:
    """Return the tenx distribution repository, never the caller's repo."""
    return os.environ.get("TENX_UPDATE_REPO") or DEFAULT_REPO


def _branch() -> str:
    return os.environ.get("TENX_UPDATE_BRANCH", DEFAULT_BRANCH)


def _github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "tenx-cli"}
    # Same token chain as `tenx sync` (env vars, then ~/.git-credentials):
    # the upstream repo may be private, and installs on machines that
    # already sync have credentials there.
    token = os.environ.get("GH_TOKEN")
    if not token:
        try:
            from .sync import resolve_token
            token = resolve_token()
        except Exception:
            token = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def parse_version(tag: str) -> tuple[int, ...]:
    """'v0.11.0' -> (0, 11, 0); tolerant of prefixes/suffixes."""
    v = str(tag).strip().lstrip("vV")
    parts: list[int] = []
    for p in re.split(r"[.\-+]", v):
        if p.isdigit():
            parts.append(int(p))
        else:
            break
    return tuple(parts) or (0,)


def _fetch_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=_github_headers())
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers=_github_headers())
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8")


def _latest_from_releases() -> tuple[str, str] | None:
    """(version, release_url) or None if the repo has no releases."""
    url = f"https://api.github.com/repos/{_repo()}/releases/latest"
    try:
        data = _fetch_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    tag = data.get("tag_name") or ""
    if not tag:
        return None
    return tag.lstrip("vV"), data.get("html_url", "")


def _latest_from_branch() -> tuple[str, str] | None:
    """(version, file_url) parsed from pyproject.toml on the branch."""
    url = (f"https://raw.githubusercontent.com/{_repo()}/{_branch()}"
           f"/pyproject.toml")
    text = _fetch_text(url)
    m = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']',
                  text, re.MULTILINE)
    if not m:
        return None
    return m.group(1), url


def fetch_latest_version() -> dict[str, Any]:
    """Resolve the latest upstream version.

    Returns {version, source, url}; raises on hard network failure
    (check_update converts that to a check-failed result).
    """
    rel = _latest_from_releases()
    if rel:
        return {"version": rel[0], "source": "release", "url": rel[1]}
    br = _latest_from_branch()
    if br:
        return {"version": br[0], "source": f"branch:{_branch()}",
                "url": br[1]}
    raise UpdateError(f"no release and no parseable pyproject.toml found "
                      f"for {_repo()}")


def check_update(current_version: str) -> dict[str, Any]:
    """Non-fatal update check. Always returns a dict, never raises.

    status: up-to-date | update-available | check-failed
    """
    result: dict[str, Any] = {
        "current": current_version,
        "latest": None,
        "source": None,
        "url": None,
        "update_available": False,
        "status": "check-failed",
        "note": "",
    }
    try:
        latest = fetch_latest_version()
    except UpdateError as exc:
        result["note"] = str(exc)
        return result
    except Exception as exc:  # URLError, HTTPError, timeout, JSON, ...
        result["note"] = (f"could not check for updates "
                          f"({type(exc).__name__}: {exc}) — offline?")
        return result
    result.update({"latest": latest["version"], "source": latest["source"],
                   "url": latest["url"]})
    newer = parse_version(latest["version"]) > parse_version(current_version)
    result["update_available"] = newer
    result["status"] = "update-available" if newer else "up-to-date"
    return result


def detect_installer() -> str | None:
    """'uv' | 'pipx' | None — whichever tool manages the tenx install."""
    if shutil.which("uv"):
        try:
            r = subprocess.run(["uv", "tool", "list"], capture_output=True,
                               text=True, timeout=15)
            if re.search(r"(?m)^tenx\b|\btenx\s+v?\d", r.stdout):
                return "uv"
        except (subprocess.TimeoutExpired, OSError):
            pass
    if shutil.which("pipx"):
        try:
            r = subprocess.run(["pipx", "list", "--short"],
                               capture_output=True, text=True, timeout=15)
            if "tenx" in r.stdout:
                return "pipx"
        except (subprocess.TimeoutExpired, OSError):
            pass
    return None


def upgrade_command(installer: str) -> list[str]:
    if installer == "uv":
        return ["uv", "tool", "upgrade", "tenx"]
    return ["pipx", "upgrade", "tenx"]


def manual_instructions() -> str:
    git_url = f"git+https://github.com/{_repo()}.git"
    return ("Could not detect how tenx was installed. Upgrade manually:\n"
            f"  uv tool install --force {git_url}     # if installed via uv\n"
            f"  pipx install --force {git_url}        # if installed via pipx\n"
            "  (editable/local installs: `git pull` in the tenx source repo "
            "is enough)")


def run_update(current_version: str, check_only: bool = False,
               as_json: bool = False) -> int:
    """`tenx update` entry point. Returns the process exit code."""
    info = check_update(current_version)

    if as_json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
        if check_only or info["status"] != "update-available":
            return 0
        # JSON + upgrade requested: fall through and upgrade.

    if info["status"] == "check-failed":
        print(f"tenx v{current_version}: {info['note']}")
        return 0

    if not info["update_available"]:
        print(f"tenx v{current_version}: up to date "
              f"(latest {info['latest']} via {info['source']}).")
        return 0

    print(f"tenx v{current_version}: update available -> v{info['latest']} "
          f"(via {info['source']})")
    if info.get("url"):
        print(f"  {info['url']}")
    if check_only:
        print("Run `tenx update` to install it.")
        return 0

    installer = detect_installer()
    if installer is None:
        print(manual_instructions())
        return 1
    cmd = upgrade_command(installer)
    print(f"Upgrading via {installer}: {' '.join(cmd)}")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f"Upgrade exited {r.returncode}. Try manually:\n"
              + manual_instructions())
        return r.returncode
    print(f"Done. Run `tenx --version` to confirm v{info['latest']}.")
    return 0
