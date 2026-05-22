#!/usr/bin/env bash
# Bidirectional vault sync between local Obsidian vault and VPS second-brain.
#
# Strategy: pull-first to protect VPS-generated content from --delete.
#   Pass 1: VPS → Mac (VPS-generated Inbox items land on Mac before push runs)
#   Pass 2: Mac → VPS --delete (Mac is source of truth; deletions propagate to VPS,
#           but VPS-generated items are safe because they now exist on Mac after Pass 1)
#
# Triggered every 5 min by ~/Library/LaunchAgents/com.ultraagents.vault-sync.plist.
# NOTE: launchd needs Full Disk Access on /bin/bash to read ~/Documents/.
#       System Settings → Privacy & Security → Full Disk Access → add /bin/bash.

set -euo pipefail

LOCAL=/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/vault/
REMOTE=root@31.97.130.253:/srv/second-brain/

EXCLUDES=(
  --exclude '.obsidian/'
  --exclude '.trash/'
  --exclude '.DS_Store'
  --exclude '_system/log.md'
  --exclude '_system/lint-report.md'
  --exclude '_system/monitor-seen.json'
  --exclude '_system/brief-seen.json'
  --exclude '_system/bluesky-seen.json'
)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] pull VPS → Mac"
/usr/bin/rsync -av --update "${EXCLUDES[@]}" "$REMOTE" "$LOCAL"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] push Mac → VPS"
/usr/bin/rsync -av --update --delete "${EXCLUDES[@]}" "$LOCAL" "$REMOTE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] done"
