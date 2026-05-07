#!/usr/bin/env bash
# Hook: UserPromptSubmit
#
# Fires on every user message. Searches mem0 for relevant memories
# and injects them into Claude's context before processing.
#
# Input:  JSON on stdin with prompt, session_id, cwd, transcript_path
# Output: Matching memories as context text (exit 0)
#
# Skips search for very short prompts and when no Mem0 API key is set.
# Uses a short timeout and compact result set to avoid overloading context.

# Intentionally omit -e so the script always exits 0 even if
# curl or jq fail — must never block the user's prompt.
set -uo pipefail

INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""' 2>/dev/null || echo "")
CWD=$(echo "$INPUT" | jq -r '.cwd // ""' 2>/dev/null || echo "")

# Skip trivial prompts — not worth a network call
MIN_CHARS="${MEM0_SEARCH_MIN_CHARS:-30}"
if [ ${#PROMPT} -lt "$MIN_CHARS" ]; then
  exit 0
fi

MEM0_BACKEND="${MEM0_BACKEND:-hosted}"
SELF_HOSTED_API_URL=""
if [ "$MEM0_BACKEND" = "self_hosted" ]; then
  SELF_HOSTED_API_URL="${MEM0_SELF_HOSTED_API_URL:-${MEM0_API_URL:-}}"
fi
SELF_HOSTED_API_KEY="${MEM0_SELF_HOSTED_API_KEY:-}"
HOSTED_API_KEY="${MEM0_API_KEY:-}"

API_KEY="$HOSTED_API_KEY"
if [ -n "$SELF_HOSTED_API_URL" ]; then
  API_KEY="$SELF_HOSTED_API_KEY"
fi

if [ -z "$API_KEY" ]; then
  exit 0
fi

USER_ID="${MEM0_USER_ID:-${USER:-default}}"
AGENT_ID="${MEM0_AGENT_ID:-codex}"
TOP_K="${MEM0_SEARCH_TOP_K:-3}"
THRESHOLD="${MEM0_SEARCH_THRESHOLD:-0.2}"
RERANK="${MEM0_SEARCH_RERANK:-true}"
MAX_MEMORY_CHARS="${MEM0_SEARCH_MAX_MEMORY_CHARS:-600}"
QUERY="$PROMPT"
if [ -n "$CWD" ]; then
  QUERY="$PROMPT

Current working directory: $CWD"
fi

if [ -n "$SELF_HOSTED_API_URL" ]; then
  BODY=$(jq -n --arg query "$QUERY" --arg user_id "$USER_ID" --argjson top_k "$TOP_K" \
    '{query: $query, user_id: $user_id, top_k: $top_k}')

  RESPONSE=$(curl -s --max-time 3 \
    -X POST "${SELF_HOSTED_API_URL%/}/search" \
    -H "X-API-Key: $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$BODY" \
    2>/dev/null || echo "")
else
  BODY=$(jq -n \
    --arg query "$QUERY" \
    --arg user_id "$USER_ID" \
    --arg agent_id "$AGENT_ID" \
    --argjson top_k "$TOP_K" \
    --argjson threshold "$THRESHOLD" \
    --argjson rerank "$RERANK" \
    '{query: $query, filters: {OR: [{user_id: $user_id}, {agent_id: $agent_id}]}, top_k: $top_k, threshold: $threshold, rerank: $rerank}')

  RESPONSE=$(curl -s --max-time 3 \
    -X POST "${MEM0_SEARCH_API_URL:-https://api.mem0.ai/v3/memories/search/}" \
    -H "Authorization: Token $API_KEY" \
    -H "Content-Type: application/json" \
    -d "$BODY" \
    2>/dev/null || echo "")
fi

if [ -z "$RESPONSE" ]; then
  exit 0
fi

# Extract memories from response (API returns a flat array)
MEMORIES=$(echo "$RESPONSE" | jq -r '
  def compact_memory($max):
    if length > $max then .[0:($max - 1)] + "…" else . end;

  if type == "array" then . else .results // [] end |
  if length == 0 then empty else
  "## Relevant memories from mem0\n\n" +
  (map(select(.memory != null) | "- " + (.memory | compact_memory($max_memory_chars))) | join("\n"))
  end
' --argjson max_memory_chars "$MAX_MEMORY_CHARS" 2>/dev/null || echo "")

if [ -n "$MEMORIES" ]; then
  echo "$MEMORIES"
fi

exit 0
