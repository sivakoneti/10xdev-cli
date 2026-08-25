"""tenx.gate - enforced landing policy (the evidence gate).

The landing discipline (SPC-014) teaches "evidence before done". This module
makes it *policy*: transitioning a spec or epic to `complete` is blocked unless

  1. validation has no errors attributed to the artifact,
  2. for a spec, every ticket is `done`, and
  3. evidence is linked - an `evidence:` frontmatter field OR a substantive
     activity-log entry referencing the artifact.

A human can override with `--force` on `tenx set`, or disable the gate
per-project via `evidence_gate: off` in `.tenx/config.yaml`.

The gate checks *presence* of evidence, not its truth. It never mutates state.
"""
from __future__ import annotations

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

    return (not reasons, reasons)
