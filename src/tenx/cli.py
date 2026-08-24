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
  tenx skills list|install         bundled skills per artifact type
  tenx hook [--mode agent]         emit the session-start packet
  tenx hook install [--agent X]    wire packet into claude/codex/opencode/gemini
  tenx doctor                      environment + harness health check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .activity import TYPES as LOG_TYPES, append_entry, read_entries
from .artifacts import (
    STATUSES,
    TICKET_STATUSES,
    TYPE_PREFIX,
    create_artifact,
    derived_status,
    load_harness,
    update_meta,
)
from .context import build_context, render_markdown
from .discovery import env_project_root, find_project_root, harness_root, is_initialized
from .hooks import install as install_hook
from .nextup import compute_next, render_next
from .rules import rebuild_convention_index, validate
from .skills import install_skills, list_skills
from .templates import BODY_TEMPLATES, CONFIG_TEMPLATE, HARNESS_README
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
        return 0
    name = args.name or root.name
    desc = args.description or f"Context base for {name}"
    for sub in ("epics", "specs", "conventions", "docs", "log"):
        (hroot / sub).mkdir(parents=True, exist_ok=True)
    cfg = hroot / "config.yaml"
    if not cfg.exists() or args.force:
        cfg.write_text(CONFIG_TEMPLATE.format(project=name, description=desc),
                       encoding="utf-8")
    readme = hroot / "README.md"
    if not readme.exists():
        readme.write_text(HARNESS_README, encoding="utf-8")
    print(f"Initialized tenx harness at {hroot}")
    print("  config.yaml, epics/, specs/, conventions/, docs/, log/")

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
    print("\nNext steps:")
    print(f'  tenx new epic "What we are building next"')
    print("  tenx hook install --agent claude   # or codex/opencode/gemini/all")
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
    if args.json:
        data = build_context(root, mode)
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        sys.stdout.write(render_markdown(root, mode))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    args.mode = "operator"
    return cmd_context(args)


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
                "status": a.status, "path": a.rel(root),
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
        print(f"{i['id']:<{width}}  {status:<13} {i['title']}  ({i['path']})")
    return 0


SETTABLE_FIELDS = {"status": STATUSES, "owner": None, "epic": None,
                   "title": None, "tags": None}


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
    if target is None:
        print(f"tenx: no ticket {args.ticket} in {art.id}", file=sys.stderr)
        return 1
    old = target.get("status")
    target["status"] = args.status
    update_meta(art, {"tickets": tickets})
    print(f"{art.id} {target['id']}: {old} -> {args.status}")
    d = derived_status(art)
    if d:
        print(f"derived spec status: {d} (authored: {art.status})")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
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


def cmd_hook(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    if args.hook_cmd == "install":
        _require_init(root)
        try:
            results = install_hook(root, args.agent)
        except ValueError as exc:
            print(f"tenx: {exc}", file=sys.stderr)
            return 2
        for changed, path in results:
            verb = "updated" if changed else "unchanged"
            print(f"  {verb}: {path}")
        print("Session-start context injection is wired. New agent sessions "
              "will boot with the full context packet.")
        return 0
    # emit
    _require_init(root)
    if args.json:
        print(json.dumps(build_context(root, args.mode), indent=2,
                         ensure_ascii=False, default=str))
    else:
        sys.stdout.write(render_markdown(root, args.mode))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    root = _root_or_die(args.root)
    print(f"tenx v{__version__}")
    print(f"python {sys.version.split()[0]}")
    print(f"project root: {root}")
    initialized = is_initialized(root)
    print(f"harness: {'found' if initialized else 'MISSING (tenx init)'} "
          f"at {harness_root(root)}")
    try:
        import yaml  # noqa: F401
        print("yaml backend: PyYAML")
    except ImportError:
        print("yaml backend: built-in yamlite (PyYAML not installed — fine)")
    if initialized:
        harness = load_harness(root)
        c = {t: len(harness.by_type(t)) for t in TYPE_PREFIX}
        print(f"artifacts: {c['epic']} epics, {c['spec']} specs, "
              f"{c['convention']} conventions, {c['doc']} docs")
        entries = read_entries(root)
        print(f"activity log: {len(entries)} entries")
        claude_settings = root / ".claude" / "settings.json"
        hooked = False
        if claude_settings.is_file():
            hooked = "tenx context" in claude_settings.read_text(
                encoding="utf-8", errors="replace")
        md_hooked = any(
            "tenx:begin" in (root / f).read_text(encoding="utf-8")
            for f in ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
            if (root / f).is_file())
        print(f"session hook: claude settings={'yes' if hooked else 'no'}, "
              f"managed md block={'yes' if md_hooked else 'no'}")
        rs = validate(root, harness)
        print(f"validation: {len(rs.errors())} errors, "
              f"{len(rs.warnings())} warnings")
    return 0


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
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("context", help="emit context packet")
    sp.add_argument("--mode", choices=["operator", "agent"], default="agent")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_context)

    sp = sub.add_parser("status", help="operator dashboard")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("new", help="create an artifact")
    sp.add_argument("type", choices=sorted(TYPE_PREFIX))
    sp.add_argument("title")
    sp.add_argument("--epic", help="parent epic id (required for specs)")
    sp.add_argument("--owner")
    sp.add_argument("--tags", help="comma-separated")
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
    sp.set_defaults(func=cmd_set)

    sp = sub.add_parser("ticket", help="move a spec ticket")
    sp.add_argument("spec")
    sp.add_argument("ticket")
    sp.add_argument("status", choices=TICKET_STATUSES)
    sp.set_defaults(func=cmd_ticket)

    sp = sub.add_parser("validate", help="lint the SDLC")
    sp.add_argument("--fix", action="store_true",
                    help="apply safe fixes (rebuild convention INDEX.md)")
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

    sp = sub.add_parser("skills", help="manage bundled skills")
    sp.add_argument("skills_cmd", choices=["list", "install", "status"])
    sp.add_argument("--target", help="skills dir (default .claude/skills)")
    sp.set_defaults(func=cmd_skills)

    sp = sub.add_parser("hook", help="session-start hook emit/install")
    sp.add_argument("hook_cmd", nargs="?", choices=["emit", "install"],
                    default="emit")
    sp.add_argument("--mode", choices=["operator", "agent"], default="agent")
    sp.add_argument("--agent",
                    choices=["claude", "codex", "opencode", "gemini", "all"],
                    default="all")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_hook)

    sp = sub.add_parser("doctor", help="environment + harness health")
    sp.set_defaults(func=cmd_doctor)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
