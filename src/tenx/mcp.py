"""tenx mcp — Model Context Protocol server on stdio.

Newline-delimited JSON-RPC 2.0. Zero dependencies (stdlib only).
Tools reuse the existing CLI command functions by capturing their
stdout — no logic duplication, no subprocesses.

Run with `tenx mcp` from a project directory (or pass --root).
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sys
from typing import Any, Callable

from . import __version__

PROTOCOL_VERSION = "2025-03-26"
KNOWN_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")

SERVER_INFO = {"name": "tenx", "version": __version__}


# ------------------------------------------------------------ tool layer

def _call_cli(func: Callable[..., int], *, lock: bool = False,
              **attrs: Any) -> tuple[str, int]:
    """Run a cmd_* function, capturing stdout+stderr. Returns (text, rc).

    lock=True serializes the call behind the same per-project advisory
    lock the CLI main() uses (SPC-023-T11): MCP tools must not race
    concurrent agents around `.tenx` writes.
    """
    # SPC-023-T11: callers may pass root explicitly (MCP clients name the
    # project); default to auto-discovery without colliding with attrs.
    ns = argparse.Namespace(**{"root": None, **attrs})
    out, err = io.StringIO(), io.StringIO()
    rc = 0

    def run() -> int:
        try:
            return func(ns)
        except SystemExit as e:
            return int(e.code or 0)

    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        if lock:
            from . import cli as C
            root = C._lock_root(ns)
            if root is not None and C.is_initialized(root):
                try:
                    with C.harness_lock(root):
                        rc = run()
                except C.LockTimeout as e:
                    print(f"tenx: {e}", file=sys.stderr)
                    rc = 2
            else:
                rc = run()
        else:
            rc = run()
    text = out.getvalue()
    if err.getvalue().strip():
        text = (text + "\n" if text else "") + err.getvalue()
    return text.rstrip("\n"), rc


def _tooldefs() -> list[dict[str, Any]]:
    """Tool registry: name, description, inputSchema, cmd factory."""
    from . import cli as C

    # SPC-023-T11: tools that write `.tenx` state take the same advisory
    # lock as the CLI, so MCP-driven fleets cannot lose or corrupt writes.
    mutating = {C.cmd_ticket, C.cmd_log, C.cmd_validate, C.cmd_scan,
                C.cmd_changelog}

    def mk(func, defaults: dict[str, Any]):
        def handler(args: dict[str, Any]) -> tuple[str, int]:
            kw = {**defaults, **{k: v for k, v in args.items()
                                 if v is not None}}
            return _call_cli(func, lock=(func in mutating), **kw)
        return handler

    def _converge_handler(args: dict[str, Any]) -> tuple[str, int]:
        # SPC-026: lock depends on the call, not the tool — the report is
        # read-only, append writes tickets. MCP is a machine interface, so
        # the answer is always JSON; rc keeps CLI semantics (isError is
        # set on nonzero rc but the report is still delivered).
        kw = {"json": True, "append": False,
              **{k: v for k, v in args.items() if v is not None}}
        return _call_cli(C.cmd_converge, lock=bool(args.get("append")),
                         **kw)

    S = {"type": "string"}
    B = {"type": "boolean"}
    return [
        {"name": "tenx_context",
         "description": "Emit the tenx context packet (project state, "
                        "specs, conventions, activity, operating "
                        "protocol). Run this first in any session.",
         "inputSchema": {"type": "object", "properties": {
             "mode": {"type": "string", "enum": ["agent", "operator"],
                      "description": "agent (default) or operator"},
             "budget": {"type": "integer",
                        "description": "optional char budget"}}},
         "handler": mk(C.cmd_context, {"mode": "agent", "json": False})},
        {"name": "tenx_next",
         "description": "Prioritized work queue: the highest-value "
                        "ticket to implement next.",
         "inputSchema": {"type": "object", "properties": {}},
         "handler": mk(C.cmd_next, {"json": False})},
        {"name": "tenx_watchdog",
         "description": "Pulse-check digest: the top things needing "
                        "attention, each cross-referenced with recent "
                        "activity to say whether it is being handled. "
                        "Run after tenx_context to spot stalled or "
                        "blocked work.",
         "inputSchema": {"type": "object", "properties": {
             "window": {"type": "number",
                        "description": "days that count as recent "
                                       "activity (default 7)"},
             "top": {"type": "integer",
                     "description": "max items to show (default 5)"}}},
         "handler": mk(C.cmd_watchdog, {"json": False, "window": 7,
                                        "top": 5})},
        {"name": "tenx_triage",
         "description": "Escalation digest for a human: classifies the "
                        "current attention items into act-now / watch / "
                        "healthy and picks the single most important "
                        "thing needing a human decision. Read-only.",
         "inputSchema": {"type": "object", "properties": {
             "window": {"type": "number",
                        "description": "days that count as recent "
                                       "activity (default 7)"},
             "top": {"type": "integer",
                     "description": "max items to consider (default 5)"}}},
         "handler": mk(C.cmd_triage, {"json": False, "window": 7,
                                      "top": 5})},
        {"name": "tenx_status",
         "description": "Operator dashboard: artifact counts, statuses, "
                        "recent activity.",
         "inputSchema": {"type": "object", "properties": {}},
         "handler": mk(C.cmd_status, {"json": False})},
        {"name": "tenx_show",
         "description": "Show one artifact (epic/spec/convention/doc) "
                        "by ID, including full body.",
         "inputSchema": {"type": "object", "properties": {
             "id": {**S, "description": "artifact id, e.g. SPC-002"}},
             "required": ["id"]},
         "handler": mk(C.cmd_show, {"json": False})},
        {"name": "tenx_list",
         "description": "List artifacts, optionally filtered by type.",
         "inputSchema": {"type": "object", "properties": {
             "type": {"type": "string",
                      "enum": ["epic", "spec", "convention", "doc"]}}},
         "handler": mk(C.cmd_list, {"type": None, "json": False})},
        {"name": "tenx_ticket",
         "description": "Set a spec ticket's status (creates on first "
                        "touch). Statuses: todo, in_progress, in_review, "
                        "done, blocked.",
         "inputSchema": {"type": "object", "properties": {
             "spec": {**S, "description": "spec id, e.g. SPC-002"},
             "ticket": {**S, "description": "ticket id, e.g. SPC-002-T1"},
             "status": {"type": "string",
                        "enum": ["todo", "in_progress", "in_review",
                                 "done", "blocked"]},
             "title": {**S, "description": "title when creating"}},
             "required": ["spec", "ticket", "status"]},
         "handler": mk(C.cmd_ticket, {"title": None})},
        {"name": "tenx_log",
         "description": "Write back to the activity log after "
                        "significant work.",
         "inputSchema": {"type": "object", "properties": {
             "message": {**S, "description": "one line: what changed"},
             "ref": {**S, "description": "artifact id, e.g. SPC-002"},
             "type": {"type": "string",
                      "enum": ["note", "progress", "decision", "blocker",
                               "review"]}},
             "required": ["message"]},
         "handler": mk(C.cmd_log, {"ref": None, "type": "progress",
                                   "actor": "agent"})},
        {"name": "tenx_validate",
         "description": "Lint the SDLC: drift between authored and "
                        "derived status, broken refs, stale artifacts.",
         "inputSchema": {"type": "object", "properties": {
             "fix": {**B, "description": "rebuild the convention index"}}},
         "handler": mk(C.cmd_validate, {"fix": False, "json": False})},
        {"name": "tenx_scan",
         "description": "Map the codebase: stacks, entry hints, tests, "
                        "CI, agent files, directory census.",
         "inputSchema": {"type": "object", "properties": {
             "write": {**B, "description": "store map as a DOC artifact"}}},
         "handler": mk(C.cmd_scan, {"json": False, "write": False})},
        {"name": "tenx_exec",
         "description": "Execution brief for a spec: everything an agent "
                        "needs to implement it ticket by ticket.",
         "inputSchema": {"type": "object", "properties": {
             "spec": {**S, "description": "spec id, e.g. SPC-002"}},
             "required": ["spec"]},
         "handler": mk(C.cmd_exec, {"json": False})},
        {"name": "tenx_ticket_brief",
         "description": "Scoped execution brief for a single ticket: "
                        "extracts only the ticket task, matching spec "
                        "requirements, conventions, and test commands "
                        "to preserve supervisor context.",
         "inputSchema": {"type": "object", "properties": {
             "spec": {**S, "description": "spec id, e.g. SPC-001"},
             "ticket": {**S, "description": "ticket id, e.g. SPC-001-T1"}},
             "required": ["spec", "ticket"]},
         "handler": mk(C.cmd_ticket_brief, {"json": False})},
        {"name": "tenx_dispatch",
         "description": "Dispatch a ticket to an isolated worker in a "
                        "git worktree: handles worktree creation, runner "
                        "command execution, visual multiplexer projection "
                        "(Herdr workspace / tmux window), and structured outcome receipt.",
         "inputSchema": {"type": "object", "properties": {
             "spec": {**S, "description": "spec id, e.g. SPC-001"},
             "ticket": {**S, "description": "ticket id, e.g. SPC-001-T1"},
             "agent": {"type": "string",
                       "description": "agent harness: pi, codex, prime, claude, grok, dsh (default pi)"},
             "visual": {**B, "description": "project subagent visually into active terminal multiplexer (Herdr workspace/tab, tmux window)"},
             "multiplexer": {"type": "string", "enum": ["auto", "herdr", "tmux", "none"],
                             "description": "multiplexer adapter (default auto)"},
             "focus": {**B, "description": "focus the newly created multiplexer window/workspace (default false)"},
             "dry_run": {**B, "description": "inspect worktree and command without executing"},
             "timeout": {"type": "integer", "description": "timeout in seconds"}},
             "required": ["spec", "ticket"]},
         "handler": mk(C.cmd_dispatch, {"agent": "pi", "visual": False, "multiplexer": "auto", "focus": False, "dry_run": False, "timeout": 600, "json": False})},
        {"name": "tenx_changelog",
         "description": "Docs-sync: manage the Keep-a-Changelog "
                        "CHANGELOG.md. action=show prints it; action=add "
                        "appends an entry to [Unreleased] (pass text, "
                        "optional type/ref); action=release stamps "
                        "[Unreleased] into a dated version (pass "
                        "text=version). Add an entry whenever you ship "
                        "work - the evidence gate requires one before a "
                        "spec/epic can be completed.",
         "inputSchema": {"type": "object", "properties": {
             "action": {"type": "string",
                        "enum": ["show", "add", "release"],
                        "description": "show (default) | add | release"},
             "text": {**S,
                      "description": "message for add, version for release"},
             "type": {"type": "string",
                      "enum": ["added", "changed", "deprecated", "removed",
                               "fixed", "security"],
                      "description": "change type for add (default added)"},
             "ref": {**S,
                     "description": "artifact ref to tag onto an add entry"}}},
         "handler": mk(C.cmd_changelog, {"action": "show", "text": None,
                                         "type": "Added", "ref": None,
                                         "json": False})},
        {"name": "tenx_capabilities",
         "description": "Capability catalog: every tenx command and "
                        "tool with when-to-use guidance. Call this once "
                        "when you first work in a tenx-governed project "
                        "to learn what tenx can do and when to use it.",
         "inputSchema": {"type": "object", "properties": {}},
         "handler": mk(C.cmd_capabilities, {"json": False})},
        {"name": "tenx_converge",
         "description": "Spec convergence check (SPC-026): deterministic "
                        "FR-### vs tickets report for one spec, as JSON. "
                        "rc 0 = CONVERGED, 1 = NOT CONVERGED (report "
                        "still delivered), 2 = bad spec id. Run before "
                        "marking a spec complete. With append=true, "
                        "creates missing tickets (append-only, takes the "
                        "harness lock).",
         "inputSchema": {"type": "object", "properties": {
             "spec_id": {**S, "description": "spec id, e.g. SPC-001"},
             "append": {**B,
                        "description": "create todo tickets for "
                                       "uncovered FR-### (default "
                                       "false)"}},
             "required": ["spec_id"]},
         "handler": _converge_handler},
    ]


# ---------------------------------------------------------- json-rpc layer

def _result(id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _error(id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id,
            "error": {"code": code, "message": message}}


class McpServer:
    def __init__(self) -> None:
        self.tools = _tooldefs()
        self._by_name = {t["name"]: t for t in self.tools}

    # -- methods ---------------------------------------------------------
    def handle(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        method = msg.get("method")
        id_ = msg.get("id")
        params = msg.get("params") or {}
        is_notification = "id" not in msg

        if method == "initialize":
            client_ver = str(params.get("protocolVersion", ""))
            negotiated = (client_ver if client_ver in KNOWN_VERSIONS
                          else PROTOCOL_VERSION)
            return _result(id_, {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            })
        if method in ("notifications/initialized",
                      "notifications/cancelled"):
            return None
        if method == "ping":
            return _result(id_, {})
        if method == "tools/list":
            return _result(id_, {"tools": [
                {"name": t["name"], "description": t["description"],
                 "inputSchema": t["inputSchema"]}
                for t in self.tools]})
        if method == "tools/call":
            name = params.get("name", "")
            tool = self._by_name.get(name)
            if tool is None:
                return _result(id_, {
                    "content": [{"type": "text",
                                 "text": f"unknown tool: {name}"}],
                    "isError": True})
            try:
                text, rc = tool["handler"](params.get("arguments") or {})
            except Exception as exc:  # never crash the server
                return _result(id_, {
                    "content": [{"type": "text",
                                 "text": f"tool error: {exc!r}"}],
                    "isError": True})
            return _result(id_, {
                "content": [{"type": "text", "text": text or "(no output)"}],
                "isError": rc != 0})
        if is_notification:
            return None
        return _error(id_, -32601, f"method not found: {method}")

    # -- transport -------------------------------------------------------
    def serve(self, stdin=None, stdout=None) -> None:
        stdin = stdin or sys.stdin
        stdout = stdout or sys.stdout
        for line in stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                if not isinstance(msg, dict):
                    raise ValueError("not an object")
            except (json.JSONDecodeError, ValueError):
                self._write(stdout, _error(None, -32700, "parse error"))
                continue
            try:
                resp = self.handle(msg)
            except Exception as exc:  # defensive: keep serving
                resp = _error(msg.get("id"), -32603, f"internal: {exc!r}")
            if resp is not None:
                self._write(stdout, resp)

    @staticmethod
    def _write(stdout, payload: dict[str, Any]) -> None:
        stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        stdout.flush()
