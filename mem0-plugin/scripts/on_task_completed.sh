#!/usr/bin/env bash
# Hook: TaskCompleted
#
# Fires when a task is marked as completed. Reminds Claude to extract
# and store learnings via the mem0 MCP tools.
#
# Input:  JSON on stdin with task_id, task_subject, task_description
# Output: Text that becomes feedback to the model (exit 0)

set -euo pipefail

INPUT=$(cat)
TASK_SUBJECT=$(echo "$INPUT" | jq -r '.task_subject // "unknown task"' 2>/dev/null || echo "unknown task")

cat <<EOF
Task completed: "$TASK_SUBJECT"

Check whether this completed task produced durable learnings worth storing with the mem0 \`add_memory\` tool:

1. What strategy worked well? -> Store with metadata \`{"type": "task_learning"}\`
2. Were there failed approaches before finding the solution? -> Store with metadata \`{"type": "anti_pattern"}\`
3. Were there architectural decisions? -> Store with metadata \`{"type": "decision"}\`
4. Did project state, blockers, milestones, or next steps change? -> Store with metadata \`{"type": "project_state"}\`
5. Did the user set an explicit standing rule? -> Store with metadata \`{"type": "standing_rule"}\`
6. Any new conventions or patterns established? -> Store with metadata \`{"type": "convention"}\`

Include project/entity metadata when possible, for example:
\`{"type":"decision","project":"project-or-repo-name","source":"agent-session","agent":"claude-code","importance":"high","entities":["Mem0"],"visibility":"private"}\`

Before adding, search existing memories and skip or update if a similar memory already exists. Memories should be self-contained, searchable, and export-friendly for future tools like Obsidian. Use absolute dates for time-sensitive facts. Do not store secrets, API keys, tokens, passwords, or raw \`.env\` values.
Only store genuinely useful learnings that will still matter in two weeks — skip if the task was trivial or merely confirms something worked.
EOF

exit 0
