import os

os.environ.setdefault("MEM0_SELF_HOSTED_API_KEY", "test-mem0-key")
os.environ.setdefault("MCP_GATEWAY_TOKEN", "test-token")
os.environ.setdefault("MCP_GATEWAY_USER_ID", "wiselancer")
os.environ.setdefault("MCP_GATEWAY_AGENT_ID", "codex")

import pytest
from httpx import ASGITransport, AsyncClient

from app import app


MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Authorization": "Bearer test-token",
}


def jsonrpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }


@pytest.mark.asyncio
async def test_requires_bearer_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/mcp",
            json=jsonrpc("initialize"),
            headers={"Accept": "application/json, text/event-stream"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_initialize_and_tools_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        init_response = await client.post(
            "/mcp",
            json=jsonrpc(
                "initialize",
                {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "0.1.0"},
                },
            ),
            headers=MCP_HEADERS,
        )
        assert init_response.status_code == 200
        assert init_response.json()["result"]["serverInfo"]["name"] == "mem0-self-hosted-gateway"

        tools_response = await client.post(
            "/mcp",
            json=jsonrpc("tools/list", req_id=2),
            headers=MCP_HEADERS,
        )
        assert tools_response.status_code == 200
        tool_names = {tool["name"] for tool in tools_response.json()["result"]["tools"]}
        assert {
            "add_memory",
            "search_memories",
            "get_memories",
            "get_memory",
            "update_memory",
            "delete_memory",
            "delete_all_memories",
        }.issubset(tool_names)
