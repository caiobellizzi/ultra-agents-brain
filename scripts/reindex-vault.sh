#!/usr/bin/env bash
# Flock-guarded pgvector reindex wrapper. Always exits 0 so cron is never broken.
set -euo pipefail

APP_DIR=/opt/ultra-agents-brain
LOCK=/tmp/uab-reindex.lock
LOG="$APP_DIR/logs/reindex.log"

exec >> "$LOG" 2>&1
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] reindex-vault: starting"

# shellcheck source=/dev/null
[ -f "$APP_DIR/.env" ] && . "$APP_DIR/.env"

if flock -n "$LOCK" "$APP_DIR/.venv/bin/python" -m agentos.knowledge --reindex; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] reindex-vault: complete"
else
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] reindex-vault: another reindex in progress; skipping"
fi

exit 0
