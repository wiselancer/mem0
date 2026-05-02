#!/usr/bin/env python3
"""Small stdio MCP bridge for the self-hosted Mem0 REST server.

The open-source Mem0 REST server does not expose the hosted mcp.mem0.ai
endpoint. This bridge gives local agents the same basic memory tools while
keeping the memory store on the user's own Mem0 deployment.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


SERVER_NAME = "mem0-self-hosted"
SERVER_VERSION = "0.1.0"
DEFAULT_API_URL = "https://api.mem.petrenko.cv"


def _env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback).strip()


def api_url() -> str:
    return _env("MEM0_SELF_HOSTED_API_URL", _env("MEM0_API_URL", DEFAULT_API_URL)).rstrip("/")


def api_key() -> str:
    return _env("MEM0_SELF_HOSTED_API_KEY", _env("MEM0_API_KEY", ""))


def default_user_id() -> str:
    return _env("MEM0_USER_ID", _env("USER", "default"))


def default_agent_id() -> str:
    return _env("MEM0_AGENT_ID", "agent")


def default_run_id() -> str:
    configured = _env("MEM0_RUN_ID", _env("MEM0_PROJECT_ID", ""))
    if configured:
        return configured

    cwd = os.getcwd()
    try:
        root = subprocess.check_output(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2,
        ).strip()
        if root:
            return os.path.basename(root)
    except Exception:
        pass

    return os.path.basename(os.path.abspath(cwd)) if cwd else ""


def read_message() -> dict[str, Any] | None:
    headers: dict[str, str] = {}

    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, _, value = line.decode("ascii", errors="replace").partition(":")
        headers[key.lower()] = value.strip()

    length = int(headers.get("content-length", "0"))
    if length <= 0:
        return None
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


def write_message(payload: dict[str, Any]) -> None:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()


def rpc_result(message_id: Any, result: dict[str, Any]) -> None:
    write_message({"jsonrpc": "2.0", "id": message_id, "result": result})


def rpc_error(message_id: Any, code: int, message: str) -> None:
    write_message({"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}})


def rest_request(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    key = api_key()
    if not key:
        raise RuntimeError("MEM0_SELF_HOSTED_API_KEY or MEM0_API_KEY is not set")

    data = None
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-API-Key": key,
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(f"{api_url()}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Mem0 API returned HTTP {exc.code}: {detail}") from exc


def content_text(value: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, indent=2)}], "isError": False}


def tool_schema() -> list[dict[str, Any]]:
    user_scope = {
        "user_id": {"type": "string", "description": "Mem0 user id. Defaults to MEM0_USER_ID or system user."},
        "agent_id": {"type": "string", "description": "Optional Mem0 agent id."},
        "run_id": {"type": "string", "description": "Optional Mem0 run id."},
    }

    return [
        {
            "name": "add_memory",
            "description": "Store a durable memory in the self-hosted Mem0 server.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "memory": {"type": "string", "description": "Memory text to store."},
                    "metadata": {"type": "object", "description": "Optional JSON metadata."},
                    "infer": {"type": "boolean", "description": "Whether Mem0 should extract facts. Defaults to false."},
                    **user_scope,
                },
                "required": ["memory"],
            },
        },
        {
            "name": "search_memories",
            "description": "Search self-hosted Mem0 for relevant memories.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query."},
                    "top_k": {"type": "integer", "description": "Maximum results. Defaults to 5."},
                    "filters": {"type": "object", "description": "Optional Mem0 filters."},
                    **user_scope,
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_memories",
            "description": "List memories for a user, agent, or run.",
            "inputSchema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "description": "Maximum results."}, **user_scope},
            },
        },
        {
            "name": "get_memory",
            "description": "Retrieve one memory by id.",
            "inputSchema": {
                "type": "object",
                "properties": {"memory_id": {"type": "string"}},
                "required": ["memory_id"],
            },
        },
        {
            "name": "update_memory",
            "description": "Update one memory by id.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string"},
                    "memory": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["memory_id", "memory"],
            },
        },
        {
            "name": "delete_memory",
            "description": "Delete one memory by id.",
            "inputSchema": {
                "type": "object",
                "properties": {"memory_id": {"type": "string"}},
                "required": ["memory_id"],
            },
        },
        {
            "name": "delete_all_memories",
            "description": "Delete all memories matching a user, agent, or run scope.",
            "inputSchema": {"type": "object", "properties": user_scope},
        },
    ]


def scoped_args(args: dict[str, Any]) -> dict[str, Any]:
    scoped: dict[str, Any] = {}
    for key in ("user_id", "agent_id", "run_id"):
        if args.get(key):
            scoped[key] = args[key]
    if not scoped:
        scoped["user_id"] = default_user_id()
    return scoped


def write_scope(args: dict[str, Any]) -> dict[str, Any]:
    scoped = {"user_id": args.get("user_id") or default_user_id()}
    agent_id = args.get("agent_id") or default_agent_id()
    run_id = args.get("run_id") or default_run_id()
    if agent_id:
        scoped["agent_id"] = agent_id
    if run_id:
        scoped["run_id"] = run_id
    return scoped


def call_tool(name: str, args: dict[str, Any]) -> Any:
    if name == "add_memory":
        body = {
            "messages": [{"role": "user", "content": args["memory"]}],
            "metadata": args.get("metadata"),
            "infer": args.get("infer", False),
            **write_scope(args),
        }
        return rest_request("POST", "/memories", {k: v for k, v in body.items() if v is not None})

    if name == "search_memories":
        body = {
            "query": args["query"],
            "top_k": args.get("top_k", 5),
            "filters": args.get("filters"),
            **scoped_args(args),
        }
        return rest_request("POST", "/search", {k: v for k, v in body.items() if v is not None})

    if name == "get_memories":
        params = {**scoped_args(args)}
        if args.get("limit"):
            params["limit"] = str(args["limit"])
        query = urllib.parse.urlencode(params)
        return rest_request("GET", f"/memories?{query}")

    if name == "get_memory":
        return rest_request("GET", f"/memories/{urllib.parse.quote(args['memory_id'])}")

    if name == "update_memory":
        body = {"text": args["memory"], "metadata": args.get("metadata")}
        return rest_request(
            "PUT",
            f"/memories/{urllib.parse.quote(args['memory_id'])}",
            {k: v for k, v in body.items() if v is not None},
        )

    if name == "delete_memory":
        return rest_request("DELETE", f"/memories/{urllib.parse.quote(args['memory_id'])}")

    if name == "delete_all_memories":
        query = urllib.parse.urlencode(scoped_args(args))
        return rest_request("DELETE", f"/memories?{query}")

    raise RuntimeError(f"Unknown tool: {name}")


def handle(message: dict[str, Any]) -> None:
    method = message.get("method")
    message_id = message.get("id")

    if method == "initialize":
        rpc_result(
            message_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        )
        return

    if method in ("notifications/initialized", "notifications/cancelled"):
        return

    if method == "ping":
        rpc_result(message_id, {})
        return

    if method == "tools/list":
        rpc_result(message_id, {"tools": tool_schema()})
        return

    if method == "tools/call":
        params = message.get("params", {})
        try:
            result = call_tool(params.get("name", ""), params.get("arguments", {}) or {})
            rpc_result(message_id, content_text(result))
        except Exception as exc:
            rpc_result(message_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
        return

    if message_id is not None:
        rpc_error(message_id, -32601, f"Method not found: {method}")


def main() -> int:
    while True:
        message = read_message()
        if message is None:
            return 0
        handle(message)


if __name__ == "__main__":
    raise SystemExit(main())
