#!/usr/bin/env bash
# Hook: Stop
#
# Fires when Claude finishes responding. Reminds Claude to consider durable
# memory writes, and captures transcript state only when MEM0_AUTO_CAPTURE=true.
#
# Input:  JSON on stdin with stop_hook_active, transcript_path, cwd
# Output: Text that becomes Claude's context (exit 0), or nothing
#
# IMPORTANT: Check stop_hook_active to avoid infinite loops.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

INPUT=$(cat)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  exit 0
fi

cat <<'EOF'
Before finishing, check if there are important learnings from this interaction that should be persisted using the mem0 `add_memory` tool:

1. Were any significant decisions made? -> Store with metadata `{"type": "decision"}`
2. Did project state, blockers, milestones, or next steps change? -> Store with metadata `{"type": "project_state"}`
3. Were any new patterns or strategies discovered? -> Store with metadata `{"type": "task_learning"}`
4. Did any approach fail? -> Store with metadata `{"type": "anti_pattern"}`
5. Did you learn anything about the user's preferences? -> Store with metadata `{"type": "user_preference"}`
6. Did the user set an explicit standing rule? -> Store with metadata `{"type": "standing_rule"}`
7. Were there environment/setup discoveries? -> Store with metadata `{"type": "environmental"}`

Include project/entity metadata when possible, for example:
`{"type":"decision","project":"project-or-repo-name","source":"agent-session","agent":"claude-code","importance":"high","entities":["Mem0"],"visibility":"private"}`

Store durable memory, not transcripts. Memories should be self-contained, searchable, and export-friendly for future tools like Obsidian. Use absolute dates for time-sensitive facts. Do not store secrets, API keys, tokens, passwords, or raw `.env` values.

Use hosted Mem0 for personal memory unless the user explicitly requests the self-hosted/project-specific backend. For hosted Mem0, always pass `user_id: "wiselancer"` on writes/searches. Also pass `agent_id` for the writer/runtime (`codex`, `claude-code`, `hermes`, `openclaw`, `sheldon`) and use metadata for `project`, `type`, `source`, `entities`, and `visibility`. Use `run_id` only for a current project/session grouping; do not reuse one global `run_id` across unrelated projects.

When searching hosted Mem0, prefer user scope first: `filters: {"user_id":"wiselancer"}`. If you need both personal and agent-specific memories, use `OR`, for example `filters: {"OR":[{"user_id":"wiselancer"},{"agent_id":"claude-code"}]}`. Do not use `AND` with `user_id` + `agent_id`; Mem0 stores entity scopes separately and that returns empty results.

If nothing notable happened in this interaction, it's fine to skip. Only store genuinely useful learnings.
EOF

if [ "${MEM0_AUTO_CAPTURE:-false}" = "true" ]; then
  echo "$INPUT" | MEM0_AGENT_ID="${MEM0_AGENT_ID:-claude-code}" python3 "$SCRIPT_DIR/on_pre_compact.py" --source=session-end 2>/dev/null &
fi

exit 0
