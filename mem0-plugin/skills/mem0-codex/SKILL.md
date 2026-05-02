---
name: mem0-codex
description: >
  Mem0 persistent memory integration for Codex. Retrieve relevant memories at
  the start of each task and store only durable, non-duplicate learnings when
  meaningful work completes. Use the mem0 MCP tools
  (add_memory, search_memories, get_memories, etc.) for all memory operations.
---

# Mem0 Memory Protocol for Codex

You have access to persistent memory via the mem0 MCP tools. Follow this protocol to maintain context across sessions.

## On every new task

1. Call `search_memories` with a query related to the current task or project to load relevant context.
2. Review returned memories to understand what has been learned in prior sessions.
3. If appropriate, call `get_memories` to browse all stored memories for this user.

## After completing significant work

Search existing memories first. Then store only durable learnings using the `add_memory` tool:

- **Decisions made** -> Include metadata `{"type": "decision"}`
- **Current project state, milestones, blockers, or next steps** -> Include metadata `{"type": "project_state"}`
- **Strategies that worked** -> Include metadata `{"type": "task_learning"}`
- **Failed approaches** -> Include metadata `{"type": "anti_pattern"}`
- **User preferences observed** -> Include metadata `{"type": "user_preference"}`
- **Explicit standing rules or policies** -> Include metadata `{"type": "standing_rule"}`
- **Environment/setup discoveries** -> Include metadata `{"type": "environmental"}`
- **Conventions established** -> Include metadata `{"type": "convention"}`

Use project/entity metadata whenever possible so memories can be reused across
Claude Code, Codex, Cursor, OpenClaw, Hermes, and future tools:

```json
{
  "type": "decision",
  "project": "project-or-repo-name",
  "source": "agent-session",
  "agent": "codex",
  "importance": "high",
  "entities": ["Mem0", "Coolify", "GCP"],
  "visibility": "private"
}
```

Memories should be self-contained, specific, searchable, and export-friendly.
Prefer "As of YYYY-MM-DD, user decided..." over vague summaries like "we talked
about deployment." Do not store secrets, API keys, tokens, passwords, or raw
`.env` values.

Skip memory writes for confirmations, passing tests, one-off observations,
temporary errors that were fixed, and repeated facts already captured elsewhere.
If a similar memory exists, update it or skip the new write instead of creating a
near-duplicate.

## Before losing context

If context is about to be compacted or the session is ending and there is
meaningful unresolved state, store one concise session summary:

```
## Session Summary

### User's Goal
[What the user originally asked for]

### What Was Accomplished
[Numbered list of tasks completed]

### Key Decisions Made
[Architectural choices, trade-offs discussed]

### Files Created or Modified
[Important file paths with what changed]

### Current State
[What is in progress, pending items, next steps]
```

Include metadata: `{"type": "session_state"}`

## Memory hygiene

- Do NOT write to MEMORY.md or any file-based memory. Use mem0 MCP tools exclusively.
- Only store genuinely useful learnings. Skip trivial interactions.
- Use specific, searchable language in memory content.
- Store durable memory, not transcripts. Raw logs belong outside Mem0.
- Avoid pronouns and vague references; use named entities like "GCP Coolify deployment" or "Mem0".
- Keep related details about the same decision, project, or service together in one memory.
- Include absolute dates for time-sensitive facts.
- Use the two-week test: store it only if it is likely to matter two weeks from now.
- Prefer canonical setup memories over breadcrumbs: decisions, stable setup facts, standing rules, and reusable lessons.
