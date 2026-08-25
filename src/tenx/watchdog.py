"""`tenx watchdog` — a pulse-check digest of what needs attention.

Modeled on the "Watchdog" playbook used by solo founders running fleets
of agents: instead of dumping raw state, it scans the whole harness and
surfaces the TOP few problems, each cross-referenced with recent activity
to answer the question that actually matters: *is this being handled?*

Signals, in order of severity:

- critical : validation errors (the harness itself is broken)
- high     : blocked specs/tickets, unresolved blocker log entries, drift
- medium   : specs waiting in_review, in_progress work that has gone quiet

For every item watchdog reports a handling verdict:
- being worked on  (recent activity references it)
- unattended       (no recent activity — needs an owner or a decision)
- waiting on review/fix

Pure read: watchdog never mutates the harness.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

from .activity import read_entries
from .artifacts import Harness, effective_priority, load_harness
from .rules import RuleSet, validate

# How far back counts as "recent" when deciding if work is being handled.
RECENT_DAYS = 7

SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _parse_ts(ts: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromisoformat(str(ts))
    except (ValueError, TypeError):
        return None


def _days_ago(ts: str) -> float | None:
    t = _parse_ts(ts)
    if t is None:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return max(0.0, (now - t).total_seconds() / 86400.0)


def _recent_refs(entries: list[dict[str, Any]],
                 window_days: float) -> dict[str, float]:
    """Map artifact ref -> smallest days-ago among recent entries for it."""
    out: dict[str, float] = {}
    for e in entries:
        ref = str(e.get("ref", "") or "").upper()
        if not ref:
            continue
        d = _days_ago(e.get("ts", ""))
        if d is None or d > window_days:
            continue
        if ref not in out or d < out[ref]:
            out[ref] = d
    return out


def _last_activity_days(ref: str, entries: list[dict[str, Any]]) -> float | None:
    """Days since the most recent activity entry referencing `ref`."""
    best: float | None = None
    for e in entries:
        if str(e.get("ref", "") or "").upper() != ref.upper():
            continue
        d = _days_ago(e.get("ts", ""))
        if d is not None and (best is None or d < best):
            best = d
    return best


def compute_watchdog(project_root: Path, harness: Harness | None = None,
                     ruleset: RuleSet | None = None,
                     window_days: float = RECENT_DAYS,
                     top: int = 5) -> dict[str, Any]:
    harness = harness or load_harness(project_root)
    ruleset = ruleset or validate(project_root, harness)
    entries = read_entries(project_root)
    recent = _recent_refs(entries, window_days)

    items: list[dict[str, Any]] = []

    def add(severity: str, problem: str, ref: str | None, handling: str,
            detail: str = "", path: str | None = None, biz: str = "") -> None:
        items.append({"severity": severity, "problem": problem, "ref": ref,
                      "handling": handling, "detail": detail, "path": path,
                      "biz": biz})

    # ---- critical: harness broken --------------------------------------
    errs = ruleset.errors()
    if errs:
        refs = sorted({f.artifact_id for f in errs if f.artifact_id})
        add("critical",
            f"harness broken — {len(errs)} validation error(s)",
            refs[0] if len(refs) == 1 else None,
            "fix the harness first (`tenx validate`)",
            detail="; ".join(f.message for f in errs[:3]))

    # ---- high: drift ---------------------------------------------------
    warns = ruleset.warnings()
    if warns:
        add("high", f"{len(warns)} drift warning(s)", None,
            "reconcile authored vs derived state (`tenx next`)",
            detail="; ".join(f.message for f in warns[:3]))

    # ---- high: blocked specs / tickets --------------------------------
    for s in harness.by_type("spec"):
        biz = effective_priority(s, harness)
        blocked_tickets = [t for t in s.tickets
                           if str(t.get("status")) == "blocked"]
        if s.status == "blocked" or blocked_tickets:
            n = len(blocked_tickets)
            last = _last_activity_days(s.id, entries)
            if s.id in recent:
                handling = (f"being worked on (activity "
                            f"{recent[s.id]:.0f}d ago)")
            elif last is None:
                handling = "unattended — no activity ever logged"
            else:
                handling = (f"stalled — blocked, last activity "
                            f"{last:.0f}d ago")
            what = (f"{s.id} blocked" if s.status == "blocked"
                    else f"{s.id} has {n} blocked ticket(s)")
            add("high", what, s.id, handling, detail=s.title,
                path=s.rel(project_root), biz=biz)

    # ---- high: unresolved blocker log entries -------------------------
    open_blockers = [e for e in entries if e.get("type") == "blocker"]
    if open_blockers:
        last = open_blockers[-1]
        ref = str(last.get("ref", "") or "") or None
        d = _days_ago(last.get("ts", ""))
        add("high", f"{len(open_blockers)} blocker(s) logged", ref,
            "resolve and log the fix, or re-triage",
            detail=str(last.get("message", ""))[:120],
            biz="")

    # ---- medium: specs waiting in_review ------------------------------
    for s in harness.by_type("spec"):
        if s.status == "in_review":
            biz = effective_priority(s, harness)
            add("medium", f"{s.id} waiting in_review", s.id,
                "run `tenx review` and land or bounce it",
                detail=s.title, path=s.rel(project_root), biz=biz)

    # ---- medium: in_progress work gone quiet --------------------------
    for s in harness.by_type("spec"):
        if s.status != "in_progress":
            continue
        if s.id in recent:
            continue  # actively handled
        last = _last_activity_days(s.id, entries)
        biz = effective_priority(s, harness)
        if last is None:
            handling = "gone quiet — no activity logged for this spec"
        else:
            handling = f"gone quiet — last activity {last:.0f}d ago"
        add("medium", f"{s.id} in_progress but quiet", s.id, handling,
            detail=s.title, path=s.rel(project_root), biz=biz)

    # ---- rank: severity, then business priority, then ref -------------
    from .nextup import PRIORITY_RANK, UNSET_RANK
    items.sort(key=lambda it: (
        SEV_RANK.get(it["severity"], 9),
        PRIORITY_RANK.get(it.get("biz", ""), UNSET_RANK),
        it.get("ref") or ""))
    items = items[:top]

    healthy_in_progress = [s.id for s in harness.by_type("spec")
                           if s.status == "in_progress" and s.id in recent]
    return {
        "window_days": window_days,
        "items": items,
        "counts": {
            "artifacts": len(harness.artifacts),
            "activity_entries": len(entries),
            "errors": len(errs),
            "warnings": len(warns),
            "healthy_in_progress": healthy_in_progress,
        },
    }


def render_watchdog(project_root: Path, window_days: float = RECENT_DAYS,
                    top: int = 5) -> str:
    data = compute_watchdog(project_root, window_days=window_days, top=top)
    c = data["counts"]
    lines = ["# tenx watchdog — what needs attention", ""]
    lines.append(f"Scanned {c['artifacts']} artifacts and "
                 f"{c['activity_entries']} activity entries "
                 f"(recent window: {data['window_days']:.0f} days).")
    lines.append("")
    if not data["items"]:
        lines.append("Nothing needs attention. Harness is clean and every "
                     "in_progress spec has recent activity.")
        return "\n".join(lines) + "\n"
    for i, it in enumerate(data["items"], 1):
        sev = it["severity"].upper()
        biz = f" {it['biz']}" if it.get("biz") else ""
        ref = f" [{it['ref']}]" if it.get("ref") else ""
        lines.append(f"{i}. [{sev}]{biz} {it['problem']}{ref}")
        lines.append(f"   → {it['handling']}")
        if it.get("detail"):
            lines.append(f"     {it['detail']}")
    hip = c["healthy_in_progress"]
    if hip:
        lines.append("")
        lines.append(f"Healthy (in_progress with recent activity): "
                     f"{', '.join(hip)}")
    return "\n".join(lines) + "\n"
