"""Validation engine: linting for the SDLC, not just the code.

Rules compare authored state (what artifacts claim) against derived state
(what the rules compute) and report drift, exactly like a linter. The agent
can run `tenx validate` at any time to self-correct.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .activity import log_path, read_entries
from .artifacts import (
    ID_FIND_RE,
    ID_RE,
    REQUIRED_FIELDS,
    PRIORITIES,
    STATUSES,
    TICKET_STATUSES,
    TYPE_DIRS,
    TYPE_PREFIX,
    Artifact,
    Harness,
    derived_status,
    load_harness,
)
from .discovery import harness_root
from .locking import atomic_write_text
from .templates import INDEX_HEADER
from .yamlite import yamlite_load

SEVERITIES = ("error", "warning", "info")

# Single source of truth for every rule `tenx validate` can emit.
# rule id -> (default severity, description). Printed by
# `tenx validate --list-rules`; keep in sync with the _rule_* functions.
RULE_CATALOG: dict[str, tuple[str, str]] = {
    # -- harness / frontmatter -------------------------------------------
    "harness-missing": ("error",
                        "no .tenx/ harness found; run `tenx init` first"),
    "frontmatter-parse": ("error",
                          "artifact frontmatter is not parseable YAML"),
    "frontmatter-required": ("error",
                             "artifact is missing a required frontmatter "
                             "field (id/type/title/status per type)"),
    "type-unknown": ("error",
                     "artifact type is not one of epic/spec/convention/doc"),
    # -- ids --------------------------------------------------------------
    "id-format": ("error",
                  "artifact id must look like EPC-001 / SPC-001 / CON-001 / "
                  "DOC-001"),
    "id-type-mismatch": ("error",
                         "artifact id prefix does not match its type"),
    "id-unique": ("error", "two artifacts share the same id"),
    "id-filename-mismatch": ("warning",
                             "artifact filename does not start with its id "
                             "(manual rename broke navigation)"),
    # -- statuses ---------------------------------------------------------
    "status-valid": ("error",
                     "artifact status missing or not in the allowed "
                     "vocabulary"),
    "dates-monotonic": ("warning",
                        "artifact `updated` date is before its `created` "
                        "date"),
    "priority-format": ("warning",
                        "priority is set but not one of P0/P1/P2 (unset is "
                        "fine; it means normal queue order)"),
    # -- structure refs ---------------------------------------------------
    "epic-ref": ("error",
                 "spec has no epic reference or references an unknown epic"),
    "convention-index": ("warning",
                         "conventions/INDEX.md drifts from the convention "
                         "files (run `tenx validate --fix`)"),
    "convention-empty-body": ("warning",
                              "convention body has too little content to be "
                              "followed (param: min_convention_chars)"),
    "config-code-root": ("error",
                         "config declares a code_root that does not exist"),
    # -- tickets ----------------------------------------------------------
    "ticket-id": ("error", "spec ticket without an id"),
    "ticket-id-unique": ("error", "duplicate ticket id within one spec"),
    "ticket-status-valid": ("error",
                            "ticket status not in todo/in_progress/"
                            "in_review/done/blocked"),
    "ticket-id-prefix": ("warning",
                         "ticket id should be '<SPEC-ID>-T<n>' — GitHub "
                         "sync markers depend on it"),
    "ticket-title-missing": ("info", "ticket has no title"),
    # -- spec/epic discipline ---------------------------------------------
    "orphan-spec": ("warning",
                    "spec is in_progress/in_review/complete but defines no "
                    "tickets"),
    "spec-missing-sections": ("warning",
                              "spec body lacks required sections "
                              "(param: spec_sections, default "
                              "Summary,Validation)"),
    "derived-status-drift": ("warning",
                             "authored spec status disagrees with the status "
                             "derived from its tickets (the 10X checkpoint "
                             "rule; also surfaces as info when all tickets "
                             "are done but the spec is not promoted)"),
    "epic-no-specs": ("info",
                      "active epic has no specs yet"),
    "epic-progress-drift": ("warning",
                            "epic status disagrees with its specs' statuses "
                            "(also surfaces as info when all specs are done "
                            "but the epic is not promoted)"),
    "archived-epic-active-specs": ("warning",
                                   "epic is archived but one or more of its "
                                   "specs are not"),
    # -- time / activity ----------------------------------------------------
    "stale-artifact": ("info",
                       "artifact sat in_review longer than stale_days "
                       "(param: stale_days)"),
    "log-quiet": ("info",
                  "no activity logged for quiet_days (param: quiet_days)"),
    "log-progress-no-ref": ("info",
                            "progress log entry has no artifact ref — "
                            "write-back should reference an artifact"),
    "blocker-unresolved": ("info",
                           "recent blocker log entry has no follow-up "
                           "progress/decision entry (param: blocker_days)"),
}


def list_rules_text() -> str:
    """Human-readable rule catalog for `tenx validate --list-rules`."""
    width = max(len(r) for r in RULE_CATALOG)
    lines = [f"# tenx validate — rule catalog ({len(RULE_CATALOG)} rules)",
             "",
             f"{'RULE':<{width}}  {'DEFAULT':<8} DESCRIPTION"]
    for rid, (sev, desc) in RULE_CATALOG.items():
        lines.append(f"{rid:<{width}}  {sev:<8} {desc}")
    lines.append("")
    lines.append("Override per project in .tenx/rules.yaml: "
                 "`disable: [<rule>]`, `severity: {<rule>: <sev>}`, "
                 "`params: {<name>: <value>}`.")
    return "\n".join(lines) + "\n"


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    artifact_id: str | None = None
    path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "artifact": self.artifact_id,
            "path": self.path,
        }


@dataclass
class RuleSet:
    findings: list[Finding] = field(default_factory=list)
    disabled: set[str] = field(default_factory=set)
    severity_override: dict[str, str] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)

    def add(self, rule: str, severity: str, message: str,
            artifact_id: str | None = None, path: str | None = None) -> None:
        if rule in self.disabled:
            return
        sev = self.severity_override.get(rule, severity)
        if sev not in SEVERITIES:
            sev = severity
        self.findings.append(Finding(rule=rule, severity=sev, message=message,
                                     artifact_id=artifact_id, path=path))

    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "error"]

    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "warning"]

    def infos(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "info"]


def _parse_date(val: Any) -> dt.date | None:
    try:
        return dt.date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def load_rule_config(project_root: Path) -> tuple[set[str], dict[str, str], dict[str, Any]]:
    """Read optional .tenx/rules.yaml overrides plus config.yaml rule params."""
    disabled: set[str] = set()
    overrides: dict[str, str] = {}
    params: dict[str, Any] = {}
    p = harness_root(project_root) / "rules.yaml"
    if p.is_file():
        try:
            cfg = yamlite_load(p.read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}
        for rid in cfg.get("disable") or []:
            disabled.add(str(rid))
        sev_block = cfg.get("severity") or {}
        if isinstance(sev_block, dict):
            for rid, sev in sev_block.items():
                overrides[str(rid)] = str(sev)
        elif isinstance(sev_block, list):
            # also accept the list-of-single-key-map form:
            #   severity:
            #     - stale-artifact: warning
            for item in sev_block:
                if isinstance(item, dict):
                    for rid, sev in item.items():
                        overrides[str(rid)] = str(sev)
        par_block = cfg.get("params") or {}
        if isinstance(par_block, dict):
            params.update(par_block)
    cfg_path = harness_root(project_root) / "config.yaml"
    if cfg_path.is_file():
        try:
            cfg = yamlite_load(cfg_path.read_text(encoding="utf-8")) or {}
            rules_block = cfg.get("rules") or {}
            if isinstance(rules_block, dict):
                for k, v in rules_block.items():
                    params.setdefault(k, v)
        except Exception:
            pass
    return disabled, overrides, params


def validate(project_root: Path, harness: Harness | None = None) -> RuleSet:
    if harness is None:
        harness = load_harness(project_root)
    disabled, overrides, params = load_rule_config(project_root)
    rs = RuleSet(disabled=disabled, severity_override=overrides, params=params)
    root = harness_root(project_root)

    if not root.is_dir():
        rs.add("harness-missing", "error",
               "no .tenx/ harness found; run `tenx init` first")
        return rs

    _rule_frontmatter(project_root, harness, rs)
    _rule_ids(harness, rs)
    _rule_statuses(harness, rs)
    _rule_epic_refs(harness, rs)
    _rule_tickets(harness, rs)
    _rule_spec_sections(harness, rs)
    _rule_derived_drift(harness, rs)
    _rule_epic_drift(harness, rs)
    _rule_convention_index(project_root, harness, rs)
    _rule_convention_body(harness, rs)
    _rule_id_filename(harness, rs)
    _rule_config_code_root(project_root, rs)
    _rule_stale(harness, rs)
    _rule_dates(harness, rs)
    _rule_activity_discipline(project_root, rs)
    _rule_log_quiet(project_root, rs)
    return rs


def _rule_frontmatter(project_root: Path, harness: Harness, rs: RuleSet) -> None:
    for a in harness.artifacts:
        rel = a.rel(project_root)
        if a.parse_error:
            rs.add("frontmatter-parse", "error",
                   f"{a.path.name}: {a.parse_error}", path=rel)
            continue
        missing = [f for f in REQUIRED_FIELDS.get(a.type, [])
                   if a.meta.get(f) in (None, "")]
        if missing:
            rs.add("frontmatter-required", "error",
                   f"{a.id or a.path.name}: missing required field(s): "
                   f"{', '.join(missing)}",
                   artifact_id=a.id or None, path=rel)
        if a.type and a.type not in REQUIRED_FIELDS:
            rs.add("type-unknown", "error",
                   f"{a.path.name}: unknown artifact type '{a.type}'", path=rel)


def _rule_ids(harness: Harness, rs: RuleSet) -> None:
    seen: dict[str, Artifact] = {}
    for a in harness.artifacts:
        if a.parse_error:
            continue
        aid = a.id
        m = ID_RE.match(aid)
        if not m:
            rs.add("id-format", "error",
                   f"{a.path.name}: id '{aid}' must look like "
                   "EPC-001 / SPC-001 / CON-001 / DOC-001",
                   artifact_id=aid or None)
            continue
        expected = TYPE_PREFIX.get(a.type)
        if expected and m.group(1) != expected:
            rs.add("id-type-mismatch", "error",
                   f"{a.path.name}: type '{a.type}' must use prefix {expected}-",
                   artifact_id=aid)
        if aid in seen:
            rs.add("id-unique", "error",
                   f"duplicate id {aid}: {seen[aid].path.name} and {a.path.name}",
                   artifact_id=aid)
        else:
            seen[aid] = a


def _rule_statuses(harness: Harness, rs: RuleSet) -> None:
    for a in harness.artifacts:
        if a.parse_error or a.type not in REQUIRED_FIELDS:
            continue
        required = "status" in REQUIRED_FIELDS[a.type]
        if a.status and a.status not in STATUSES:
            rs.add("status-valid", "error",
                   f"{a.id}: status '{a.status}' not in {list(STATUSES)}",
                   artifact_id=a.id)
        elif required and not a.status:
            rs.add("status-valid", "error",
                   f"{a.id}: missing status", artifact_id=a.id)
        prio = str(a.meta.get("priority", "") or "").strip()
        if prio and prio.upper() not in PRIORITIES:
            rs.add("priority-format", "warning",
                   f"{a.id}: priority '{prio}' not in {list(PRIORITIES)}",
                   artifact_id=a.id)


def _rule_epic_refs(harness: Harness, rs: RuleSet) -> None:
    epic_ids = {a.id for a in harness.by_type("epic")}
    for s in harness.by_type("spec"):
        if s.parse_error:
            continue
        ref = str(s.meta.get("epic", ""))
        if not ref:
            rs.add("epic-ref", "error", f"{s.id}: spec has no epic reference",
                   artifact_id=s.id)
        elif ref not in epic_ids:
            rs.add("epic-ref", "error",
                   f"{s.id}: references unknown epic '{ref}'", artifact_id=s.id)


def _rule_tickets(harness: Harness, rs: RuleSet) -> None:
    for s in harness.by_type("spec"):
        if s.parse_error:
            continue
        seen_tickets: set[str] = set()
        for t in s.tickets:
            tid = str(t.get("id", ""))
            tstat = str(t.get("status", ""))
            if not tid:
                rs.add("ticket-id", "error", f"{s.id}: ticket without id",
                       artifact_id=s.id)
            elif tid in seen_tickets:
                rs.add("ticket-id-unique", "error",
                       f"{s.id}: duplicate ticket id {tid}", artifact_id=s.id)
            else:
                seen_tickets.add(tid)
            if tstat not in TICKET_STATUSES:
                rs.add("ticket-status-valid", "error",
                       f"{s.id}: ticket {tid or '?'} status '{tstat}' "
                       f"not in {list(TICKET_STATUSES)}",
                       artifact_id=s.id)
        if s.status in ("in_progress", "in_review", "complete") and not s.tickets:
            rs.add("orphan-spec", "warning",
                   f"{s.id}: status '{s.status}' but no tickets defined; "
                   "break the spec into tickets so progress is verifiable",
                   artifact_id=s.id)
        # ticket hygiene: traceable ids and titles
        for t in s.tickets:
            tid = str(t.get("id", ""))
            if tid and not tid.startswith(f"{s.id}-T"):
                rs.add("ticket-id-prefix", "warning",
                       f"{s.id}: ticket {tid} should be named "
                       f"'{s.id}-T<n>' (sync markers depend on it)",
                       artifact_id=s.id)
            if tid and not str(t.get("title", "")).strip():
                rs.add("ticket-title-missing", "info",
                       f"{s.id}: ticket {tid} has no title",
                       artifact_id=s.id)


def _rule_spec_sections(harness: Harness, rs: RuleSet) -> None:
    required = [x.strip() for x in str(
        rs.params.get("spec_sections", "Summary,Validation")).split(",")
        if x.strip()]
    for s in harness.by_type("spec"):
        if s.parse_error:
            continue
        missing = [sec for sec in required if f"## {sec}" not in s.body]
        if missing:
            rs.add("spec-missing-sections", "warning",
                   f"{s.id}: body missing required section(s): "
                   + ", ".join(f"'## {m}'" for m in missing),
                   artifact_id=s.id)


def _rule_derived_drift(harness: Harness, rs: RuleSet) -> None:
    """The checkpoint rule: authored status must agree with derived status."""
    for s in harness.by_type("spec"):
        if s.parse_error or not s.tickets:
            continue
        derived = derived_status(s)
        authored = s.status
        if derived is None or authored not in STATUSES:
            continue
        if authored == "complete" and derived != "complete":
            rs.add("derived-status-drift", "warning",
                   f"{s.id}: authored status 'complete' but derived status is "
                   f"'{derived}' (not all tickets are done)", artifact_id=s.id)
        elif authored in ("draft", "in_progress", "in_review") and derived == "complete":
            rs.add("derived-status-drift", "info",
                   f"{s.id}: all tickets done but authored status is "
                   f"'{authored}'; promote it (tenx set {s.id} status complete)",
                   artifact_id=s.id)


def _rule_epic_drift(harness: Harness, rs: RuleSet) -> None:
    for e in harness.by_type("epic"):
        if e.parse_error:
            continue
        specs = harness.specs_for_epic(e.id)
        if not specs:
            if e.status not in ("draft", "archived"):
                rs.add("epic-no-specs", "info",
                       f"{e.id}: epic has no specs yet (status '{e.status}')",
                       artifact_id=e.id)
            continue
        incomplete = sorted(s.id for s in specs if s.status != "complete")
        if e.status == "complete" and incomplete:
            rs.add("epic-progress-drift", "warning",
                   f"{e.id}: epic marked complete but specs not complete: "
                   f"{', '.join(incomplete)}", artifact_id=e.id)
        if e.status in ("draft", "in_review") and not incomplete:
            rs.add("epic-progress-drift", "info",
                   f"{e.id}: all specs complete but epic status is '{e.status}'",
                   artifact_id=e.id)
        if e.status == "archived":
            active = sorted(s.id for s in specs if s.status != "archived")
            if active:
                rs.add("archived-epic-active-specs", "warning",
                       f"{e.id}: epic archived but specs still active: "
                       f"{', '.join(active)}", artifact_id=e.id)


def _rule_convention_index(project_root: Path, harness: Harness, rs: RuleSet) -> None:
    idx_path = harness_root(project_root) / TYPE_DIRS["convention"] / "INDEX.md"
    cons = harness.by_type("convention")
    if not cons:
        return
    if not idx_path.is_file():
        rs.add("convention-index", "warning",
               "conventions exist but conventions/INDEX.md is missing "
               "(run `tenx validate --fix`)", path=str(idx_path))
        return
    text = idx_path.read_text(encoding="utf-8")
    listed = {m.group(0) for m in ID_FIND_RE.finditer(text)}
    actual = {c.id for c in cons}
    for missing in sorted(actual - listed):
        rs.add("convention-index", "warning",
               f"{missing} exists but is not listed in conventions/INDEX.md "
               "(run `tenx validate --fix`)", artifact_id=missing)
    for ghost in sorted(listed - actual):
        rs.add("convention-index", "warning",
               f"INDEX.md lists {ghost} but no such convention file exists",
               path=str(idx_path))


def rebuild_convention_index(project_root: Path, harness: Harness) -> Path:
    idx_path = harness_root(project_root) / TYPE_DIRS["convention"] / "INDEX.md"
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [INDEX_HEADER]
    for c in harness.by_type("convention"):
        status = c.status or "draft"
        lines.append(f"- **{c.id}** — {c.title} `[{status}]` → `{c.path.name}`\n")
    atomic_write_text(idx_path, "".join(lines))
    return idx_path


def _rule_convention_body(harness: Harness, rs: RuleSet) -> None:
    min_chars = int(rs.params.get("min_convention_chars", 40))
    for c in harness.by_type("convention"):
        if c.parse_error:
            continue
        text = "\n".join(
            ln for ln in c.body.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#"))
        if len(text.strip()) < min_chars:
            rs.add("convention-empty-body", "warning",
                   f"{c.id}: convention body has < {min_chars} chars of "
                   "content; a convention with no substance cannot be "
                   "followed", artifact_id=c.id)


def _rule_id_filename(harness: Harness, rs: RuleSet) -> None:
    for a in harness.artifacts:
        if a.parse_error or not a.id:
            continue
        if not a.path.name.startswith(a.id):
            rs.add("id-filename-mismatch", "warning",
                   f"{a.id}: filename '{a.path.name}' does not start "
                   "with the artifact id", artifact_id=a.id)


def _rule_config_code_root(project_root: Path, rs: RuleSet) -> None:
    cfg_path = harness_root(project_root) / "config.yaml"
    if not cfg_path.is_file():
        return
    try:
        cfg = yamlite_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return
    code_root_val = cfg.get("code_root")
    if not code_root_val:
        return  # co-located harness: nothing to check
    cr = Path(str(code_root_val)).expanduser()
    if not cr.is_absolute():
        cr = (project_root / cr)
    if not cr.resolve().is_dir():
        rs.add("config-code-root", "error",
               f"config code_root '{code_root_val}' does not exist "
               "(discovery silently falls back to the harness host)",
               path=str(cfg_path))


def _rule_activity_discipline(project_root: Path, rs: RuleSet) -> None:
    p = log_path(project_root)
    if not p.is_file():
        return
    entries = read_entries(project_root)
    if not entries:
        return
    # log-progress-no-ref: write-back should point at an artifact
    for e in entries:
        if str(e.get("type", "")) == "progress" and not str(e.get("ref", "")).strip():
            rs.add("log-progress-no-ref", "info",
                   f"progress entry '{str(e.get('message', ''))[:50]}' has "
                   "no ref; write-back should reference an artifact")
    # blocker-unresolved: blocker with no later progress/decision on same ref
    blocker_days = int(rs.params.get("blocker_days", 14))
    now = dt.datetime.now(dt.timezone.utc)
    for i, e in enumerate(entries):
        if str(e.get("type", "")) != "blocker":
            continue
        try:
            ts = dt.datetime.fromisoformat(str(e.get("ts", "")))
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=dt.timezone.utc)
        if now - ts > dt.timedelta(days=blocker_days):
            continue
        ref = str(e.get("ref", ""))
        resolved = any(
            str(later.get("type", "")) in ("progress", "decision")
            and (not ref or str(later.get("ref", "")) == ref)
            for later in entries[i + 1:])
        if not resolved:
            rs.add("blocker-unresolved", "info",
                   f"blocker logged {str(e.get('ts', ''))[:10]}"
                   + (f" on {ref}" if ref else "")
                   + " has no follow-up progress/decision entry yet")


def _rule_stale(harness: Harness, rs: RuleSet) -> None:
    stale_days = int(rs.params.get("stale_days", 14))
    cutoff = dt.date.today() - dt.timedelta(days=stale_days)
    for a in harness.artifacts:
        if a.parse_error or a.status != "in_review":
            continue
        upd = _parse_date(a.meta.get("updated"))
        if upd and upd < cutoff:
            rs.add("stale-artifact", "info",
                   f"{a.id}: in_review for over {stale_days} days without update",
                   artifact_id=a.id)


def _rule_dates(harness: Harness, rs: RuleSet) -> None:
    for a in harness.artifacts:
        if a.parse_error:
            continue
        created = _parse_date(a.meta.get("created"))
        updated = _parse_date(a.meta.get("updated"))
        if created and updated and updated < created:
            rs.add("dates-monotonic", "warning",
                   f"{a.id}: updated ({updated}) is before created ({created})",
                   artifact_id=a.id)


def _rule_log_quiet(project_root: Path, rs: RuleSet) -> None:
    quiet_days = int(rs.params.get("quiet_days", 7))
    p = log_path(project_root)
    if not p.is_file():
        return
    entries = read_entries(project_root)
    if not entries:
        return
    last = entries[-1].get("ts", "")
    try:
        ts = dt.datetime.fromisoformat(str(last))
    except ValueError:
        return
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    age = dt.datetime.now(dt.timezone.utc) - ts
    if age > dt.timedelta(days=quiet_days):
        rs.add("log-quiet", "info",
               f"no activity logged for {age.days} days; agents should "
               "`tenx log` after significant work")
