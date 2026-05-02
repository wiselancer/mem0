# Agent Memory Protocol

Use this protocol when Mem0 is shared across coding agents such as Claude Code,
Codex, Cursor, OpenClaw, Hermes, and other MCP-capable assistants.

Mem0 should store durable operational memory, not transcripts. Raw conversation
logs can live elsewhere; Mem0 should contain the facts, decisions, preferences,
project state, and lessons that make future agents more useful.

## Core Loop

Every agent should follow the same loop:

1. Recall before work starts.
2. Do the task using recalled context when relevant.
3. Search for similar memories before writing.
4. Store only durable learnings after meaningful work.
5. Save one session summary before compaction or handoff only when useful state would otherwise be lost.

## What To Remember

Store a memory only when a new agent would benefit from knowing it days or weeks
later.

Good memories:

- User preferences and standing instructions.
- Infrastructure facts and environment setup.
- Product, architecture, and deployment decisions.
- Current project state, milestones, blockers, and next steps.
- Lessons learned, failed approaches, and repeatable strategies.
- Tooling conventions that should apply across agents.

Skip:

- Small talk, acknowledgements, and one-off status updates.
- Confirmations that something worked.
- Passing test results unless they establish a reusable release or verification fact.
- Temporary errors after they have been fixed.
- Repeated facts already captured in another memory.
- Raw command output unless the result changes future behavior.
- Generic summaries such as "we discussed GCP."
- Secrets, API keys, tokens, passwords, private URLs with embedded credentials,
  or full `.env` values.

## Memory Shape

Write memories as self-contained third-person facts. Avoid pronouns and vague
references.

Good:

```text
As of 2026-05-02, user has Coolify running on GCP and wants it to become the new deployment home while gradually migrating apps away from Hetzner.
```

Bad:

```text
We talked about that migration and decided to use it.
```

Prefer one complete memory per entity or decision rather than many tiny
fragments. If multiple details describe the same project, service, or decision,
combine them into one concise fact.

## Metadata

Use consistent metadata so memories can later be filtered, exported, or rendered
as an Obsidian-style knowledge graph.

Recommended metadata:

```json
{
  "type": "decision",
  "project": "gcp-coolify-mem0",
  "source": "agent-session",
  "agent": "codex",
  "importance": "high",
  "entities": ["Mem0", "Coolify", "GCP", "Hetzner"],
  "visibility": "private"
}
```

Use these `type` values:

| Type | Use for |
| ---- | ------- |
| `user_preference` | Stable user preferences, style, tools, workflows |
| `standing_rule` | Explicit rules or policies the user wants agents to follow |
| `decision` | Product, architecture, infrastructure, or process decisions |
| `project_state` | Active project status, milestones, blockers, next actions |
| `environmental` | Setup facts: hosts, services, ports, deployment shape, versions |
| `convention` | Repo, team, or agent workflow conventions |
| `task_learning` | Reusable strategies that worked |
| `anti_pattern` | Approaches that failed or should be avoided |
| `session_state` | Handoff summaries before compaction, pause, or session end |

When the memory is time-sensitive, include an absolute date in the memory text:
`As of YYYY-MM-DD, ...`.

## Scoping

Use hosted Mem0 for personal memory by default. Keep self-hosted Mem0 for
explicit project-specific memory spaces. Use one stable `user_id` across agents
for personal memory. Use `agent_id` for the agent or tool that wrote the memory.
Use project metadata for filtering.

Recommended defaults:

| Field | Example |
| ----- | ------- |
| `user_id` | `wiselancer` |
| `agent_id` | `codex`, `claude-code`, `openclaw`, `hermes`, `sheldon` |
| `run_id` | A session or task identifier when available |
| `metadata.project` | `gcp-coolify-mem0` |

Avoid creating separate users for each agent unless memory isolation is the goal.
Shared memory works best when all trusted agents write into the same user scope
and distinguish themselves with `agent_id` or metadata.

When using hosted Mem0 MCP, pass `user_id="wiselancer"` explicitly on
`add_memory`, `search_memories`, `get_memories`, `delete_all_memories`, and any
scope-sensitive call. The hosted MCP server defaults to `user_id="mem0-mcp"` if
the caller omits a user, which is not the desired personal-memory scope.

For normal recall, search the user scope:

```json
{"user_id": "wiselancer"}
```

For cross-agent recall, use `OR` rather than `AND`:

```json
{"OR": [{"user_id": "wiselancer"}, {"agent_id": "codex"}]}
```

Do not use an `AND` filter combining `user_id` and `agent_id`; hosted Mem0 stores
entity scopes separately, so that pattern commonly returns empty results.

## Agent Tool Mapping

Different agents expose different tool names, but the protocol is the same.

| Agent | Recall | Store |
| ----- | ------ | ----- |
| Claude Code / Cursor MCP | `search_memories` | `add_memory` |
| Codex MCP | `search_memories` | `add_memory` |
| OpenClaw | `memory_search` | `memory_add` |
| Hermes | `mem0_search` / `mem0_profile` | `mem0_conclude` |
| Other MCP agents | Mem0 MCP search/list tools | Mem0 MCP add/update tools |

When the agent supports direct fact storage without server-side extraction
(for example Hermes `mem0_conclude` or OpenClaw skill-based triage), store the
curated fact directly.

## Session Handoff Memory

Before compaction, shutdown, or handing off to another agent, save one
`session_state` memory with:

- User goal.
- What was completed.
- Key decisions.
- Files or services touched.
- Current state.
- Next recommended steps.
- Known risks or open questions.

This is the only memory type that may be longer than a normal fact.

## Obsidian And Knowledge Graph Readiness

To make future export easy, keep metadata rich and predictable:

- `project` becomes an Obsidian folder or property.
- `type` becomes a note class.
- `entities` become links such as `[[Mem0]]`, `[[Coolify]]`, `[[GCP]]`.
- `created_at` and temporal phrases support timelines.
- `visibility` helps decide what can be synced to human-readable notes.

A later exporter can turn a decision memory into Markdown like:

```markdown
# Decision: Keep Mem0 As Primary Memory Layer

Project: [[gcp-coolify-mem0]]
Type: decision
Entities: [[Mem0]], [[Coolify]], [[GCP]]

As of 2026-05-02, user decided to keep Mem0 as the primary memory layer for the
GCP Coolify deployment and postpone CaviraOSS/OpenMemory evaluation.
```

## Quality Checklist

Before storing, ask:

- Is this durable and useful?
- Is it new or materially updated?
- Did I search for an existing similar memory first?
- Is it specific enough to retrieve later?
- Does it avoid secrets?
- Does it include project/type metadata?
- Would it still make sense outside the current chat?
- Would it still matter two weeks from now?
