#!/usr/bin/env bash
# Hook: SessionStart (matcher: startup|resume|compact)
#
# Bootstraps mem0 context at the start of every session.
# Output becomes part of Claude's context so it calls mem0 MCP tools.
#
# Input:  JSON on stdin with session_id, source, transcript_path, model, cwd
# Output: Text injected into Claude's context (exit 0)

# Intentionally omit -e so the script always outputs a bootstrap prompt
# even if jq is missing or stdin is malformed.
set -uo pipefail

INPUT=$(cat)
SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"' 2>/dev/null || echo "startup")

if [ "$SOURCE" = "startup" ]; then
  cat <<'EOF'
## Mem0 Session Bootstrap

You have access to persistent memory via the mem0 MCP tools. Before doing anything else:

1. Call `search_memories` with a query related to the current project or user request to load relevant context. For hosted personal memory, pass `filters: {"user_id":"wiselancer"}`.
2. Review the returned memories to understand what has been learned in prior sessions.
3. If appropriate, call `get_memories` to browse all stored memories for this user.

Use hosted Mem0 for personal memory by default. Always pass `user_id: "wiselancer"` on personal memory writes/searches, pass `agent_id: "claude-code"` for Claude Code, and use metadata for project/type/source/entities/visibility. If you need both personal and agent-specific memories, use `OR`; do not use `AND` with `user_id` + `agent_id`.

IMPORTANT: Do NOT skip this step. Always bootstrap context first.
EOF

elif [ "$SOURCE" = "resume" ]; then
  cat <<'EOF'
## Mem0 Session Resumed

This is a resumed session. Your prior context is already loaded. Before continuing:

1. Call `search_memories` with a query related to the current task to refresh relevant memories. For hosted personal memory, pass `filters: {"user_id":"wiselancer"}`.
2. If significant time has passed, search for recent project-wide updates.

Use hosted Mem0 for personal memory by default. Always pass `user_id: "wiselancer"` on personal memory writes/searches, pass `agent_id: "claude-code"` for Claude Code, and use `OR` rather than `AND` when combining user and agent scope.

Continue where you left off.
EOF

elif [ "$SOURCE" = "compact" ]; then
  cat <<'EOF'
## Mem0 Post-Compaction Recovery

Context was just compacted. You may have lost important session context.

1. Call `search_memories` with queries related to what you were working on to reload relevant knowledge. For hosted personal memory, pass `filters: {"user_id":"wiselancer"}`.
2. Check for any session state memories that were saved before compaction.
3. Continue working based on the recovered context.

Use hosted Mem0 for personal memory by default. Always pass `user_id: "wiselancer"` on personal memory writes/searches, pass `agent_id: "claude-code"` for Claude Code, and use `OR` rather than `AND` when combining user and agent scope.
EOF
fi

exit 0
