from __future__ import annotations

import contextvars
import json
import os
from typing import Any

import anyio
import httpx
from fastapi import FastAPI, HTTPException, Request
from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.responses import Response


SERVER_NAME = "mem0-self-hosted-gateway"
DEFAULT_MEM0_API_URL = "https://api.mem.petrenko.cv"

mcp = FastMCP(SERVER_NAME)
app = FastAPI(title="Self-hosted Mem0 MCP Gateway", version="0.1.0")

identity_var: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar("identity")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def mem0_api_url() -> str:
    return _env("MEM0_SELF_HOSTED_API_URL", _env("MEM0_API_URL", DEFAULT_MEM0_API_URL)).rstrip("/")


def mem0_api_key() -> str:
    key = _env("MEM0_SELF_HOSTED_API_KEY", _env("MEM0_API_KEY", ""))
    if not key:
        raise RuntimeError("MEM0_SELF_HOSTED_API_KEY or MEM0_API_KEY is required")
    return key


def token_map() -> dict[str, dict[str, str]]:
    raw = _env("MCP_GATEWAY_TOKENS")
    if raw:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise RuntimeError("MCP_GATEWAY_TOKENS must be a JSON object")
        return {str(token): {str(k): str(v) for k, v in value.items()} for token, value in parsed.items()}

    token = _env("MCP_GATEWAY_TOKEN")
    if token:
        return {
            token: {
                "user_id": _env("MCP_GATEWAY_USER_ID", _env("MEM0_USER_ID", "default")),
                "agent_id": _env("MCP_GATEWAY_AGENT_ID", _env("MEM0_AGENT_ID", "agent")),
                "run_id": _env("MCP_GATEWAY_RUN_ID", _env("MEM0_RUN_ID", "")),
            }
        }

    return {}


def bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token.strip()


def authenticate(request: Request) -> dict[str, str]:
    tokens = token_map()
    if not tokens:
        raise HTTPException(status_code=500, detail="MCP gateway token is not configured")

    token = bearer_token(request)
    identity = tokens.get(token)
    if not identity:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    if not identity.get("user_id"):
        raise HTTPException(status_code=500, detail="Token identity is missing user_id")

    return identity


def current_identity() -> dict[str, str]:
    try:
        return identity_var.get()
    except LookupError as exc:
        raise RuntimeError("MCP identity is not set") from exc


def scoped_args(args: dict[str, Any], *, include_run: bool = True) -> dict[str, Any]:
    identity = current_identity()
    scoped: dict[str, Any] = {
        "user_id": args.get("user_id") or identity.get("user_id"),
    }
    agent_id = args.get("agent_id") or identity.get("agent_id")
    run_id = args.get("run_id") or identity.get("run_id")
    if agent_id:
        scoped["agent_id"] = agent_id
    if include_run and run_id:
        scoped["run_id"] = run_id
    return scoped


async def mem0_request(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-API-Key": mem0_api_key(),
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(method, f"{mem0_api_url()}{path}", json=body, headers=headers)
    response.raise_for_status()
    return response.json() if response.content else {}


@mcp.tool(description="Store a durable memory in the self-hosted Mem0 server.")
async def add_memory(
    memory: str,
    metadata: dict[str, Any] | None = None,
    infer: bool = False,
    user_id: str | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> str:
    body = {
        "messages": [{"role": "user", "content": memory}],
        "metadata": metadata,
        "infer": infer,
        **scoped_args({"user_id": user_id, "agent_id": agent_id, "run_id": run_id}),
    }
    return json.dumps(await mem0_request("POST", "/memories", {k: v for k, v in body.items() if v is not None}))


@mcp.tool(description="Search self-hosted Mem0 for relevant memories.")
async def search_memories(
    query: str,
    top_k: int = 5,
    filters: dict[str, Any] | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> str:
    body = {
        "query": query,
        "top_k": top_k,
        "filters": filters,
        **scoped_args({"user_id": user_id, "agent_id": agent_id, "run_id": run_id}, include_run=False),
    }
    if run_id:
        body["run_id"] = run_id
    return json.dumps(await mem0_request("POST", "/search", {k: v for k, v in body.items() if v is not None}), indent=2)


@mcp.tool(description="List memories for the authenticated user, optionally scoped by agent or run.")
async def get_memories(
    user_id: str | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> str:
    params = scoped_args({"user_id": user_id, "agent_id": agent_id, "run_id": run_id}, include_run=False)
    if run_id:
        params["run_id"] = run_id
    query = httpx.QueryParams(params)
    return json.dumps(await mem0_request("GET", f"/memories?{query}"), indent=2)


@mcp.tool(description="Retrieve one memory by id.")
async def get_memory(memory_id: str) -> str:
    return json.dumps(await mem0_request("GET", f"/memories/{memory_id}"), indent=2)


@mcp.tool(description="Update one memory by id.")
async def update_memory(memory_id: str, memory: str, metadata: dict[str, Any] | None = None) -> str:
    body = {"text": memory, "metadata": metadata}
    return json.dumps(await mem0_request("PUT", f"/memories/{memory_id}", {k: v for k, v in body.items() if v is not None}))


@mcp.tool(description="Delete one memory by id.")
async def delete_memory(memory_id: str) -> str:
    return json.dumps(await mem0_request("DELETE", f"/memories/{memory_id}"))


@mcp.tool(description="Delete all memories in the authenticated scope.")
async def delete_all_memories(
    user_id: str | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> str:
    params = scoped_args({"user_id": user_id, "agent_id": agent_id, "run_id": run_id}, include_run=False)
    if run_id:
        params["run_id"] = run_id
    query = httpx.QueryParams(params)
    return json.dumps(await mem0_request("DELETE", f"/memories?{query}"))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route("/mcp", methods=["POST", "GET", "DELETE"])
async def handle_mcp(request: Request):
    identity = authenticate(request)
    identity_token = identity_var.set(identity)

    response_started = False
    response_status = 200
    response_headers: list[tuple[bytes, bytes]] = []
    response_body = bytearray()

    async def capture_send(message):
        nonlocal response_started, response_status
        if message["type"] == "http.response.start":
            response_started = True
            response_status = message["status"]
            response_headers.extend(message.get("headers", []))
        elif message["type"] == "http.response.body":
            response_body.extend(message.get("body", b""))

    try:
        transport = StreamableHTTPServerTransport(
            mcp_session_id=None,
            is_json_response_enabled=True,
        )

        async with anyio.create_task_group() as task_group:

            async def run_server(*, task_status=anyio.TASK_STATUS_IGNORED):
                async with transport.connect() as (read_stream, write_stream):
                    task_status.started()
                    await mcp._mcp_server.run(
                        read_stream,
                        write_stream,
                        mcp._mcp_server.create_initialization_options(),
                        stateless=True,
                    )

            await task_group.start(run_server)
            await transport.handle_request(request.scope, request.receive, capture_send)
            await transport.terminate()
            task_group.cancel_scope.cancel()
    finally:
        identity_var.reset(identity_token)

    if not response_started:
        return Response(status_code=500, content=b"Transport did not produce a response")

    return Response(
        content=bytes(response_body),
        status_code=response_status,
        headers={k.decode(): v.decode() for k, v in response_headers},
    )


mcp._mcp_server.name = SERVER_NAME
