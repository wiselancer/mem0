# Self-hosted Mem0 MCP Gateway

Small Streamable HTTP MCP gateway for the self-hosted Mem0 REST API.

It exposes:

```text
POST https://mcp.mem.petrenko.cv/mcp
```

and translates MCP tool calls into REST calls against `api.mem.petrenko.cv`.

## Environment

```bash
MEM0_SELF_HOSTED_API_URL=https://api.mem.petrenko.cv
MEM0_SELF_HOSTED_API_KEY=m0sk_...
MCP_GATEWAY_TOKEN=agent-facing-token
MCP_GATEWAY_USER_ID=wiselancer
MCP_GATEWAY_AGENT_ID=codex
```

For multiple agents, prefer:

```bash
MCP_GATEWAY_TOKENS='{
  "token-for-codex": {"user_id":"wiselancer","agent_id":"codex"},
  "token-for-claude": {"user_id":"wiselancer","agent_id":"claude-code"}
}'
```

## Tools

- `add_memory`
- `search_memories`
- `get_memories`
- `get_memory`
- `update_memory`
- `delete_memory`
- `delete_all_memories`
