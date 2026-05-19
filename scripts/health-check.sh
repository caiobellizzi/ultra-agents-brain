#!/usr/bin/env bash
set -euo pipefail

QUIET=0
[ "${1:-}" = "--quiet" ] && QUIET=1

LITELLM_HEALTH_URL="${LITELLM_HEALTH_URL:-http://127.0.0.1:4000/health/liveliness}"
HERMES_HEALTH_URL="${HERMES_HEALTH_URL:-http://127.0.0.1:8787/health}"
SECOND_BRAIN_DIR="${SECOND_BRAIN_DIR:-/srv/second-brain}"
DISK_PATH="${DISK_PATH:-/}"
DISK_MAX_PERCENT="${DISK_MAX_PERCENT:-85}"

failures=""

append_failure() {
  failures="${failures}
- $1"
}

telegram_send() {
  message="$1"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_ALERT_CHAT_ID:-}" ]; then
    curl -fsS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_ALERT_CHAT_ID}" \
      --data-urlencode "text=${message}" >/dev/null || true
  fi
}

check_url() {
  name="$1"
  url="$2"
  if ! curl -fsS --max-time 10 "$url" >/dev/null; then
    append_failure "$name unreachable at $url"
  fi
}

check_telegram() {
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    if ! curl -fsS --max-time 10 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" >/dev/null; then
      append_failure "Telegram bot getMe failed"
    fi
  elif [ "$QUIET" -eq 0 ]; then
    echo "Skipping Telegram check; TELEGRAM_BOT_TOKEN is not set."
  fi
}

check_docker_service() {
  service="$1"
  if command -v docker >/dev/null 2>&1; then
    if ! docker compose -f "${COMPOSE_FILE:-/opt/ultra-agents-brain/deploy/docker-compose.yml}" ps --status running "$service" 2>/dev/null | grep -q "$service"; then
      append_failure "Docker Compose service not running: $service"
    fi
  fi
}

check_vault_git() {
  if [ -d "$SECOND_BRAIN_DIR/.git" ]; then
    tmp_status="$(mktemp)"
    if ! git -C "$SECOND_BRAIN_DIR" status --porcelain >"$tmp_status" 2>/dev/null; then
      rm -f "$tmp_status"
      append_failure "Vault git status failed at $SECOND_BRAIN_DIR"
      return
    fi
    if [ -s "$tmp_status" ] && [ "${ALLOW_DIRTY_VAULT:-0}" != "1" ]; then
      append_failure "Vault has uncommitted changes at $SECOND_BRAIN_DIR"
    fi
    rm -f "$tmp_status"
  else
    append_failure "Vault git checkout missing at $SECOND_BRAIN_DIR"
  fi
}

check_disk() {
  used="$(df -P "$DISK_PATH" | awk 'NR==2 {gsub(/%/, "", $5); print $5}')"
  if [ -z "$used" ] || [ "$used" -ge "$DISK_MAX_PERCENT" ]; then
    append_failure "Disk usage ${used:-unknown}% on $DISK_PATH exceeds ${DISK_MAX_PERCENT}%"
  fi
}

main() {
  check_url LiteLLM "$LITELLM_HEALTH_URL"
  check_url Hermes "$HERMES_HEALTH_URL"
  check_telegram
  check_docker_service litellm
  check_docker_service hermes
  check_vault_git
  check_disk

  if [ -n "$failures" ]; then
    message="ultra-agents-brain health check FAILED:${failures}"
    echo "$message" >&2
    telegram_send "$message"
    exit 1
  fi

  message="ultra-agents-brain health check OK"
  [ "$QUIET" -eq 0 ] && echo "$message"
  [ "${HEALTH_NOTIFY_ON_SUCCESS:-0}" = "1" ] && telegram_send "$message"
}

main "$@"
