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

def _call_cli(func: Callable[..., int], **attrs: Any) -> tuple[str, int]:
    """Run a cmd_* function, capturing stdout+stderr. Returns (text, rc)."""
    ns = argparse.Namespace(root=None, **attrs)
    out, err = io.StringIO(), io.StringIO()
    rc = 0
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = func(ns)
    except SystemExit as e:
        rc = int(e.code or 0)
    text = out.getvalue()
    if err.getvalue().strip():
        text = (text + "\n" if text else "") + err.getvalue()
    return text.rstrip("\n"), rc


def _tooldefs() -> list[dict[str, Any]]:
    """Tool registry: name, description, inputSchema, cmd factory."""
    from . import cli as C

    def mk(func, defaults: dict[str, Any]):
        def handler(args: dict[str, Any]) -> tuple[str, int]:
            kw = {**defaults, **{k: v for k, v in args.items()
                                 if v is not None}}
            return _call_cli(func, **kw)
        return handler

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
