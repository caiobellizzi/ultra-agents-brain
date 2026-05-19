#!/usr/bin/env bash
set -euo pipefail

SECOND_BRAIN_DIR="${SECOND_BRAIN_DIR:-/srv/second-brain}"
COST_LEDGER="${COST_LEDGER:-$SECOND_BRAIN_DIR/_system/cost-ledger.md}"
DAILY_COST_CAP_USD="${DAILY_COST_CAP_USD:-20}"
COST_WARNING_USD="${COST_WARNING_USD:-}"
DATE_UTC="${DATE_UTC:-$(date -u +%F)}"

telegram_send() {
  message="$1"
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_ALERT_CHAT_ID:-}" ]; then
    curl -fsS "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${TELEGRAM_ALERT_CHAT_ID}" \
      --data-urlencode "text=${message}" >/dev/null || true
  fi
}

sum_today() {
  if [ ! -f "$COST_LEDGER" ]; then
    printf '0.00\n'
    return
  fi

  awk -F'|' -v day="$DATE_UTC" '
    $0 ~ day && NF >= 6 {
      value = ($1 ~ /^[[:space:]]*$/) ? $6 : $5
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      gsub(/^\$/, "", value)
      if (value ~ /^[0-9]+(\.[0-9]+)?$/) {
        total += value
      }
    }
    END { printf "%.2f\n", total + 0 }
  ' "$COST_LEDGER"
}

main() {
  total="$(sum_today)"
  message="ultra-agents-brain cost ${DATE_UTC}: \$${total} / \$${DAILY_COST_CAP_USD}"
  echo "$message"
  warning="${COST_WARNING_USD:-$(awk -v cap="$DAILY_COST_CAP_USD" 'BEGIN { printf "%.2f", cap * 0.8 }')}"

  if awk -v total="$total" -v warning="$warning" -v cap="$DAILY_COST_CAP_USD" 'BEGIN { exit !(total >= warning && total < cap) }'; then
    telegram_send "Cost warning: $message"
  fi

  if awk -v total="$total" -v cap="$DAILY_COST_CAP_USD" 'BEGIN { exit !(total >= cap) }'; then
    telegram_send "COST CAP REACHED: $message"
    exit 1
  fi

  telegram_send "$message"
}

main "$@"
