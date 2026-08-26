"""tenx.gate - enforced landing policy (the evidence gate).

The landing discipline (SPC-014) teaches "evidence before done". This module
makes it *policy*: transitioning a spec or epic to `complete` is blocked unless

  1. validation has no errors attributed to the artifact,
  2. for a spec, every ticket is `done`,
  3. evidence is linked - an `evidence:` frontmatter field OR a substantive
     activity-log entry referencing the artifact, and
  4. docs-sync: a CHANGELOG.md entry references the artifact (so shipped work
     is documented). Skipped when the project has no CHANGELOG.md.

A human can override with `--force` on `tenx set`, or disable the gate
per-project via `evidence_gate: off` in `.tenx/config.yaml`.

The gate checks *presence* of evidence, not its truth. It never mutates state.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from . import activity
from .artifacts import Artifact, Harness

# Activity entry types that count as "someone logged real work/decision".
# `session` (auto-logged) and `blocker` (means blocked, not done) do not count.
EVIDENCE_LOG_TYPES = ("progress", "review", "decision", "note")

GATE_CONFIG_KEY = "evidence_gate"


def gate_enabled(harness: Harness) -> bool:
    """Default on; `evidence_gate: off` in config.yaml disables it."""
    val = str(harness.config.get(GATE_CONFIG_KEY, "on")).strip().lower()
    return val != "off"


def _has_evidence_field(art: Artifact) -> bool:
    return bool(str(art.meta.get("evidence") or "").strip())


def _has_evidence_log(project_root: Path, artifact_id: str) -> bool:
    want = (artifact_id or "").upper()
    if not want:
        return False
    for e in activity.read_entries(project_root):
        if str(e.get("ref", "") or "").upper() != want:
            continue
        if str(e.get("type", "") or "") in EVIDENCE_LOG_TYPES:
            return True
    return False


def _has_changelog_entry(project_root: Path,
                         wanted_ids: list[str]) -> bool | None:
    """Docs-sync evidence. Returns True if ANY changelog section
    ([Unreleased] or a released version) references one of `wanted_ids`,
    False if a changelog exists but none does, or None if the project has
    no CHANGELOG.md (skip the requirement).

    SPC-023-T14: released sections count too — work documented before a
    release must not fail the gate when the artifact is completed after
    the version shipped.

    For a spec the wanted id is just the spec; for an epic it is the epic
    plus its specs, so aggregate work documented via its specs counts."""
    from . import changelog as cl
    p = cl.changelog_path(project_root)
    if not p.is_file():
        return None
    wants = {w.upper() for w in wanted_ids if w}
    if not wants:
        return False
    try:
        _pre, sections = cl.parse_changelog(p.read_text(encoding="utf-8"))
    except OSError:
        return None
    for s in sections:
        for msgs in s.entries.values():
            for m in msgs:
                up = m.upper()
                if any(w in up for w in wants):
                    return True
    return False


def check_evidence_gate(project_root: Path, harness: Harness, art: Artifact,
                        ruleset: Any) -> tuple[bool, list[str]]:
    """Return (ok, reasons). Call only on a spec/epic -> complete transition.

    `ruleset` is a rules.RuleSet (already computed) so the gate reuses the
    caller's validation pass instead of re-running it.
    """
    reasons: list[str] = []

    # 1. no validation errors attributed to this artifact
    errs = [f for f in ruleset.errors() if (f.artifact_id or "") == art.id]
    if errs:
        reasons.append(
            f"{len(errs)} validation error(s) on {art.id} - fix first "
            f"(run `tenx validate`): {errs[0].message}")

    # 2. spec: every ticket must be done
    if art.type == "spec":
        tix = art.tickets
        open_tix = [t for t in tix if str(t.get("status", "todo")) != "done"]
        if tix and open_tix:
            ids = ", ".join(str(t.get("id", "?")) for t in open_tix[:5])
            more = f" (+{len(open_tix) - 5} more)" if len(open_tix) > 5 else ""
            reasons.append(
                f"{len(open_tix)} ticket(s) not done: {ids}{more}")

    # 3. evidence linked
    if not _has_evidence_field(art) and not _has_evidence_log(project_root, art.id):
        reasons.append(
            f"no evidence linked - log work with "
            f"`tenx log ... --ref {art.id}`, or attach it with "
            f"`tenx set {art.id} evidence <link/command>`, or re-run with "
            f"--force (human override)")

    # 4. docs-sync: shipped work must be noted in the changelog. An epic is
    #    satisfied by an entry referencing it or any of its specs.
    wanted = [art.id]
    if art.type == "epic":
        wanted += [s.id for s in harness.specs_for_epic(art.id)]
    cl_state = _has_changelog_entry(project_root, wanted)
    if cl_state is False:
        reasons.append(
            f"no changelog entry for {art.id} - document the shipped work "
            f"with `tenx changelog add \"...\" --ref {art.id}`, or re-run "
            f"with --force (human override)")

    return (not reasons, reasons)


# ── SPC-023-T4: staged-change freshness gate (pre-commit seam) ────────────
# The evidence gate polices spec/epic completion; this gate polices the
# COMMIT itself: code going into the index must have write-back behind it.

COMMIT_GATE_CONFIG_KEY = "commit_gate"
COMMIT_GATE_MODES = ("on", "warn", "off")


def commit_gate_mode(harness: Harness) -> str:
    """`commit_gate: on|warn|off` in config.yaml; default `warn`."""
    val = str(harness.config.get(COMMIT_GATE_CONFIG_KEY, "warn")
              ).strip().lower()
    return val if val in COMMIT_GATE_MODES else "warn"


def commit_check(project_root: Path,
                 harness: Harness) -> tuple[bool, str]:
    """Check staged changes against the activity log.

    Returns (ok, message). Fails when the index contains code files (not
    just .tenx/ process files) but no work entry was logged since the
    previous commit. Fail-open: any git problem returns ok — this check
    must never break a commit on a machine without git.
    """
    import subprocess

    from .discovery import code_root as _code_root
    from .rules import _is_code_path

    try:
        cr = _code_root(project_root, harness.config)
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], cwd=cr,
            capture_output=True, text=True, timeout=15)
        if staged.returncode != 0:
            return True, ""
        code_files = [l.strip() for l in staged.stdout.splitlines()
                      if _is_code_path(l)]
        if not code_files:
            return True, ""  # process-only commit: it IS the write-back
        prev = subprocess.run(
            ["git", "log", "-1", "--pretty=%aI", "HEAD"], cwd=cr,
            capture_output=True, text=True, timeout=15)
        prev_ts = None
        if prev.returncode == 0 and prev.stdout.strip():
            try:
                prev_ts = dt.datetime.fromisoformat(prev.stdout.strip())
                if prev_ts.tzinfo is None:
                    prev_ts = prev_ts.replace(tzinfo=dt.timezone.utc)
            except ValueError:
                prev_ts = None
        for e in reversed(activity.read_entries(project_root)):
            if str(e.get("type", "")) not in ("progress", "review",
                                              "decision", "note"):
                continue
            try:
                ets = dt.datetime.fromisoformat(str(e.get("ts", "")))
            except ValueError:
                continue
            if ets.tzinfo is None:
                ets = ets.replace(tzinfo=dt.timezone.utc)
            if prev_ts is None or ets >= prev_ts:
                return True, ""  # found write-back newer than last commit
        shown = ", ".join(code_files[:3]) + (
            f" (+{len(code_files) - 3} more)" if len(code_files) > 3 else "")
        return False, (
            f"staged code files ({shown}) but no activity-log entry since "
            "the last commit — write back first: "
            "`tenx log \"what changed\" --ref <ID>` "
            "(or set commit_gate: off in .tenx/config.yaml to disable)")
    except (OSError, subprocess.SubprocessError):
        return True, ""
