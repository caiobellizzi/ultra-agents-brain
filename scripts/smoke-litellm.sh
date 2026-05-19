#!/usr/bin/env bash
set -euo pipefail

LITELLM_BASE_URL="${LITELLM_BASE_URL:-http://127.0.0.1:4000/v1}"
MODELS="${MODELS:-orchestrator default-worker cheap-worker private-worker fallback}"

require_env() {
  name="$1"
  if [ -z "${!name:-}" ]; then
    echo "Missing required env var: $name" >&2
    exit 1
  fi
}

post_chat() {
  model="$1"
  curl -fsS "$LITELLM_BASE_URL/chat/completions" \
    -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"$model\",
      \"messages\": [{\"role\": \"user\", \"content\": \"Reply with ok.\"}],
      \"max_tokens\": 8
    }" >/dev/null
}

main() {
  require_env LITELLM_MASTER_KEY

  for model in $MODELS; do
    printf 'smoke %s ... ' "$model"
    post_chat "$model"
    printf 'ok\n'
  done
}

main "$@"
