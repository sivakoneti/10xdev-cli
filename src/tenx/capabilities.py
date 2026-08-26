"""Capability catalog: what tenx can do, and when an agent should use it.

Single curated listing behind three surfaces:

- `tenx capabilities [--json]`   (CLI)
- the `tenx_capabilities` MCP tool
- a discovery pointer in the context packet

Entries are hand-written on purpose: argparse help says what a flag does,
not "run this after tenx_context to spot stalled work". Keep entries in
sync when adding a subcommand or MCP tool.
"""

from __future__ import annotations

from typing import Any

from . import __version__

# surface: "cli" = CLI-only, "mcp" = MCP-only, "both" = exposed over both.
# group: session-loop stage used to order the human-readable rendering.
CAPABILITIES: list[dict[str, str]] = [
    # ---------------------------------------------------------- discover
    {"name": "capabilities", "surface": "both", "group": "discover",
     "usage": "tenx capabilities [--json]",
     "what": "This catalog: every command and tool, with when-to-use "
             "guidance.",
     "when": "Run once when you first meet a tenx-governed project — or "
             "whenever unsure which tenx command fits the job."},
    {"name": "context", "surface": "both", "group": "discover",
     "usage": "tenx context [--mode agent|operator] [--budget N] [--json]",
     "what": "The context packet: project state, specs, conventions, "
             "recent activity, operating protocol.",
     "when": "First thing in any session, before planning or coding."},
    {"name": "status", "surface": "both", "group": "discover",
     "usage": "tenx status [--json]",
     "what": "Operator dashboard: artifact counts, statuses, recent "
             "activity.",
     "when": "A compact health readout for humans; agents usually want "
             "`tenx context` instead."},
    {"name": "scan", "surface": "both", "group": "discover",
     "usage": "tenx scan [--write] [--json]",
     "what": "Map a codebase: stacks, test commands, CI, agent files, "
             "directory census. --write REPLACES the codebase-map DOC "
             "body (regenerated content), so keep manual notes in a "
             "separate DOC.",
     "when": "Bootstrap or refresh the codebase map in .tenx/docs/; "
             "re-run after major structural changes."},
    {"name": "doctor", "surface": "cli", "group": "discover",
     "usage": "tenx doctor [--json]",
     "what": "Environment and harness health check, including the "
             "enforcement audit: pre-commit gate present/fresh, managed "
             "agent surfaces current, MCP + skills installed. Exits 1 "
             "with exact fix commands when anything is wrong.",
     "when": "Something looks broken (discovery, adapters, git, gates) "
             "and you want one diagnostic dump."},
    {"name": "update", "surface": "cli", "group": "discover",
     "usage": "tenx update --check | tenx update",
     "what": "Check for / apply CLI self-updates.",
     "when": "Session start: run `tenx update --check`; never block on it."},
    # -------------------------------------------------------------- plan
    {"name": "new", "surface": "cli", "group": "plan",
     "usage": "tenx new {epic,spec,convention,doc} TITLE [--epic ID] "
              "[--owner X] [--tags a,b] [--priority P0|P1|P2]",
     "what": "Create an artifact in .tenx/.",
     "when": "Before non-trivial changes: find or create the epic+spec "
             "(specs need --epic)."},
    {"name": "show", "surface": "both", "group": "plan",
     "usage": "tenx show <ID> [--json]",
     "what": "Print one artifact in full by id (EPC-/SPC-/CON-/DOC-).",
     "when": "Load the artifacts relevant to your task before coding."},
    {"name": "list", "surface": "both", "group": "plan",
     "usage": "tenx list [type] [--json]",
     "what": "List artifacts, optionally filtered by type.",
     "when": "Finding ids before `tenx show` or checking what exists."},
    {"name": "exec", "surface": "both", "group": "plan",
     "usage": "tenx exec <SPEC-ID> [--json]",
     "what": "Execution brief for a spec: everything needed to implement "
             "it ticket by ticket.",
     "when": "About to implement a spec autonomously — start here "
             "instead of re-reading the raw spec."},
    # ------------------------------------------------------------- track
    {"name": "next", "surface": "both", "group": "track",
     "usage": "tenx next [--json]",
     "what": "Prioritized work queue: the highest-value ticket to "
             "implement next.",
     "when": "Unsure what to do: run it and do the top item."},
    {"name": "ticket", "surface": "both", "group": "track",
     "usage": "tenx ticket <SPEC-ID> <TICKET-ID> "
              "{todo,in_progress,in_review,done,blocked} [--title T]",
     "what": "Move a spec ticket's status (creates on first touch).",
     "when": "Continuously, as you work — statuses are harness context."},
    {"name": "set", "surface": "cli", "group": "track",
     "usage": "tenx set <ID> {status,owner,epic,title,tags,priority,"
              "evidence} VALUE [--force]",
     "what": "Update artifact metadata fields.",
     "when": "Moving spec/epic status (evidence gate applies), assigning "
             "owners or priorities. `--force` bypasses the gate on "
             "`status complete` — human override only."},
    {"name": "log", "surface": "both", "group": "track",
     "usage": "tenx log \"message\" [--ref ID] [--type note|progress|"
              "decision|blocker|review] [--actor agent]",
     "what": "Append to the activity log.",
     "when": "After significant work. Unwritten work is lost context."},
    {"name": "history", "surface": "cli", "group": "track",
     "usage": "tenx history [--limit N] [--json]",
     "what": "Read the activity log back.",
     "when": "Catching up on what previous sessions did."},
    {"name": "watchdog", "surface": "both", "group": "track",
     "usage": "tenx watchdog [--window DAYS] [--top N] [--json]",
     "what": "Pulse-check digest: top attention items, each cross-"
             "referenced with recent activity to say whether it is being "
             "handled.",
     "when": "After tenx context, to spot stalled or blocked work."},
    {"name": "triage", "surface": "both", "group": "track",
     "usage": "tenx triage [--window DAYS] [--top N] [--json]",
     "what": "Escalation digest for a human: act-now / watch / healthy, "
             "plus the single most important decision needed. Read-only.",
     "when": "Reporting to the operator, or deciding what genuinely "
             "needs a human."},
    {"name": "review", "surface": "cli", "group": "track",
     "usage": "tenx review [--json]",
     "what": "What awaits review (specs and tickets in_review).",
     "when": "Human review passes; agents check it before claiming "
             "nothing is pending."},
    {"name": "archive", "surface": "cli", "group": "track",
     "usage": "tenx archive <EPIC-ID> --approved-by \"<operator>\" [--yes]",
     "what": "Retire a finished epic and its specs. --approved-by is "
             "REQUIRED and recorded in the activity log.",
     "when": "Only with explicit human approval — never archive on your "
             "own initiative."},
    {"name": "sync", "surface": "cli", "group": "track",
     "usage": "tenx sync {push,pull} [--spec ID] [--dry-run] [--json]",
     "what": "Two-way sync between spec tickets and GitHub Issues.",
     "when": "When the project mirrors work to GitHub Issues."},
    # ----------------------------------------------------------- quality
    {"name": "validate", "surface": "both", "group": "quality",
     "usage": "tenx validate [--fix] [--list-rules] [--json]",
     "what": "Lint the SDLC: drift, broken refs, stale artifacts. "
             "--list-rules prints the rule catalog.",
     "when": "Before ending any session and before every commit (the "
             "pre-commit gate runs it); fix errors, never leave new ones."},
    {"name": "converge", "surface": "cli", "group": "quality",
     "usage": "tenx converge <SPC-ID> [--json] [--append]",
     "what": "Deterministic spec-completion convergence: maps FR-### "
             "requirements to tickets, reports satisfied/open, and with "
             "--append adds a todo ticket per uncovered requirement.",
     "when": "Before marking a spec complete: run it, satisfy the open "
             "requirements, resolve clarify markers, re-run until "
             "CONVERGED."},
    {"name": "gate", "surface": "cli", "group": "quality",
     "usage": "tenx gate commit-check",
     "what": "Commit-time freshness gate: staged code files must have "
             "write-back (an activity-log entry) behind them. Mode via "
             "commit_gate in .tenx/config.yaml: on (block), warn "
             "(default), off.",
     "when": "Run automatically by the git pre-commit hook; run manually "
             "to see what the hook would say."},
    {"name": "changelog", "surface": "both", "group": "quality",
     "usage": "tenx changelog [{show,add,release}] [TEXT] "
              "[--type added|changed|...] [--ref ID]",
     "what": "Docs-sync: manage CHANGELOG.md (Keep-a-Changelog).",
     "when": "Whenever you ship a behavior change — the evidence gate "
             "requires an entry before a spec/epic can be completed."},
    # --------------------------------------------------------- integrate
    {"name": "init", "surface": "cli", "group": "integrate",
     "usage": "tenx init [--name X] [--description D] [--bootstrap] "
              "[--standalone --code-root PATH] [--agent A|all|detected|"
              "none] [--no-hooks] [--force]",
     "what": "Scaffold the .tenx/ harness in a repo and wire the agent "
             "surfaces (instruction files, session hook, MCP, skills, "
             "pre-commit gate).",
     "when": "Once per repo, before any other tenx command; re-run with "
             "--force only to repair a broken harness."},
    {"name": "mcp", "surface": "cli", "group": "integrate",
     "usage": "tenx mcp [serve] | tenx mcp install",
     "what": "Model Context Protocol server on stdio exposing tenx as "
             "native tools; `install` wires it into .mcp.json.",
     "when": "Harnesses with MCP support get structured tool access; "
             "`init` installs it automatically unless --no-hooks."},
    {"name": "hook", "surface": "cli", "group": "integrate",
     "usage": "tenx hook [emit|install|bootstrap|detect] [--agent A] "
              "[--mode M] [--budget N] [--git] [--no-log] [--json]",
     "what": "Session-start hook: emit or install the context packet "
             "wiring for agent harnesses; --git adds the pre-commit gate.",
     "when": "Wiring a new harness manually or debugging hook emission; "
             "`init` normally handles this."},
    {"name": "skills", "surface": "cli", "group": "integrate",
     "usage": "tenx skills {list,install,status} [--target DIR]",
     "what": "Manage bundled agent skills.",
     "when": "Installing the tenx skill pack into a harness skills dir."},
]



GROUP_ORDER = ["discover", "plan", "track", "quality", "integrate"]

GROUP_TITLES = {
    "discover": "Discover & orient",
    "plan": "Plan (artifacts)",
    "track": "Track & coordinate work",
    "quality": "Quality gates",
    "integrate": "Integrate with agent harnesses",
}


def catalog() -> dict[str, Any]:
    """JSON payload: stable shape for agents."""
    return {"cli_version": __version__,
            "capabilities": CAPABILITIES}


def render_text() -> str:
    """Grouped human/agent-readable listing."""
    lines = [f"tenx v{__version__} — capability catalog",
             "", "Every command below is also available as an MCP tool "
                 f"(tenx_<name>) where surface is 'both'. Run "
                 "`tenx capabilities --json` for machine-readable output.",
             ""]
    by_group: dict[str, list[dict[str, str]]] = {}
    for cap in CAPABILITIES:
        by_group.setdefault(cap["group"], []).append(cap)
    for group in GROUP_ORDER:
        caps = by_group.get(group)
        if not caps:
            continue
        lines.append(f"## {GROUP_TITLES[group]}")
        for cap in caps:
            lines.append(f"- `{cap['usage']}`  [{cap['surface']}]")
            lines.append(f"  what: {cap['what']}")
            lines.append(f"  when: {cap['when']}")
        lines.append("")
    return "\n".join(lines)
