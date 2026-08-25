"""tenx.triage - opinionated escalation layer over `tenx watchdog`.

`tenx triage` answers the one question a human overseeing a fleet of agents
asks: "what needs ME right now?" It classifies the current watchdog items
into act-now / watch / healthy and picks the single most important human
escalation. Read-only: it never mutates harness state and is offline-safe.

The `tenx-triage` bundled skill wraps this as an agent role (a "Triage
Officer") that any runtime can schedule.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .watchdog import RECENT_DAYS, compute_watchdog

# handling-verdict fragments that mean "no one is on this" -> needs a human
UNATTENDED_FRAGMENTS = ("unattended", "stalled")


def _is_unattended(item: dict[str, Any]) -> bool:
    handling = str(item.get("handling", "") or "").lower()
    return any(f in handling for f in UNATTENDED_FRAGMENTS)


def compute_triage(project_root: Path, harness: Any = None,
                   ruleset: Any = None, window_days: float = RECENT_DAYS,
                   top: int = 5) -> dict[str, Any]:
    """Build the triage payload on top of `compute_watchdog`.

    act_now  = critical items, plus high items nobody is handling.
    watch    = everything else (being worked on, waiting review, gone quiet).
    escalation = the single most important item needing a human decision.
    """
    wd = compute_watchdog(project_root, harness=harness, ruleset=ruleset,
                          window_days=window_days, top=top)
    act_now: list[dict[str, Any]] = []
    watch: list[dict[str, Any]] = []
    for it in wd["items"]:
        if it["severity"] == "critical" or (
                it["severity"] == "high" and _is_unattended(it)):
            act_now.append(it)
        else:
            watch.append(it)
    escalation = act_now[0] if act_now else None
    return {
        "window_days": wd["window_days"],
        "act_now": act_now,
        "watch": watch,
        "healthy_in_progress": wd["counts"].get("healthy_in_progress", []),
        "escalation": escalation,
        "counts": wd["counts"],
    }


def _fmt(item: dict[str, Any]) -> str:
    biz = f" {item['biz']}" if item.get("biz") else ""
    ref = f" [{item['ref']}]" if item.get("ref") else ""
    return (f"- [{item['severity'].upper()}]{biz} {item['problem']}{ref}"
            f" -> {item['handling']}")


def render_triage(project_root: Path, window_days: float = RECENT_DAYS,
                  top: int = 5) -> str:
    data = compute_triage(project_root, window_days=window_days, top=top)
    c = data["counts"]
    lines: list[str] = []
    lines.append("# tenx triage")
    lines.append("")
    hip = data["healthy_in_progress"]
    lines.append(f"Health: {c['errors']} error(s), {c['warnings']} "
                 f"warning(s), {len(hip)} healthy in-progress.")
    lines.append("")
    lines.append(f"## Act now ({len(data['act_now'])})")
    if data["act_now"]:
        lines.extend(_fmt(it) for it in data["act_now"])
    else:
        lines.append("- nothing critical")
    lines.append("")
    lines.append(f"## Watch ({len(data['watch'])})")
    if data["watch"]:
        lines.extend(_fmt(it) for it in data["watch"])
    else:
        lines.append("- nothing to watch")
    lines.append("")
    lines.append("## Escalate to human")
    esc = data["escalation"]
    if esc:
        ref = f" [{esc['ref']}]" if esc.get("ref") else ""
        lines.append(f"> {esc['problem']}{ref} - {esc['handling']}")
    else:
        lines.append("> nothing needs a human decision right now")
    lines.append("")
    return "\n".join(lines)
