#!/usr/bin/env bash
set -euo pipefail

LITELLM_BASE_URL="${LITELLM_BASE_URL:-http://127.0.0.1:4000/v1}"
LINT_MODEL="${LINT_MODEL:-default-worker}"
SECOND_BRAIN_DIR="${SECOND_BRAIN_DIR:-/srv/second-brain}"
LINT_REPORT="${LINT_REPORT:-$SECOND_BRAIN_DIR/_system/lint-report.md}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${UAB_PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

require_env() {
  name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required env var: $name" >&2
    exit 1
  fi
}

telegram_send() {
  message="$1"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_ALERT_CHAT_ID:-}" ]; then
    curl -fsS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_ALERT_CHAT_ID}" \
      --data-urlencode "text=${message}" >/dev/null || true
  fi
}

main() {
  mkdir -p "$(dirname "$LINT_REPORT")"

  if [ -d "$PROJECT_ROOT/ultra_brain" ]; then
    PYTHONPATH="$PROJECT_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -m ultra_brain --vault "$SECOND_BRAIN_DIR" lint >/dev/null
  else
    require_env LITELLM_MASTER_KEY
    prompt="Create a concise weekly second-brain lint checklist for vault path $SECOND_BRAIN_DIR. Focus on contradictions, orphan pages, stale claims, progressive summarization, and missing citations."
    tmp="$(mktemp)"
    trap 'rm -f "$tmp"' EXIT

    curl -fsS "$LITELLM_BASE_URL/chat/completions" \
      -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
      -H "Content-Type: application/json" \
      -d "{
        \"model\": \"$LINT_MODEL\",
        \"messages\": [{\"role\": \"user\", \"content\": \"$prompt\"}],
        \"max_tokens\": 800
      }" >"$tmp"

    {
      printf '# Brain Lint Report\n\n'
      printf 'Generated: %s\n\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      jq -r '.choices[0].message.content // .' "$tmp"
      printf '\n'
    } >"$LINT_REPORT"
  fi

  telegram_send "Brain lint report updated: $LINT_REPORT"
  echo "Wrote $LINT_REPORT"
}

main "$@"
