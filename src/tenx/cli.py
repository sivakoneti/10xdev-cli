"""tenx — meta-harness CLI: context-as-code for AI coding agents.

Command map (mirrors the 10X harness from the David Ondrej podcast):

  tenx init                        scaffold .tenx/ in this project
  tenx context --mode operator     human dashboard
  tenx context --mode agent        full session-start context packet
  tenx status                      alias for operator dashboard
  tenx new <type> "Title"          create epic/spec/convention/doc artifact
  tenx show <ID>                   print one artifact (metadata + body)
  tenx list [type]                 list artifacts
  tenx set <ID> <field> <value>    update artifact metadata
  tenx ticket <SPEC> <TID> <stat>  move a ticket (todo/in_progress/in_review/done)
  tenx validate [--fix]            lint the SDLC (drift, refs, staleness)
  tenx log "message" --ref <ID>    append to the activity log
  tenx history                     show recent activity
  tenx next                        most important thing to work on next
  tenx watchdog                    top things needing attention + are they handled
  tenx triage                      what needs a human now: act/watch/escalation
  tenx skills list|install         bundled skills per artifact type
  tenx hook [--mode agent]         emit the session-start packet
  tenx hook install [--agent X]    wire packet into claude/codex/opencode/gemini
  tenx doctor                      environment + harness health check
  tenx update [--check]            check for (and apply) CLI updates
"""

from __future__ import annotations

import argparse
import os
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .activity import TYPES as LOG_TYPES, append_entry, read_entries
from .artifacts import (
    PRIORITIES,
    STATUSES,
    TICKET_STATUSES,
    TYPE_PREFIX,
    create_artifact,
    derived_status,
    effective_priority,
    load_harness,
    update_meta,
)
from .context import build_context, render_markdown
from .execbrief import build_exec_brief
from .discovery import (TENXLINK, code_root, env_project_root,
                        find_project_root, harness_root, is_initialized)
from .adapters import adapter_ids, detect_adapters, get_adapter
from .hooks import (bootstrap_snippet, install as install_hook,
                     install_git_hook)
from .nextup import compute_next, render_next
from .watchdog import compute_watchdog, render_watchdog
from .triage import compute_triage, render_triage
from .locking import LockTimeout, harness_lock
from .rules import RULE_CATALOG, list_rules_text, rebuild_convention_index, validate
from .skills import install_skills, list_skills
from .templates import BODY_TEMPLATES, CODE_ROOT_COMMENT, CONFIG_TEMPLATE, HARNESS_README
from .update import run_update
from .yamlite import dump_frontmatter


def _root_or_die(explicit: str | None = None) -> Path:
    root = Path(explicit).resolve() if explicit else (env_project_root() or find_project_root())
    if root is None:
        print("tenx: could not determine project root", file=sys.stderr)
        sys.exit(2)
    return root


def _require_init(root: Path) -> None:
    if not is_initialized(root):
        print(f"tenx: no harness at {harness_root(root)} — run `tenx init` first",
              file=sys.stderr)
        sys.exit(2)


def _emit(payload: Any, as_json: bool, md_renderer) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    else:
        sys.stdout.write(md_renderer())


# ---------------------------------------------------------------- commands

def cmd_init(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    hroot = harness_root(root)
    if is_initialized(root) and not args.force:
        print(f"tenx: harness already initialized at {hroot}")
        if not getattr(args, "no_hooks", False):
            print("Ensuring agent harnesses are wired:")
            _install_agent_surfaces(root, getattr(args, "agent", "detected"))
        return 0
    name = args.name or root.name
    desc = args.description or f"Context base for {name}"
    for sub in ("epics", "specs", "conventions", "docs", "log"):
        (hroot / sub).mkdir(parents=True, exist_ok=True)
    code_root_line = CODE_ROOT_COMMENT
    link_written: Path | None = None
    if args.standalone:
        if not args.code_root:
            print("tenx: --standalone needs --code-root <path-to-code-repo>",
                  file=sys.stderr)
            return 2
        code_path = Path(args.code_root).expanduser().resolve()
        if not code_path.is_dir():
            print(f"tenx: code root {code_path} is not a directory",
                  file=sys.stderr)
            return 2
        try:
            rel = Path(os.path.relpath(code_path, root))
        except ValueError:
            rel = code_path
        code_root_line = f"code_root: {rel}\n"
        # pointer in the code repo back to this PM repo
        try:
            back = Path(os.path.relpath(root, code_path))
        except ValueError:
            back = root
        link = code_path / TENXLINK
        if not link.exists() or args.force:
            link.write_text(back.as_posix() + "\n", encoding="utf-8")
            link_written = link
    cfg = hroot / "config.yaml"
    if not cfg.exists() or args.force:
        cfg.write_text(CONFIG_TEMPLATE.format(project=name, description=desc,
                                              code_root_line=code_root_line),
                       encoding="utf-8")
    readme = hroot / "README.md"
    if not readme.exists():
        readme.write_text(HARNESS_README, encoding="utf-8")
    from . import changelog as _cl
    seeded_cl = _cl.seed_changelog(root)
    print(f"Initialized tenx harness at {hroot}")
    print("  config.yaml, epics/, specs/, conventions/, docs/, log/")
    if seeded_cl:
        print("  seeded CHANGELOG.md (Keep a Changelog - docs-sync)")
    if link_written is not None:
        print(f"  wrote pointer {link_written} -> {root}")

    if args.bootstrap:
        harness = load_harness(root)
        if not harness.by_type("convention"):
            facts = _detect_project_facts(root)
            body = ("## Rule\n\nFollow the existing project structure and "
                    "tooling detected below; do not introduce new frameworks "
                    "without a spec.\n\n## Detected project facts\n\n" + facts)
            create_artifact(root, "convention", "General project conventions",
                            body=body)
            rebuild_convention_index(root, load_harness(root))
            print("  seeded CON-001 (general conventions) + INDEX.md")
        if not harness.by_type("doc"):
            create_artifact(root, "doc", "Architecture overview",
                            body=("## Purpose\n\nOrientation for agents new to "
                                  "this codebase.\n\n## Content\n\nTODO: "
                                  "describe components, data flow, and how to "
                                  "run/test the project.\n"))
            print("  seeded DOC-001 (architecture overview skeleton)")
    if not getattr(args, "no_hooks", False):
        print("Wiring agent harnesses so they follow tenx:")
        _install_agent_surfaces(root, getattr(args, "agent", "detected"))
    print("\nNext steps:")
    print(f'  tenx new epic "What we are building next"')
    print("  tenx context --mode agent   # what each new agent session reads")
    if getattr(args, "no_hooks", False):
        print("  tenx hook install --agent detected   # agent wiring was skipped")
    return 0


def _detect_project_facts(root: Path) -> str:
    facts: list[str] = []
    pj = root / "package.json"
    if pj.is_file():
        try:
            data = json.loads(pj.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            facts.append(f"- Node project `{data.get('name', '?')}` "
                         f"(package.json). Scripts: "
                         f"{', '.join(sorted(scripts)) or 'none'}.")
        except json.JSONDecodeError:
            facts.append("- package.json present (unparseable).")
    if (root / "pyproject.toml").is_file():
        facts.append("- Python project (pyproject.toml).")
    if (root / "go.mod").is_file():
        facts.append("- Go project (go.mod).")
    if (root / "Cargo.toml").is_file():
        facts.append("- Rust project (Cargo.toml).")
    lock = [n for n in ("pnpm-lock.yaml", "package-lock.json",
                        "yarn.lock", "bun.lockb", "uv.lock", "poetry.lock")
            if (root / n).exists()]
    if lock:
        facts.append(f"- Lockfile(s): {', '.join(lock)}.")
    ci = root / ".github" / "workflows"
    if ci.is_dir():
        facts.append("- GitHub Actions CI in .github/workflows/.")
    if not facts:
        facts.append("- No well-known manifest detected; fill this in manually.")
    return "\n".join(facts) + "\n"


def cmd_context(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    mode = args.mode
    budget = getattr(args, "budget", None)
    if args.json:
        data = build_context(root, mode)
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        sys.stdout.write(render_markdown(root, mode, budget=budget))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    args.mode = "operator"
    return cmd_context(args)


def cmd_capabilities(args: argparse.Namespace) -> int:
    """Print the capability catalog (what tenx can do, and when)."""
    from .capabilities import catalog, render_text
    _emit(catalog(), args.json, render_text)
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    from .discovery import code_root as resolve_code_root
    from .scan import scan_tree

    root = _root_or_die(args.root)
    _require_init(root)
    croot = resolve_code_root(root)
    result = scan_tree(root, croot)
    if getattr(args, "write", False):
        from .scan import write_codebase_map
        rel = write_codebase_map(root, croot, result)
        print(f"codebase map written to .tenx/{rel}")
        return 0
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    # human summary
    print(f"# tenx scan — {result['project'] or 'unnamed project'}")
    print(f"code root: {result['code_root']}")
    print(f"files scanned: {result['file_count_scanned']}")
    print()
    print("stacks:      " + (", ".join(result["stacks"]) or "none detected"))
    if result["markers"]:
        print("markers:     " + ", ".join(result["markers"]))
    if result["entry_hints"]:
        print("entry hints: " + ", ".join(result["entry_hints"]))
    print("tests:       " + (", ".join(result["test_setup"]) or "none found"))
    print("CI:          " + (", ".join(result["ci"]) or "none found"))
    print("agent files: " + (", ".join(result["agent_files"]) or "none"))
    if result["top_level_census"]:
        print()
        total = int(result.get("top_level_entries",
                               len(result["top_level_census"])) or 0)
        suffix = (f" — showing top {len(result['top_level_census'])} "
                  f"of {total} entries") if total > len(
            result["top_level_census"]) else ""
        print(f"top-level census (files per entry, depth<=2){suffix}:")
        for name, n in result["top_level_census"].items():
            print(f"  {name:<28} {n}")
    print()
    print("Run `tenx scan --write` to store this map as a DOC artifact.")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    from . import sync as syncmod
    from .activity import append_entry
    from .artifacts import load_harness

    root = _root_or_die(args.root)
    _require_init(root)
    harness = load_harness(root)
    if args.spec:
        spec = harness.get(args.spec.upper())
        if spec is None or spec.type != "spec":
            print(f"tenx: unknown spec {args.spec}", file=sys.stderr)
            return 2
        specs = [spec]
    else:
        specs = [s for s in harness.by_type("spec") if s.tickets]

    try:
        token = syncmod.resolve_token()
        repo = syncmod.resolve_repo(root, harness.config)
    except syncmod.SyncError as e:
        print(f"tenx sync: {e}", file=sys.stderr)
        return 2

    try:
        issues = syncmod.list_issues(token, repo)
    except syncmod.SyncError as e:
        print(f"tenx sync: {e}", file=sys.stderr)
        return 1

    if args.direction == "push":
        actions = syncmod.plan_push(specs, issues, project_root=root)
        if args.dry_run:
            if args.json:
                print(json.dumps({"repo": repo, "dry_run": True,
                                  "actions": actions}, indent=2,
                                 default=str))
            else:
                print(f"# tenx sync push — {repo} (dry run)")
                for a in actions:
                    if a["action"] == "skip":
                        print(f"  =  {a['ticket']} #{a.get('number')} "
                              f"already in sync")
                    elif a["action"] == "create":
                        print(f"  +  {a['ticket']} create: {a['title']}")
                    else:
                        print(f"  ~  {a['ticket']} #{a.get('number')} "
                              f"update {sorted(a['changes'])}")
            return 0
        # execute
        label_names = {syncmod.BASE_LABEL}
        for a in actions:
            if a["action"] == "create":
                label_names.update(a["labels"])
            elif a["action"] == "update" and "labels" in a["changes"]:
                label_names.update(a["changes"]["labels"])
        done = []
        try:
            syncmod.ensure_labels(token, repo, sorted(label_names))
            for a in actions:
                if a["action"] == "create":
                    it = syncmod.create_issue(token, repo, a["title"],
                                              a["body"], a["labels"])
                    if a["state"] == "closed":
                        syncmod.update_issue(token, repo, it["number"],
                                             {"state": "closed"})
                    done.append({**a, "number": it["number"],
                                 "url": it.get("html_url")})
                elif a["action"] == "update":
                    syncmod.update_issue(token, repo, a["number"],
                                         a["changes"])
                    done.append(a)
                else:
                    done.append(a)
        except syncmod.SyncError as e:
            print(f"tenx sync: {e}", file=sys.stderr)
            print("tenx sync: GitHub/network error; re-run to resume "
                  "(push is idempotent).", file=sys.stderr)
            return 2
        created = sum(1 for a in done if a["action"] == "create")
        updated = sum(1 for a in done if a["action"] == "update")
        if created or updated:
            append_entry(
                root,
                f"github sync push to {repo}: {created} created, "
                f"{updated} updated",
                entry_type="progress",
                ref=args.spec.upper() if args.spec else None)
        if args.json:
            print(json.dumps({"repo": repo, "actions": done}, indent=2,
                             default=str))
        else:
            print(f"synced {repo}: {created} created, {updated} updated, "
                  f"{len(done) - created - updated} in sync")
        return 0

    # pull
    actions = syncmod.plan_pull(specs, issues)
    if args.dry_run:
        if args.json:
            print(json.dumps({"repo": repo, "dry_run": True,
                              "actions": actions}, indent=2))
        else:
            print(f"# tenx sync pull — {repo} (dry run)")
            for a in actions:
                print(f"  ~  {a['ticket']}: {a['from']} -> {a['to']} "
                      f"(issue #{a.get('number')})")
            if not actions:
                print("  nothing to pull")
        return 0
    changed = 0
    for a in actions:
        spec = harness.get(a["spec"])
        if spec is None:
            continue
        tickets = spec.meta.get("tickets") or []
        for t in tickets:
            if str(t.get("id")) == a["ticket"]:
                t["status"] = a["to"]
                changed += 1
                break
        from .artifacts import update_meta
        update_meta(spec, {"tickets": tickets})
    if changed:
        append_entry(root,
                     f"github sync pull from {repo}: {changed} ticket(s) "
                     f"updated from issue state",
                     entry_type="progress",
                     ref=args.spec.upper() if args.spec else None)
    if args.json:
        print(json.dumps({"repo": repo, "actions": actions,
                          "changed": changed}, indent=2))
    else:
        for a in actions:
            print(f"  {a['ticket']}: {a['from']} -> {a['to']}")
        print(f"pulled {repo}: {changed} ticket(s) updated")
    return 0



def _install_mcp_config(target_root: Path) -> tuple[str, Path]:
    """Write/merge the tenx MCP server into <target_root>/.mcp.json.

    Idempotent. Returns (verb, path) with verb in created/updated/unchanged.
    """
    import json as _json
    target = target_root / ".mcp.json"
    server = {"command": "tenx", "args": ["mcp"]}
    config = {"mcpServers": {"tenx": server}}
    if target.exists():
        try:
            existing = _json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
        servers = existing.setdefault("mcpServers", {})
        if servers.get("tenx") == server:
            return "unchanged", target
        servers["tenx"] = server
        config = existing
        verb = "updated"
    else:
        verb = "created"
    target.write_text(_json.dumps(config, indent=2) + "\n",
                      encoding="utf-8")
    return verb, target


def _install_agent_surfaces(root: Path, agent: str) -> None:
    """Wire agent harnesses so they follow tenx out of the box.

    Installs (1) instruction files + session hook for `agent`, (2) bundled
    skills, and (3) the MCP server registration. Fault-tolerant: a failure
    warns but never aborts `tenx init`.
    """
    target = code_root(root)
    # 1. instruction files (AGENTS.md et al.) + session-start hook
    try:
        results = install_hook(root, agent)
        changed = [p for c, p in results if c]
        if changed:
            print(f"  agent hooks: wired {len(changed)} file(s) "
                  f"(--agent {agent})")
            for p in changed:
                print(f"    {p}")
        else:
            print(f"  agent hooks: already wired (--agent {agent})")
    except ValueError as exc:
        print(f"tenx: hook install skipped: {exc}", file=sys.stderr)
    # 2. bundled skills
    try:
        skills_target = target / ".claude" / "skills"
        written = install_skills(skills_target)
        print(f"  skills: installed {len(written)} bundled skills "
              f"-> {skills_target}")
    except Exception as exc:  # defensive: never abort init
        print(f"tenx: skills install skipped: {exc}", file=sys.stderr)
    # 3. MCP registration
    try:
        verb, mcp_path = _install_mcp_config(target)
        print(f"  mcp: {verb} {mcp_path}")
    except Exception as exc:  # defensive: never abort init
        print(f"tenx: mcp install skipped: {exc}", file=sys.stderr)
    # 4. git pre-commit gate (the universal, harness-agnostic backstop)
    try:
        changed, path = install_git_hook(target)
        verb = "installed" if changed else "already present"
        print(f"  git gate: {verb} -> {path}")
    except Exception as exc:  # defensive: never abort init
        print(f"tenx: git hook install skipped: {exc}", file=sys.stderr)


def cmd_mcp(args: argparse.Namespace) -> int:
    if getattr(args, "mcp_cmd", "serve") == "install":
        root = _root_or_die(args.root)
        _require_init(root)
        verb, target = _install_mcp_config(code_root(root))
        print(f"  {verb}: {target}")
        if verb != "unchanged":
            print("MCP-capable harnesses (Claude Code et al.) will now see "
                  "tenx tools in this project.")
        return 0
    # serve
    from .mcp import McpServer
    if args.root:
        import os
        os.environ["TENX_ROOT"] = str(Path(args.root).resolve())
    McpServer().serve()
    return 0



def _days_since(date_str: str) -> int | None:
    from datetime import date
    try:
        y, m, d = (int(x) for x in str(date_str)[:10].split("-"))
        return max(0, (date.today() - date(y, m, d)).days)
    except (ValueError, TypeError):
        return None


def cmd_review(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    harness = load_harness(root)
    items = []
    for s in harness.by_type("spec"):
        in_review_tickets = [t for t in s.tickets
                             if str(t.get("status")) == "in_review"]
        if s.status == "in_review" or in_review_tickets:
            items.append({
                "spec": s.id,
                "title": s.title,
                "spec_status": s.status,
                "days_in_state": _days_since(s.meta.get("updated", "")),
                "path": s.rel(root),
                "in_review_tickets": [
                    {"id": str(t.get("id", "")),
                     "title": str(t.get("title", ""))}
                    for t in in_review_tickets],
            })
    if args.json:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        return 0
    if not items:
        print("nothing awaits review.")
        return 0
    print("# tenx review — awaiting review")
    for it in items:
        days = (f" ({it['days_in_state']}d in state)"
                if it["days_in_state"] is not None else "")
        print(f"- **{it['spec']}** {it['title']} "
              f"[{it['spec_status']}]{days} — `{it['path']}`")
        for t in it["in_review_tickets"]:
            print(f"    - {t['id']}: {t['title']}")
    print()
    print("Review with `tenx show <SPEC-ID>`, then "
          "`tenx ticket <SPEC> <TICKET> done` and "
          "`tenx set <SPEC> status complete`.")
    return 0


def cmd_archive(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    harness = load_harness(root)
    epic = harness.get(args.epic.upper())
    if epic is None or epic.type != "epic":
        print(f"tenx: unknown epic {args.epic}", file=sys.stderr)
        return 2
    specs = harness.specs_for_epic(epic.id)
    open_statuses = ("todo", "in_progress", "in_review")
    blockers = [(s.id, str(t.get("id", "")))
                for s in specs for t in s.tickets
                if str(t.get("status")) in open_statuses]
    approved = str(getattr(args, "approved_by", "") or "").strip()
    if not approved:
        # SPC-023-T14: hard rule — never archive without explicit
        # human/operator approval. An agent must not be able to run
        # this on its own authority.
        msg = (f"tenx: archiving {epic.id} requires explicit operator "
               f"approval. Re-run as: "
               f"tenx archive {epic.id} --approved-by \"<operator name>\"")
        print(msg,
              file=sys.stderr)
        return 2
    if blockers and not args.yes:
        print(f"tenx: {epic.id} has {len(blockers)} open ticket(s):",
              file=sys.stderr)
        for sid, tid in blockers[:10]:
            print(f"  {sid}: {tid}", file=sys.stderr)
        print("finish them first, or pass --yes to archive anyway.",
              file=sys.stderr)
        return 2
    from .activity import append_entry
    from .artifacts import update_meta
    update_meta(epic, {"status": "archived"})
    for s in specs:
        update_meta(s, {"status": "archived"})
    append_entry(root,
                 f"archived {epic.id} ({epic.title}) and "
                 f"{len(specs)} spec(s); approved by {approved}",
                 entry_type="decision", ref=epic.id)
    print(f"archived {epic.id} + {len(specs)} spec(s) "
          f"(approved by {approved}). "
          f"They stay readable via `tenx show`.")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    atype = args.type
    extra: dict[str, Any] = {}
    if atype == "spec":
        if not args.epic:
            print("tenx: specs need --epic EPC-xxx", file=sys.stderr)
            return 2
        extra["epic"] = args.epic.upper()
        harness = load_harness(root)
        if harness.get(args.epic) is None:
            print(f"tenx: unknown epic {args.epic} — create it first",
                  file=sys.stderr)
            return 2
    if args.owner:
        extra["owner"] = args.owner
    if args.tags:
        extra["tags"] = [t.strip() for t in args.tags.split(",") if t.strip()]
    if getattr(args, "priority", None):
        prio = str(args.priority).upper()
        if prio not in PRIORITIES:
            print(f"tenx: priority must be one of {PRIORITIES}",
                  file=sys.stderr)
            return 2
        extra["priority"] = prio
    body = BODY_TEMPLATES.get(atype, "")
    try:
        art = create_artifact(root, atype, args.title, extra_meta=extra,
                              body=body)
    except FileExistsError as exc:
        print(f"tenx: {exc} already exists", file=sys.stderr)
        return 2
    if atype == "convention":
        rebuild_convention_index(root, load_harness(root))
    print(f"Created {art.id}: {art.path}")
    if atype == "spec":
        print("Add tickets to the frontmatter `tickets:` list, then work "
              "them with `tenx ticket`.")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    harness = load_harness(root)
    art = harness.get(args.id)
    if art is None:
        print(f"tenx: no artifact with id {args.id}", file=sys.stderr)
        return 1
    if args.json:
        payload = {
            "meta": art.meta,
            "derived_status": derived_status(art),
            "path": art.rel(root),
            "body": art.body,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return 0
    print(f"# {art.id} — {art.title}")
    print(f"type={art.type} status={art.status} path={art.rel(root)}")
    d = derived_status(art)
    if d and d != art.status:
        print(f"derived_status={d}  ⚠ drift — run tenx validate")
    print()
    print(art.body.strip())
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    harness = load_harness(root)
    types = [args.type] if args.type else list(TYPE_PREFIX)
    items = []
    for t in types:
        for a in harness.by_type(t):
            items.append({
                "id": a.id, "type": a.type, "title": a.title,
                "status": a.status, "priority": a.priority,
                "path": a.rel(root),
            })
    if args.json:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        return 0
    if not items:
        print("No artifacts yet. Create one: tenx new epic \"Title\"")
        return 0
    width = max(len(i["id"]) for i in items)
    for i in items:
        status = f"[{i['status']}]" if i["status"] else ""
        prio = f" {i['priority']}" if i.get("priority") else ""
        print(f"{i['id']:<{width}}  {status:<13}{prio:<4} "
              f"{i['title']}  ({i['path']})")
    return 0


SETTABLE_FIELDS = {"status": STATUSES, "owner": None, "epic": None,
                   "title": None, "tags": None, "priority": PRIORITIES,
                   "evidence": None}


def cmd_set(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    harness = load_harness(root)
    art = harness.get(args.id)
    if art is None:
        print(f"tenx: no artifact with id {args.id}", file=sys.stderr)
        return 1
    field = args.field
    if field not in SETTABLE_FIELDS:
        print(f"tenx: field must be one of {sorted(SETTABLE_FIELDS)}",
              file=sys.stderr)
        return 2
    allowed = SETTABLE_FIELDS[field]
    value: Any = args.value
    if field == "priority":
        value = str(value).upper()
    if allowed and value not in allowed:
        print(f"tenx: {field} must be one of {allowed}", file=sys.stderr)
        return 2
    if field == "epic":
        value = value.upper()
        if harness.get(value) is None:
            print(f"tenx: unknown epic {value}", file=sys.stderr)
            return 2
    if field == "tags":
        value = [t.strip() for t in args.value.split(",") if t.strip()]
    # ---- enforced evidence gate (SPC-015) ------------------------------
    if (field == "status" and value == "complete"
            and art.type in ("spec", "epic") and art.status != "complete"):
        from .gate import check_evidence_gate, gate_enabled
        forced = bool(getattr(args, "force", False))
        if gate_enabled(harness) and not forced:
            rs = validate(root, harness)
            ok, reasons = check_evidence_gate(root, harness, art, rs)
            if not ok:
                print(f"tenx: evidence gate blocked {art.id} -> complete:",
                      file=sys.stderr)
                for r in reasons:
                    print(f"  - {r}", file=sys.stderr)
                # SPC-023-T7: gate blocks leave an audit trail.
                append_entry(root,
                             f"evidence gate BLOCKED {art.id} -> complete: "
                             + "; ".join(reasons),
                             entry_type="blocker", ref=art.id)
                return 2
        elif forced:
            print(f"tenx: --force used — evidence gate bypassed for "
                  f"{art.id} (human override).", file=sys.stderr)
            # SPC-023-T7: forced completions are visible in `tenx history`.
            append_entry(root,
                         f"evidence gate BYPASSED with --force for "
                         f"{art.id} -> complete (human override)",
                         entry_type="decision", ref=art.id)
    update_meta(art, {field: value})
    print(f"{art.id}: {field} = {value}")
    return 0


def cmd_ticket(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    harness = load_harness(root)
    art = harness.get(args.spec)
    if art is None or art.type != "spec":
        print(f"tenx: {args.spec} is not a spec", file=sys.stderr)
        return 1
    if args.status not in TICKET_STATUSES:
        print(f"tenx: ticket status must be one of {list(TICKET_STATUSES)}",
              file=sys.stderr)
        return 2
    tickets = art.meta.get("tickets") or []
    target = None
    for t in tickets:
        if isinstance(t, dict) and str(t.get("id", "")).upper() == args.ticket.upper():
            target = t
            break
    created = False
    if target is None:
        # create-on-first-touch so agents can grow a spec's ticket list
        target = {"id": args.ticket.upper(),
                  "title": args.title or "",
                  "status": args.status}
        tickets.append(target)
        created = True
    old = target.get("status")
    target["status"] = args.status
    if args.title and not target.get("title"):
        target["title"] = args.title
    update_meta(art, {"tickets": tickets})
    # SPC-023-T6: every ticket move leaves a trace in the activity log —
    # skipping ticket tracking is no longer invisible.
    if created:
        append_entry(root,
                     f"ticket {target['id']}: created as {args.status}",
                     entry_type="progress", ref=art.id)
        print(f"{art.id} {target['id']}: created as {args.status}")
    else:
        append_entry(root,
                     f"ticket {target['id']}: {old} -> {args.status}",
                     entry_type="progress", ref=art.id)
        print(f"{art.id} {target['id']}: {old} -> {args.status}")
    d = derived_status(art)
    if d:
        print(f"derived spec status: {d} (authored: {art.status})")
    return 0


def cmd_gate(args: argparse.Namespace) -> int:
    """Commit-time gates. `commit-check`: staged code must have write-back."""
    if getattr(args, "gate_cmd", "") != "commit-check":
        print("tenx: unknown gate command", file=sys.stderr)
        return 2
    root = _root_or_die(args.root)
    _require_init(root)
    harness = load_harness(root)
    from .gate import commit_check, commit_gate_mode
    mode = commit_gate_mode(harness)
    if mode == "off":
        return 0
    ok, message = commit_check(root, harness)
    if ok:
        return 0
    if mode == "warn":
        print(f"tenx commit-gate WARN: {message}", file=sys.stderr)
        return 0
    print(f"tenx commit-gate BLOCKED: {message}", file=sys.stderr)
    return 1


def cmd_validate(args: argparse.Namespace) -> int:
    if getattr(args, "list_rules", False):
        if args.json:
            print(json.dumps(
                [{"rule": rid, "default_severity": sev, "description": desc}
                 for rid, (sev, desc) in RULE_CATALOG.items()],
                indent=2, ensure_ascii=False))
        else:
            sys.stdout.write(list_rules_text())
        return 0
    root = _root_or_die(args.root)
    _require_init(root)
    harness = load_harness(root)
    if args.fix:
        idx = rebuild_convention_index(root, harness)
        print(f"Rebuilt {idx}")
        harness = load_harness(root)
    rs = validate(root, harness)
    if args.json:
        payload = {
            "errors": [f.to_dict() for f in rs.errors()],
            "warnings": [f.to_dict() for f in rs.warnings()],
            "info": [f.to_dict() for f in rs.infos()],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        if not rs.findings:
            print("tenx validate: clean — no errors, warnings, or drift.")
        for f in rs.errors():
            print(f"ERROR   [{f.rule}] {f.message}")
        for f in rs.warnings():
            print(f"WARN    [{f.rule}] {f.message}")
        for f in rs.infos():
            print(f"info    [{f.rule}] {f.message}")
        if rs.findings:
            print(f"\n{len(rs.errors())} error(s), {len(rs.warnings())} "
                  f"warning(s), {len(rs.infos())} info.")
    return 1 if rs.errors() else 0


def cmd_log(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    try:
        entry = append_entry(root, args.message, entry_type=args.type,
                             ref=args.ref, actor=args.actor)
    except ValueError as exc:
        print(f"tenx: {exc}", file=sys.stderr)
        return 2
    print(f"logged [{entry['type']}] {entry['message']}"
          + (f" ({entry['ref']})" if entry.get("ref") else ""))
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    entries = read_entries(root, limit=args.limit)
    if args.json:
        print(json.dumps(entries, indent=2, ensure_ascii=False))
        return 0
    if not entries:
        print("No activity logged yet.")
        return 0
    for e in entries:
        ref = f" ({e['ref']})" if e.get("ref") else ""
        print(f"{e.get('ts', '?')[:16]} [{e.get('type', '?')}]{ref} "
              f"{e.get('message', '')}")
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    if args.json:
        print(json.dumps(compute_next(root), indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render_next(root))
    return 0


def cmd_watchdog(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    window = float(getattr(args, "window", 7) or 7)
    top = int(getattr(args, "top", 5) or 5)
    if args.json:
        print(json.dumps(compute_watchdog(root, window_days=window, top=top),
                         indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render_watchdog(root, window_days=window, top=top))
    return 0


def cmd_triage(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    _require_init(root)
    window = float(getattr(args, "window", 7) or 7)
    top = int(getattr(args, "top", 5) or 5)
    if args.json:
        print(json.dumps(compute_triage(root, window_days=window, top=top),
                         indent=2, ensure_ascii=False))
    else:
        sys.stdout.write(render_triage(root, window_days=window, top=top))
    return 0


def cmd_skills(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    if args.skills_cmd in ("list", "status"):
        print("Bundled skills (install into your agent's skills dir):")
        for name in list_skills():
            print(f"  {name}")
        return 0
    if args.skills_cmd == "install":
        target = Path(args.target) if args.target else root / ".claude" / "skills"
        written = install_skills(target)
        print(f"Installed {len(written)} skills to {target}")
        for p in written:
            print(f"  {p.parent.name}/SKILL.md")
        return 0
    print(f"tenx: unknown skills command {args.skills_cmd}", file=sys.stderr)
    return 2


def cmd_exec(args: argparse.Namespace) -> int:
    """Print an autonomous execution brief for a spec."""
    root = _root_or_die(args.root)
    _require_init(root)
    harness = load_harness(root)
    art = harness.get(args.spec.upper())
    if art is None or art.type != "spec":
        print(f"tenx: {args.spec} is not a spec", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({
            "spec": art.id,
            "title": art.title,
            "status": art.status,
            "tickets": art.tickets,
            "brief": build_exec_brief(harness, art, root),
        }, indent=2))
        return 0
    print(build_exec_brief(harness, art, root))
    return 0


def cmd_hook(args: argparse.Namespace) -> int:
    if args.hook_cmd == "detect":
        from .adapters import ADAPTERS

        found = detect_adapters()
        rows = []
        for a in ADAPTERS:
            hit = found.get(a.id)
            rows.append({"id": a.id, "name": a.name,
                         "detected": bool(hit), "bin": hit,
                         "files": list(a.instruction_files),
                         "hook": a.hook})
        if args.json:
            print(json.dumps(rows, indent=2))
            return 0
        width = max(len(r["id"]) for r in rows)
        print(f"{'ADAPTER':<{width}}  {'STATUS':<9} TARGETS")
        for r in rows:
            status = f"found: {r['bin']}" if r["detected"] else "not found"
            targets = ", ".join(r["files"])
            if r["hook"]:
                targets = f"{r['hook']} + {targets}"
            print(f"{r['id']:<{width}}  {status:<9} {targets}")
        n = sum(1 for r in rows if r["detected"])
        print(f"\n{n}/{len(rows)} harnesses detected on PATH. "
              f"`tenx hook install --agent detected` wires those; "
              f"`--agent all` wires every file-based target.")
        return 0
    if args.hook_cmd == "bootstrap":
        # Harness-agnostic bootstrap: works for ANY agent that can run a
        # shell command. No project root needed.
        sys.stdout.write(bootstrap_snippet() + "\n")
        return 0
    root = _root_or_die(args.root)
    if args.hook_cmd == "install":
        _require_init(root)
        target = code_root(root)
        try:
            results = install_hook(root, args.agent)
        except ValueError as exc:
            print(f"tenx: {exc}", file=sys.stderr)
            return 2
        if getattr(args, "git", False):
            results.append(install_git_hook(target))
        if target != root:
            print(f"  hook target (code repo): {target}")
        for changed, path in results:
            verb = "updated" if changed else "unchanged"
            print(f"  {verb}: {path}")
        print("Session-start context injection is wired. New agent sessions "
              "will boot with the full context packet.")
        return 0
    # emit
    _require_init(root)
    if not getattr(args, "no_log", False):
        from .activity import log_session
        log_session(root)
    if args.json:
        print(json.dumps(build_context(root, args.mode), indent=2,
                         ensure_ascii=False, default=str))
    else:
        sys.stdout.write(render_markdown(root, args.mode,
                                         budget=args.budget))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    initialized = is_initialized(root)
    try:
        import yaml  # noqa: F401
        backend = "PyYAML"
    except ImportError:
        backend = "yamlite"
    data: dict[str, Any] = {
        "version": __version__,
        "python": sys.version.split()[0],
        "project_root": str(root),
        "initialized": initialized,
        "harness_root": str(harness_root(root)),
        "yaml_backend": backend,
    }
    problems: list[str] = []
    if initialized:
        harness = load_harness(root)
        cr = code_root(root, harness.config)
        c = {t: len(harness.by_type(t)) for t in TYPE_PREFIX}
        entries = read_entries(root)
        claude_settings = cr / ".claude" / "settings.json"
        hooked = False
        if claude_settings.is_file():
            hooked = "tenx context" in claude_settings.read_text(
                encoding="utf-8", errors="replace")
        md_hooked = any(
            "tenx:begin" in (cr / f).read_text(encoding="utf-8")
            for f in ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
            if (cr / f).is_file())
        problems = _doctor_enforcement(root, cr, harness)
        rs = validate(root, harness)
        data.update({
            "code_root": str(cr),
            "artifacts": c,
            "activity_entries": len(entries),
            "session_hook": {"claude_settings": hooked,
                             "managed_md_block": md_hooked},
            "validation": {"errors": len(rs.errors()),
                           "warnings": len(rs.warnings())},
        })
    data["enforcement_problems"] = problems
    if getattr(args, "json", False):
        print(json.dumps(data, indent=2))
        return 1 if problems else 0
    print(f"tenx v{data['version']}")
    print(f"python {data['python']}")
    print(f"project root: {root}")
    print(f"harness: {'found' if initialized else 'MISSING (tenx init)'} "
          f"at {harness_root(root)}")
    print(f"yaml backend: {backend}"
          + ("" if backend == "PyYAML"
             else " (PyYAML not installed — fine)"))
    if initialized:
        if data["code_root"] != str(root):
            print(f"code repo (code_root): {data['code_root']}")
        c = data["artifacts"]
        print(f"artifacts: {c['epic']} epics, {c['spec']} specs, "
              f"{c['convention']} conventions, {c['doc']} docs")
        print(f"activity log: {data['activity_entries']} entries")
        sh = data["session_hook"]
        print(f"session hook: claude settings="
              f"{'yes' if sh['claude_settings'] else 'no'}, "
              f"managed md block="
              f"{'yes' if sh['managed_md_block'] else 'no'}")
        print(f"validation: {data['validation']['errors']} errors, "
              f"{data['validation']['warnings']} warnings")
        if problems:
            print("enforcement problems:")
            for p in problems:
                print(f"  ! {p}")
            return 1
        print("enforcement: git gate + agent surfaces all fresh")
    return 0


def _doctor_enforcement(root: Path, cr: Path, harness) -> list[str]:
    """SPC-023-T1: doctor must see enforcement rot, not just marker presence.

    Checks the git pre-commit gate (present/managed/fresh, core.hooksPath
    override), managed-block freshness vs the shipped templates, .mcp.json
    registration, and bundled skills. Returns problem lines, each ending
    in the exact fix command.
    """
    import subprocess

    from .hooks import GIT_HOOK_MARKER, GIT_HOOK_SCRIPT

    problems: list[str] = []

    # -- git pre-commit gate ---------------------------------------------
    git_dir = None
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"], cwd=cr,
            capture_output=True, text=True, timeout=10)
        if probe.returncode == 0 and probe.stdout.strip():
            gd = Path(probe.stdout.strip())
            git_dir = gd if gd.is_absolute() else (cr / gd)
    except (OSError, subprocess.SubprocessError):
        git_dir = None
    if git_dir is None:
        problems.append("no git repository found at the code root — the "
                        "pre-commit gate cannot be installed")
    else:
        try:
            hp = subprocess.run(
                ["git", "config", "core.hooksPath"], cwd=cr,
                capture_output=True, text=True, timeout=10)
            hooks_path = hp.stdout.strip() if hp.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            hooks_path = ""
        hooks_dir = (Path(hooks_path) if hooks_path
                     else git_dir / "hooks")
        if not hooks_dir.is_absolute():
            hooks_dir = cr / hooks_dir
        hook = hooks_dir / "pre-commit"
        if hooks_path:
            problems.append(
                f"git core.hooksPath is set to '{hooks_path}' — tenx's "
                "pre-commit gate in .git/hooks is BYPASSED; unset it "
                "(`git config --unset core.hooksPath`) or install the gate "
                "there (`tenx hook install --git`)")
        if not hook.is_file():
            problems.append("git pre-commit gate MISSING — commits are "
                            "ungated; fix: `tenx hook install --git`")
        else:
            content = hook.read_text(encoding="utf-8", errors="replace")
            if GIT_HOOK_MARKER not in content:
                problems.append("a non-tenx pre-commit hook is installed; "
                                "tenx will not clobber it — chain tenx "
                                "validate into it, or replace it with "
                                "`tenx hook install --git`")
            elif content != GIT_HOOK_SCRIPT:
                problems.append("git pre-commit gate is STALE (older tenx "
                                "version wrote it); fix: "
                                "`tenx hook install --git`")

    # -- managed agent-surface freshness ----------------------------------
    from .hooks import find_stale_surfaces
    stale = find_stale_surfaces(cr)
    if stale:
        problems.append(
            "stale managed instruction file(s): " + ", ".join(stale)
            + " — they predate the current hard-rules template; fix: "
              "`tenx hook install --agent all`")

    # -- MCP registration + bundled skills --------------------------------
    if not (cr / ".mcp.json").is_file():
        problems.append(".mcp.json missing — MCP-capable harnesses get no "
                        "tenx tools; fix: `tenx mcp install`")
    if not (cr / ".claude" / "skills").is_dir():
        problems.append("bundled skills not installed (.claude/skills); "
                        "fix: `tenx skills install`")

    # -- gate configuration (informational problems: none, just report) ---
    from .gate import COMMIT_GATE_CONFIG_KEY, commit_gate_mode
    mode = commit_gate_mode(harness)
    if str(harness.config.get(COMMIT_GATE_CONFIG_KEY, "")).strip() == "off":
        problems.append("commit_gate is OFF in .tenx/config.yaml — commits "
                        "of unlogged code will not even warn")
    return problems


def cmd_update(args: argparse.Namespace) -> int:
    """Check for (and apply) tenx CLI updates.

    Default: check + upgrade if newer. --check: report only, never
    upgrade — this is the session-start form agents should run.
    """
    from .update import check_update
    try:
        info = check_update(__version__)
    except Exception:
        info = {}
    rc = run_update(__version__, check_only=args.check, as_json=args.json)
    if rc == 0 and not args.check and info.get("update_available"):
        _resync_after_upgrade(getattr(args, "root", None))
    return rc


def _resync_after_upgrade(root_arg: str | None) -> None:
    """SPC-023-T8: resync lifecycle.

    After a successful upgrade the on-disk agent surfaces and the git
    pre-commit hook still carry the OLD version's templates. Re-run
    `tenx hook install` with the NEW binary (now on PATH) so the hard
    rules and the gate stay current without anyone remembering. Fail-open:
    a resync problem must never fail `tenx update` itself.
    """
    import subprocess

    from .discovery import find_project_root, is_initialized

    try:
        root = find_project_root(Path(root_arg) if root_arg else None)
    except Exception:
        return
    if root is None or not is_initialized(root):
        return
    print("Resyncing agent surfaces + git gate with the new version...")
    try:
        r = subprocess.run(["tenx", "hook", "install", "--agent",
                            "detected", "--git"], cwd=root, timeout=120)
        if r.returncode != 0:
            print("tenx update: resync reported a problem - run "
                  "`tenx hook install --agent all --git` manually.")
    except (OSError, subprocess.SubprocessError):
        print("tenx update: could not run the resync - run "
              "`tenx hook install --agent all --git` manually.")


def cmd_changelog(args: argparse.Namespace) -> int:
    """Manage the Keep-a-Changelog CHANGELOG.md (docs-sync discipline).

    show (default): print the changelog. add: append an entry to [Unreleased].
    release: stamp [Unreleased] into a dated version and reopen [Unreleased].
    """
    from . import changelog as cl
    root = _root_or_die(args.root)
    _require_init(root)
    action = getattr(args, "action", "show") or "show"
    if action == "show":
        p = cl.changelog_path(root)
        if args.json:
            print(json.dumps(cl.to_dict(root), indent=2))
            return 0
        if not p.exists():
            print("tenx changelog: no CHANGELOG.md yet - run "
                  "`tenx changelog add \"...\"` to start one.")
            return 0
        sys.stdout.write(p.read_text(encoding="utf-8"))
        return 0
    if action == "add":
        if not args.text:
            print("tenx changelog add: provide a message, e.g. "
                  "`tenx changelog add \"shipped X\"`", file=sys.stderr)
            return 2
        sec = cl.add_entry(root, args.text, type=args.type, ref=args.ref)
        typ = next((t for t in cl.TYPES
                    if t.lower() == (args.type or "added").lower()), "Added")
        print(f"changelog: added under [Unreleased]/{typ}: {args.text}")
        return 0
    if action == "release":
        if not args.text:
            print("tenx changelog release: provide a version, e.g. "
                  "`tenx changelog release v0.16.0`", file=sys.stderr)
            return 2
        try:
            sec = cl.release(root, args.text)
        except ValueError as exc:
            print(f"tenx changelog release: {exc}", file=sys.stderr)
            return 2
        print(f"changelog: released [{sec.label}] - {sec.date}; "
              f"reopened [Unreleased]")
        return 0
    print(f"tenx changelog: unknown action {action!r} "
          f"(use show, add, or release)", file=sys.stderr)
    return 2


# ------------------------------------------------------------------ parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tenx",
        description="Meta-harness CLI: context-as-code for AI coding agents.",
    )
    p.add_argument("--version", action="version", version=f"tenx {__version__}")
    p.add_argument("--root", help="project root (default: auto-discover)")
    sub = p.add_subparsers(dest="command")

    sp = sub.add_parser("init", help="scaffold .tenx/ harness")
    sp.add_argument("--name", help="project name (default: directory name)")
    sp.add_argument("--description", help="one-line project description")
    sp.add_argument("--bootstrap", action="store_true",
                    help="seed starter convention + architecture doc")
    sp.add_argument("--standalone", action="store_true",
                    help="this repo is a dedicated PM repo governing a "
                         "separate code repo (the 10X layout)")
    sp.add_argument("--code-root",
                    help="path to the governed code repo (with --standalone)")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--agent", default="detected",
                    help="agent-harness wiring scope: an adapter id, 'all', "
                         "or 'detected' (default: detected + AGENTS.md)")
    sp.add_argument("--no-hooks", action="store_true",
                    help="skip automatic agent-harness wiring "
                         "(instruction files, skills, MCP)")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("context", help="emit context packet")
    sp.add_argument("--mode", choices=["operator", "agent"], default="agent")
    sp.add_argument("--budget", type=int, default=None,
                    help="approx. char budget for the agent packet; "
                         "low-priority sections are truncated/omitted")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_context)

    sp = sub.add_parser("status", help="operator dashboard")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("capabilities",
                        help="capability catalog: every command and "
                             "tool with when-to-use guidance")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_capabilities)

    sp = sub.add_parser("scan", help="map the codebase (stack, tests, CI, "
                                      "agent files, directory census)")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--write", action="store_true",
                    help="upsert the map as a DOC artifact in .tenx/docs/")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("sync", help="two-way sync between spec tickets "
                                     "and GitHub Issues")
    sp.add_argument("direction", choices=["push", "pull"])
    sp.add_argument("--spec", help="limit to one spec (SPC-xxx)")
    sp.add_argument("--dry-run", action="store_true",
                    help="print the plan, touch nothing")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_sync)

    sp = sub.add_parser("mcp", help="MCP server: expose tenx as native "
                                    "tools for MCP-capable harnesses")
    sp.add_argument("mcp_cmd", nargs="?", choices=["serve", "install"],
                    default="serve")
    sp.set_defaults(func=cmd_mcp)

    sp = sub.add_parser("review", help="what awaits review (specs and "
                                       "tickets in_review)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_review)

    sp = sub.add_parser("archive", help="retire a finished epic and its "
                                        "specs")
    sp.add_argument("epic", help="epic id, e.g. EPC-001")
    sp.add_argument("--yes", action="store_true",
                    help="archive even if tickets are still open")
    sp.add_argument("--approved-by", default="",
                    help="REQUIRED: the human/operator who approved the "
                         "archive (hard rule: never archive without "
                         "explicit approval)")
    sp.set_defaults(func=cmd_archive)

    sp = sub.add_parser("new", help="create an artifact")
    sp.add_argument("type", choices=sorted(TYPE_PREFIX))
    sp.add_argument("title")
    sp.add_argument("--epic", help="parent epic id (required for specs)")
    sp.add_argument("--owner")
    sp.add_argument("--tags", help="comma-separated")
    sp.add_argument("--priority", help="business priority tier: P0/P1/P2")
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("show", help="print one artifact")
    sp.add_argument("id")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_show)

    sp = sub.add_parser("list", help="list artifacts")
    sp.add_argument("type", nargs="?", choices=sorted(TYPE_PREFIX))
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("set", help="update artifact metadata")
    sp.add_argument("id")
    sp.add_argument("field", choices=sorted(SETTABLE_FIELDS))
    sp.add_argument("value")
    sp.add_argument("--force", action="store_true",
                    help="bypass the evidence gate on `status complete` "
                         "(human override)")
    sp.set_defaults(func=cmd_set)

    sp = sub.add_parser("ticket", help="move a spec ticket")
    sp.add_argument("spec")
    sp.add_argument("ticket")
    sp.add_argument("status", choices=TICKET_STATUSES)
    sp.add_argument("--title", help="ticket title (used when creating)")
    sp.set_defaults(func=cmd_ticket)

    sp = sub.add_parser("gate", help="commit-time gates")
    gsp = sp.add_subparsers(dest="gate_cmd")
    g = gsp.add_parser("commit-check",
                       help="block/warn when staged code has no write-back")
    g.add_argument("--root", default=None)
    g.set_defaults(func=cmd_gate)
    sp.set_defaults(func=lambda a: 2)

    sp = sub.add_parser("validate", help="lint the SDLC")
    sp.add_argument("--fix", action="store_true",
                    help="apply safe fixes (rebuild convention INDEX.md)")
    sp.add_argument("--list-rules", action="store_true",
                    help="print the rule catalog and exit (no linting)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser("log", help="append to the activity log")
    sp.add_argument("message")
    sp.add_argument("--type", choices=LOG_TYPES, default="progress")
    sp.add_argument("--ref", help="artifact id this work relates to")
    sp.add_argument("--actor", default="agent")
    sp.set_defaults(func=cmd_log)

    sp = sub.add_parser("history", help="show activity log")
    sp.add_argument("--limit", type=int, default=20)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_history)

    sp = sub.add_parser("next", help="most important thing to work on next")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_next)

    sp = sub.add_parser("watchdog",
                        help="top things needing attention + are they handled")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--window", type=float, default=7,
                    help="days that count as 'recent' activity (default 7)")
    sp.add_argument("--top", type=int, default=5,
                    help="max items to show (default 5)")
    sp.set_defaults(func=cmd_watchdog)

    sp = sub.add_parser("triage",
                        help="what needs a human now: act/watch/escalation")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--window", type=float, default=7,
                    help="days that count as 'recent' activity (default 7)")
    sp.add_argument("--top", type=int, default=5,
                    help="max items to consider (default 5)")
    sp.set_defaults(func=cmd_triage)

    sp = sub.add_parser("exec",
                        help="print an autonomous execution brief for a spec")
    sp.add_argument("spec", help="spec ID, e.g. SPC-001")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_exec)

    sp = sub.add_parser("skills", help="manage bundled skills")
    sp.add_argument("skills_cmd", choices=["list", "install", "status"])
    sp.add_argument("--target", help="skills dir (default .claude/skills)")
    sp.set_defaults(func=cmd_skills)

    sp = sub.add_parser("hook", help="session-start hook emit/install")
    sp.add_argument("hook_cmd", nargs="?",
                    choices=["emit", "install", "bootstrap", "detect"],
                    default="emit")
    sp.add_argument("--mode", choices=["operator", "agent"], default="agent")
    from .adapters import AGENT_ALIASES as _AA
    sp.add_argument("--agent",
                    choices=adapter_ids() + sorted(_AA) + ["all", "detected"],
                    default="all",
                    help="adapter id, 'all', or 'detected' (only harnesses "
                         "whose binary is on PATH)")
    sp.add_argument("--budget", type=int, default=None,
                    help="approx. char budget for the emitted packet")
    sp.add_argument("--no-log", action="store_true",
                    help="do not write a throttled session entry on emit")
    sp.add_argument("--git", action="store_true",
                    help="also install the tenx pre-commit gate "
                         "(runs `tenx validate`, blocks commits on errors; "
                         "works on every harness)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_hook)

    sp = sub.add_parser("doctor", help="environment + harness health")
    sp.add_argument("--json", action="store_true",
                    help="machine-readable health report")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("update",
                        help="check for and apply CLI updates "
                             "(agents: run `tenx update --check` at "
                             "session start)")
    sp.add_argument("--check", action="store_true",
                    help="only report whether a newer version exists; "
                         "never upgrade (safe at session start)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_update)

    sp = sub.add_parser("changelog",
                        help="manage the Keep-a-Changelog CHANGELOG.md "
                             "(docs-sync: add an entry when you ship, "
                             "release when you cut a version)")
    sp.add_argument("action", nargs="?", default="show",
                    choices=["show", "add", "release"],
                    help="show (default) | add | release")
    sp.add_argument("text", nargs="?", default=None,
                    help="message for `add`, version for `release`")
    sp.add_argument("--type", default="Added",
                    help="change type for add: added/changed/deprecated/"
                         "removed/fixed/security (default added)")
    sp.add_argument("--ref", default=None,
                    help="artifact ref to tag onto an add entry (e.g. SPC-018)")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_changelog)

    return p


# Commands that write `.tenx` state. They are serialized behind a per-project
# advisory lock so a fleet of concurrent agents cannot lose or corrupt writes.
MUTATING_COMMANDS = {"init", "new", "set", "ticket", "log", "archive",
                     "hook", "skills", "sync", "validate", "changelog",
                     "scan"}  # scan --write rewrites conventions/INDEX.md


def _lock_root(args: argparse.Namespace) -> Path | None:
    """Best-effort project root for locking; None if not resolvable."""
    try:
        explicit = getattr(args, "root", None)
        if explicit:
            return Path(explicit).resolve()
        return env_project_root() or find_project_root()
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    cmd = getattr(args, "command", None)
    lock_root = None
    if cmd in MUTATING_COMMANDS:
        lock_root = _lock_root(args)
        # First `tenx init` has no harness yet; nothing to guard.
        if lock_root is not None and not is_initialized(lock_root):
            lock_root = None
    try:
        if lock_root is not None:
            try:
                with harness_lock(lock_root):
                    return args.func(args)
            except LockTimeout as e:
                print(f"tenx: {e}", file=sys.stderr)
                return 2
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
