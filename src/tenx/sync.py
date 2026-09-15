"""tenx sync — two-way sync between spec tickets and GitHub Issues.

Zero new dependencies (stdlib urllib). The token is only ever held in
memory: resolved from env or ~/.git-credentials, never written into
.tenx/ artifacts or the activity log.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API = os.environ.get("TENX_GITHUB_API", "https://api.github.com")
# TENX_GITHUB_API overrides the endpoint (GitHub Enterprise / tests).
MARKER_RE = re.compile(r"^\[(SPC-\d{3}-T\d+)\]")
LABEL_PREFIX = "tenx:"
BASE_LABEL = "tenx"


class SyncError(RuntimeError):
    pass


# ---------------------------------------------------------------- tokens

def _token_from_git_credentials() -> str | None:
    """Parse the github.com entry of ~/.git-credentials (git 'store')."""
    p = Path.home() / ".git-credentials"
    if not p.is_file():
        return None
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        line = line.strip()
        if not line or "github.com" not in line:
            continue
        try:
            u = urllib.parse.urlparse(line)
        except ValueError:
            continue
        tok = u.password or (u.username if u.scheme in ("http", "https")
                             and not u.password else None)
        if tok:
            return tok
    return None


def _token_from_gh_cli() -> str | None:
    """SPC-024 / QoL: try resolving auth token from `gh auth token` if gh is installed."""
    try:
        res = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        tok = res.stdout.strip()
        return tok if tok and res.returncode == 0 else None
    except Exception:
        return None


def resolve_token() -> str:
    tok = (os.environ.get("TENX_GITHUB_TOKEN")
           or os.environ.get("GITHUB_TOKEN")
           or os.environ.get("GH_TOKEN")
           or _token_from_git_credentials()
           or _token_from_gh_cli())
    if not tok:
        raise SyncError(
            "no GitHub token found. Set TENX_GITHUB_TOKEN, GITHUB_TOKEN, GH_TOKEN, "
            "store credentials in ~/.git-credentials, or log in via `gh auth login`.")
    return tok


# ------------------------------------------------------------------ repo

_SSH_RE = re.compile(r"^git@github\.com[:/]([^/]+)/(.+?)(?:\.git)?$")
_HTTPS_RE = re.compile(r"github\.com[:/]([^/]+)/(.+?)(?:\.git)?/?$")


def repo_from_remote_url(url: str) -> str | None:
    url = url.strip()
    for rx in (_SSH_RE, _HTTPS_RE):
        m = rx.search(url)
        if m:
            return f"{m.group(1)}/{m.group(2)}"
    return None


def resolve_repo(project_root: Path, config: dict[str, Any]) -> str:
    cfg_val = (config.get("github") or {}).get("repo") \
        if isinstance(config.get("github"), dict) else None
    if cfg_val is None:
        cfg_val = config.get("github_repo")
    if cfg_val:
        return str(cfg_val)
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=project_root, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        url = ""
    repo = repo_from_remote_url(url) if url else None
    if not repo:
        raise SyncError(
            "could not resolve the GitHub repo. Set `github_repo: "
            "owner/name` in .tenx/config.yaml or add an `origin` remote.")
    return repo


# ------------------------------------------------------------------ http

def _request(token: str, method: str, path: str,
             body: dict[str, Any] | None = None) -> tuple[int, Any]:
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "tenx-sync",
            "Content-Type": "application/json",
        })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            detail = json.loads(raw)
        except Exception:
            detail = {"raw": raw.decode("utf-8", "replace")[:300]}
        return e.code, detail
    except OSError as e:
        # URLError / socket.timeout / connection errors -> clean SyncError.
        reason = getattr(e, "reason", None) or e
        raise SyncError(f"network error calling {url}: {reason}") from e


def list_issues(token: str, repo: str) -> list[dict[str, Any]]:
    """All issues (state=all), paginated, marker issues only."""
    out: list[dict[str, Any]] = []
    page = 1
    while True:
        status, data = _request(
            token, "GET",
            f"/repos/{repo}/issues?state=all&per_page=100&page={page}")
        if status != 200 or not isinstance(data, list):
            raise SyncError(f"list issues failed ({status}): "
                            f"{str(data)[:200]}")
        for it in data:
            if it.get("pull_request"):
                continue
            title = str(it.get("title", ""))
            if MARKER_RE.match(title):
                out.append(it)
        if len(data) < 100:
            break
        page += 1
        if page > 20:  # safety cap: 2000 issues
            break
    return out


def ensure_labels(token: str, repo: str, names: list[str]) -> None:
    """Create missing labels (idempotent, 422 == already exists)."""
    colors = {"tenx": "1d76db", "tenx:todo": "cccccc",
              "tenx:in_progress": "fbca04", "tenx:in_review": "5319e7",
              "tenx:done": "0e8a16"}
    for n in names:
        status, _ = _request(token, "POST", f"/repos/{repo}/labels",
                             {"name": n, "color": colors.get(n, "ededed")})
        if status not in (201, 422):
            raise SyncError(f"label create {n} failed ({status})")


def create_issue(token: str, repo: str, title: str, body: str,
                 labels: list[str]) -> dict[str, Any]:
    status, data = _request(token, "POST", f"/repos/{repo}/issues",
                            {"title": title, "body": body,
                             "labels": labels})
    if status != 201:
        raise SyncError(f"issue create failed ({status}): "
                        f"{str(data)[:200]}")
    return data


def update_issue(token: str, repo: str, number: int,
                 patch: dict[str, Any]) -> dict[str, Any]:
    status, data = _request(token, "PATCH",
                            f"/repos/{repo}/issues/{number}", patch)
    if status != 200:
        raise SyncError(f"issue update #{number} failed ({status}): "
                        f"{str(data)[:200]}")
    return data


# ----------------------------------------------------------- orchestration

def _issue_body(spec_id: str, spec_title: str, ticket: dict[str, Any],
                spec_rel: str) -> str:
    return (
        f"tenx-status: {ticket.get('status', 'todo')}\n\n"
        f"Spec: {spec_id} — {spec_title}\n"
        f"Spec file: `{spec_rel}`\n\n"
        "_Managed by `tenx sync`. Edit ticket state with "
        "`tenx ticket`, then `tenx sync push`._"
    )


def _body_status(body: str) -> str | None:
    m = re.search(r"^tenx-status:\s*(\w+)", body or "", re.M)
    return m.group(1) if m else None


def plan_push(specs: list[Any], issues: list[dict[str, Any]],
              project_root: Path | None = None,
              ) -> list[dict[str, Any]]:
    """Compute actions: [{action: create|update|skip, spec, ticket, ...}]."""
    by_marker: dict[str, dict[str, Any]] = {}
    for it in issues:
        m = MARKER_RE.match(str(it.get("title", "")))
        if m:
            by_marker[m.group(1)] = it

    actions: list[dict[str, Any]] = []
    for spec in specs:
        spec_id = spec.id
        spec_rel = spec.rel(project_root) if project_root else ""
        for t in spec.tickets:
            tid = str(t.get("id", ""))
            if not tid:
                continue
            tstatus = str(t.get("status", "todo"))
            title = f"[{tid}] {t.get('title') or spec.title}"
            want_state = "closed" if tstatus == "done" else "open"
            want_labels = sorted([BASE_LABEL, f"{LABEL_PREFIX}{tstatus}"])
            existing = by_marker.get(tid)
            if existing is None:
                actions.append({
                    "action": "create", "spec": spec_id, "ticket": tid,
                    "title": title, "status": tstatus,
                    "state": want_state, "labels": want_labels,
                    "body": _issue_body(spec_id, spec.title, t, spec_rel),
                })
                continue
            have_labels = sorted(l.get("name", "")
                                 for l in existing.get("labels", []))
            have_status = _body_status(str(existing.get("body", "")))
            changes: dict[str, Any] = {}
            if existing.get("state") != want_state:
                changes["state"] = want_state
            if have_labels != want_labels:
                changes["labels"] = want_labels
            if have_status != tstatus:
                changes["body"] = _issue_body(spec_id, spec.title, t,
                                              spec_rel)
            if changes:
                actions.append({
                    "action": "update", "spec": spec_id, "ticket": tid,
                    "number": existing.get("number"),
                    "status": tstatus, "changes": changes,
                })
            else:
                actions.append({"action": "skip", "spec": spec_id,
                                "ticket": tid,
                                "number": existing.get("number")})
    return actions


def plan_pull(specs: list[Any], issues: list[dict[str, Any]]
              ) -> list[dict[str, Any]]:
    """Map issue state back to ticket status changes."""
    ticket_state: dict[str, tuple[str, str | None, int | None]] = {}
    for it in issues:
        m = MARKER_RE.match(str(it.get("title", "")))
        if not m:
            continue
        state = it.get("state", "open")
        body_status = _body_status(str(it.get("body", "")))
        ticket_state[m.group(1)] = (state, body_status, it.get("number"))

    actions: list[dict[str, Any]] = []
    for spec in specs:
        for t in spec.tickets:
            tid = str(t.get("id", ""))
            if tid not in ticket_state:
                continue
            state, body_status, number = ticket_state[tid]
            cur = str(t.get("status", "todo"))
            new = cur
            if state == "closed" and cur != "done":
                new = "done"
            elif state == "open" and body_status and body_status != cur \
                    and body_status in ("todo", "in_progress", "in_review"):
                new = body_status
            if new != cur:
                actions.append({"action": "set", "spec": spec.id,
                                "ticket": tid, "from": cur, "to": new,
                                "number": number})
    return actions
