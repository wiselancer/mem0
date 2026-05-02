#!/usr/bin/env bash
# Hook: Stop (Codex)
#
# Fires when Codex finishes a turn. By default this hook lets the turn end
# without writing memory. Set MEM0_AUTO_CAPTURE=true to capture a compact
# session state in the background.
# Set MEM0_STOP_HOOK_BLOCK=true to restore the interactive reminder behavior.
#
# Input:  JSON on stdin with session_id, turn_id, stop_hook_active,
#         last_assistant_message, transcript_path, cwd,
#         hook_event_name, model
# Output: JSON on stdout (Codex rejects plain text on Stop).
#         - default -> {"continue": true}
#         - MEM0_STOP_HOOK_BLOCK=true and stop_hook_active=false
#           -> {"decision":"block","reason":"..."}
#
# We must respect stop_hook_active or we'd loop forever: every "block"
# reopens the turn, which triggers Stop again when the agent settles.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT=$(cat)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false' 2>/dev/null || echo "false")

if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
  printf '{"continue":true}\n'
  exit 0
fi

if [ "${MEM0_STOP_HOOK_BLOCK:-false}" != "true" ]; then
  if [ "${MEM0_AUTO_CAPTURE:-false}" = "true" ]; then
    echo "$INPUT" | MEM0_AGENT_ID="${MEM0_AGENT_ID:-codex}" python3 "$SCRIPT_DIR/on_pre_compact.py" --source=codex-session-end 2>/dev/null &
  fi
  printf '{"continue":true}\n'
  exit 0
fi

REASON=$(cat <<'EOF'
Before finishing, check if there are important learnings from this interaction that should be persisted using the mem0 `add_memory` tool:

1. Were any significant decisions made? -> Store with metadata `{"type": "decision"}`
2. Did project state, blockers, milestones, or next steps change? -> Store with metadata `{"type": "project_state"}`
3. Were any new patterns or strategies discovered? -> Store with metadata `{"type": "task_learning"}`
4. Did any approach fail? -> Store with metadata `{"type": "anti_pattern"}`
5. Did you learn anything about the user's preferences? -> Store with metadata `{"type": "user_preference"}`
6. Did the user set an explicit standing rule? -> Store with metadata `{"type": "standing_rule"}`
7. Were there environment/setup discoveries? -> Store with metadata `{"type": "environmental"}`

Include project/entity metadata when possible, for example:
`{"type":"decision","project":"project-or-repo-name","source":"agent-session","agent":"codex","importance":"high","entities":["Mem0"],"visibility":"private"}`

Store durable memory, not transcripts. Memories should be self-contained, searchable, and export-friendly for future tools like Obsidian. Use absolute dates for time-sensitive facts. Do not store secrets, API keys, tokens, passwords, or raw `.env` values.

Use `user_id` for the stable owner/person, `agent_id` for the writer/runtime, and `run_id` for the current project or session grouping. Do not reuse one global `run_id` across unrelated projects.

If nothing notable happened in this interaction, it's fine to skip. Only store genuinely useful learnings.
EOF
)

jq -cn --arg reason "$REASON" '{decision:"block", reason:$reason}'
exit 0
