#!/usr/bin/env bash
# Bidirectional vault sync between local Obsidian vault and VPS second-brain.
#
# Strategy: two rsync passes with --update (newer mtime wins, no deletions).
#   Pass 1: VPS → Mac (so locally-opened Obsidian sees agent-written notes)
#   Pass 2: Mac → VPS (so Web Clipper notes reach AgentOS agents)
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
)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] push Mac → VPS"
/usr/bin/rsync -av --update --delete "${EXCLUDES[@]}" "$LOCAL" "$REMOTE"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] pull VPS → Mac"
/usr/bin/rsync -av --update "${EXCLUDES[@]}" "$REMOTE" "$LOCAL"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] done"
