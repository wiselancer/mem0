# R&D: claude-mem Audit — Ideas to Borrow

**Date:** 2026-05-04
**Sources audited:**
- [`thedotmack/claude-mem`](https://github.com/thedotmack/claude-mem) — main repo (65K+ stars)
- [`customable/claude-mem`](https://github.com/customable/claude-mem) — Qdrant fork
- [`vm-wylbur/claude-mem`](https://github.com/vm-wylbur/claude-mem) — semantic search / pgvector fork
- [`coleam00/claude-memory-compiler`](https://github.com/coleam00/claude-memory-compiler) — Karpathy LLM Knowledge Base pattern

**Why:** Building a product from this repo (mem0-plugin / agent memory layer). These are patterns from the open-source ecosystem worth implementing natively on top of hosted Mem0.

---

## Priority Backlog

| # | Feature | Impact | Effort | Source |
|---|---------|--------|--------|--------|
| 1 | Recursion guard + `<private>` tag filtering in `on_pre_compact.py` | High | 30 min | claude-mem |
| 2 | Structured observation XML schema (`type + title + subtitle + facts + narrative + concepts + files`) | High | 2 hrs | claude-mem |
| 3 | `PreToolUse` file-context hook — inject memories about a file before Claude reads it | High | 1 hr | claude-mem |
| 4 | 6-field structured session summary (`request, investigated, learned, completed, next_steps, notes`) | Medium | 1 hr | claude-mem |
| 5 | Local knowledge index + end-of-day compilation pipeline | Medium | 4 hrs | coleam00 |
| 6 | `__IMPORTANT` meta-tool enforcing 3-layer retrieval in MCP server | Medium | 1 hr | claude-mem |
| 7 | `timeline` MCP tool — chronological neighbors of a memory | Medium | 2 hrs | claude-mem |
| 8 | Memory curation workflow (`delete / connect / enhance / extract-pattern`) | Low | 3 hrs | vm-wylbur |
| 9 | Memory health check / lint (`orphans, duplicates, stale, contradictions`) | Low | 3 hrs | vm-wylbur + coleam00 |
| 10 | Knowledge corpus builder + `query_corpus` (persistent knowledge agent) | Low | 5 hrs | claude-mem |

---

## Feature Details

### 1. Recursion Guard + `<private>` Filtering
**File:** `mem0-plugin/scripts/on_pre_compact.py`

**Problem:** If on_pre_compact.py spawns a Claude subprocess via Agent SDK in the future, that subprocess will re-fire the hook — causing infinite recursion and duplicate memory writes.

**Fix — add at top of `main()`:**
```python
import os
if os.environ.get("CLAUDE_INVOKED_BY") or os.environ.get("MEM0_FLUSH_ACTIVE"):
    sys.exit(0)
os.environ["MEM0_FLUSH_ACTIVE"] = "1"
```

**`<private>` tag filtering — strip before POSTing:**
```python
import re
content = re.sub(r'<private>.*?</private>', '', content, flags=re.DOTALL)
```

Claude should emit `<private>...</private>` around any sensitive reasoning. Content inside those tags is never stored.

---

### 2. Structured Observation XML Schema

**Current:** `on_stop.sh` prompts Claude with 7 free-text memory types. Result: inconsistently shaped memories, hard to filter.

**Replace with this schema** in the on_stop.sh prompt:

```xml
<observation>
  <type>[ bugfix | feature | refactor | change | discovery | decision ]</type>
  <title>[Short title — core action or topic]</title>
  <subtitle>[One sentence, max 24 words]</subtitle>
  <facts>
    <fact>[Concise, self-contained, no pronouns]</fact>
  </facts>
  <narrative>[Full context: what was done, how it works, why it matters]</narrative>
  <concepts>
    <concept>[how-it-works | why-it-exists | what-changed | problem-solution | gotcha | pattern | trade-off]</concept>
  </concepts>
  <files_read><file>[path]</file></files_read>
  <files_modified><file>[path]</file></files_modified>
</observation>
```

**Note:** `type` = what kind of change; `concepts` = knowledge dimension (orthogonal). This enables filtering like "all `gotcha` concepts in project X."

**Skip guidance to add to prompt (reduces noise):**
```
WHEN TO SKIP: Empty status checks, package installs with no errors, simple file
listings with no findings, repetitive operations already documented.
If skipping, return an empty response only. Do not explain the skip.
```

**Observer identity guidance:**
```
Record what was LEARNED/BUILT/FIXED/DEPLOYED, not what you (the observer) are doing.
Use verbs: implemented, fixed, deployed, configured, migrated, discovered, confirmed.
GOOD: "Authentication now supports OAuth2 with PKCE flow"
BAD:  "Analyzed authentication implementation and stored findings"
```

**Parsing:** `on_stop.sh` (or a companion Python script) parses each `<observation>` block, maps fields to Mem0 metadata:
```json
{
  "type": "bugfix",
  "concepts": ["gotcha", "problem-solution"],
  "files_modified": ["src/auth/login.ts"],
  "title": "Fix OAuth2 redirect loop",
  "subtitle": "Redirect URI must be registered before token exchange"
}
```

---

### 3. PreToolUse File-Context Hook

**How it works:** Before Claude reads any file, query Mem0 for memories mentioning that file path. Inject top-3 results as hook context.

**Add to `hooks/hooks.json`:**
```json
"PreToolUse": [{
  "matcher": "Read",
  "hooks": [{
    "type": "command",
    "command": "/path/to/mem0-plugin/scripts/on_pre_file_read.sh",
    "timeout": 3000
  }]
}]
```

**`on_pre_file_read.sh`:**
```bash
#!/usr/bin/env bash
set -uo pipefail

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ] || [ -z "${MEM0_API_KEY:-}" ]; then
  exit 0
fi

USER_ID="${MEM0_USER_ID:-wiselancer}"
AGENT_ID="${MEM0_AGENT_ID:-claude-code}"

BODY=$(jq -n \
  --arg query "$FILE_PATH" \
  --arg user_id "$USER_ID" \
  --arg agent_id "$AGENT_ID" \
  '{query: $query, filters: {OR: [{user_id: $user_id}, {agent_id: $agent_id}]}, top_k: 3}')

RESPONSE=$(curl -s --max-time 3 \
  -X POST "https://api.mem0.ai/v2/memories/search/" \
  -H "Authorization: Token $MEM0_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$BODY" 2>/dev/null || echo "")

MEMORIES=$(echo "$RESPONSE" | jq -r '
  if type == "array" then . else .results // [] end |
  if length == 0 then empty else
  "## Past context for `" + $file + "`\n" +
  (map(select(.memory != null) | "- " + .memory) | join("\n"))
  end
' --arg file "$FILE_PATH" 2>/dev/null || echo "")

[ -n "$MEMORIES" ] && echo "$MEMORIES"
exit 0
```

---

### 4. 6-Field Session Summary Schema

**Current:** `on_pre_compact.py` builds a freeform markdown blob of user messages + files + commands.

**Replace the content builder with:**
```xml
<summary>
  <request>[What the user was asking for — substance, not just words]</request>
  <investigated>[What was explored or examined this session]</investigated>
  <learned>[What was discovered about how things work]</learned>
  <completed>[What shipped or changed — specific files/services]</completed>
  <next_steps>[Current active trajectory, NOT future TODOs]</next_steps>
  <notes>[Additional insights or anomalies]</notes>
</summary>
```

**Key distinction on `next_steps`:** "current trajectory of work" — what's actively being done right now, not post-session wishlist. This makes session handoffs dramatically more useful for resuming work.

Map to Mem0 metadata:
```json
{
  "type": "session_state",
  "summary_type": "session_checkpoint",
  "source": "pre-compaction",
  "has_next_steps": true
}
```

---

### 5. Local Knowledge Index + End-of-Day Compilation

**Pattern from:** `coleam00/claude-memory-compiler`

**Architecture:**
1. `compile_knowledge.py` — runs nightly (or triggered manually), queries all Mem0 memories for `user_id:"wiselancer"`, groups by project + type, writes `~/.mem0-plugin/knowledge/index.md` as a table: `| Project | Type | Title | Date |`
2. `on_session_start.sh` injects the top 20KB of `index.md` as `additionalContext` — gives instant O(1) orientation without waiting for API search
3. Hash-based change detection: skip recompile if no new memories since last run

**Benefits:**
- Works as offline fallback when Mem0 API is slow/down
- Makes the "what do I know?" question free (no API call)
- Enables Obsidian-style export directly from the index

**Lint checks to add (from coleam00):**
- Duplicate memory detection (same title, different IDs)
- Stale project state (project_state memories older than 30 days with no update)
- Orphaned memories (no project tag)
- Contradiction detection (two memories in same project with conflicting facts)

---

### 6. `__IMPORTANT` Meta-Tool (3-Layer Retrieval Enforcement)

**Add to MCP server (`server/mcp-gateway/app.py` or mem0-plugin MCP server):**

```python
{
    "name": "__IMPORTANT",
    "description": """ALWAYS USE THIS 3-LAYER WORKFLOW:
1. search_memories(query, top_k=20) → Get compact result list with IDs
2. For ambiguous results, narrow with date/type/project filters
3. get_memory(id) → Fetch full detail ONLY for IDs you actually need

NEVER call get_memories() without filtering first.
NEVER fetch full details for all search results.
This prevents token waste and keeps context focused.""",
    "inputSchema": {"type": "object", "properties": {}}
}
```

This shows up in Claude's tool list at session start, enforcing the workflow without prompt injection.

---

### 7. `timeline` MCP Tool

**Add to MCP server:**

```python
@app.tool("timeline")
async def timeline(anchor_id: str, depth_before: int = 3, depth_after: int = 3) -> str:
    """Get chronological neighbors of a memory. Shows what was being worked on
    around the same time as the anchor memory."""
    anchor = await get_memory(anchor_id)
    anchor_time = anchor["created_at"]
    # Query memories ±depth around anchor's timestamp
    before = await search_by_time(before=anchor_time, limit=depth_before)
    after = await search_by_time(after=anchor_time, limit=depth_after)
    return format_timeline(before, [anchor], after)
```

Use case: "What was being worked on when this auth decision was made?"

---

### 8. Memory Curation Workflow

**Pattern from:** `vm-wylbur/claude-mem` `tools/interactive-curator.ts`

**How it works:** A multi-session curation workflow where Claude reviews memories in batches and categorizes each as:
- `delete` — no longer relevant or duplicate
- `connect` — should be linked to another memory
- `enhance` — needs more context added
- `extract-pattern` — specific enough to generalize into a convention

Session state persists in `.curation_session.json`. Claude can stop and resume mid-triage.

**Adapt as a MCP tool `curate_memories`:**
```python
@app.tool("curate_memories")
async def curate_memories(project: str = None, older_than_days: int = 30) -> str:
    """Interactive triage of low-quality or stale memories."""
    ...
```

---

### 9. Memory Health Check

**Pattern from:** `vm-wylbur/claude-mem` (detailed-curator-report) + `coleam00/claude-memory-compiler` (lint.py)

**Checks to implement:**
1. **Duplicates** — memories with cosine similarity > 0.92 (use Mem0 search to find near-duplicates)
2. **Orphaned** — memories with no `project` in metadata
3. **Stale project_state** — `type=project_state` memories older than 30 days
4. **Secret leakage** — memories containing patterns like `sk-`, `Bearer `, `password`, `_KEY=`
5. **Missing metadata** — memories without `type`, `source`, or `agent`
6. **Contradiction candidates** — two memories in same project with opposing facts (LLM check)

**Run as CLI tool:** `python3 mem0-plugin/scripts/memory_health.py`

---

### 10. Knowledge Corpus Builder

**Pattern from:** `claude-mem` `src/servers/mcp-server.ts` — `build_corpus` / `query_corpus`

**How it works:**
1. `build_corpus(project?, type?, date_start?, date_end?)` — filters memories, builds markdown corpus, spawns a headless Claude session with corpus as system prompt, stores `session_id`
2. `query_corpus(question)` — routes question to the corpus session, returns answer without touching main session context
3. Sessions auto-reprime when expired

**Parent process heartbeat** (prevent orphan MCP processes):
```python
import os, time, threading
initial_ppid = os.getppid()
def _heartbeat():
    while True:
        time.sleep(30)
        if os.getppid() in (1, None) or os.getppid() != initial_ppid:
            os._exit(0)
threading.Thread(target=_heartbeat, daemon=True).start()
```

---

## What We Already Do Better

| Area | Why our approach wins |
|------|----------------------|
| **Cross-agent memory** | `user_id:"wiselancer"` + OR filters across Claude Code, Codex, Hermes, OpenClaw, Sheldon. claude-mem is Claude Code-only. |
| **Zero local infra** | Hosted Mem0 API. claude-mem requires Bun + ChromaDB + SQLite + background worker on port 37777. |
| **Metadata richness** | `importance`, `visibility`, `entities` fields. claude-mem has none of these. |
| **Protocol documentation** | `AGENT_MEMORY_PROTOCOL.md` covers 7 types, scoping, cross-agent mapping, Obsidian export. claude-mem is code-only. |
| **Security** | No unauthenticated local API surface. claude-mem Feb 2026 audit: cleartext API key exposure, arbitrary file read via MCP, unauthenticated network exposure. |

---

## Rejected Ideas

| Idea | Reason |
|------|--------|
| ChromaDB / SQLite local backend | We use hosted Mem0 — zero ops wins |
| PostToolUse per-tool-call observer agent | Too noisy; generates low-quality memories from routine bash/read calls. Better done selectively at stop-time. |
| Token economics tracking | Low ROI for our use case; Mem0 API doesn't expose token cost per memory |
| Real-time websocket broadcast (customable fork) | Premature; no UI dashboard yet |
| Multi-AI consensus quality scoring (vm-wylbur) | Overkill; Claude-only LLM quality check is sufficient |

---

## Notes on claude-mem Security (Do Not Implement These Patterns)

From the February 2026 community security audit (Issue #1251):

- **Unauthenticated API** — worker listens on `0.0.0.0:37777` with no auth. We use HTTPS + token auth.
- **Cleartext API key in `/api/settings`** — returns full `settings.json` including `GEMINI_API_KEY` etc. Never expose settings over HTTP.
- **Arbitrary file read via MCP** — `get_observations` tool accepts arbitrary paths. All our MCP tools scope to Mem0 API calls only, never the local filesystem.

---

*Last updated: 2026-05-04 | Next review: when implementing priority #1 or #2*
