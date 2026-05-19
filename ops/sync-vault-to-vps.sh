#!/usr/bin/env bash
# Push local Obsidian vault clips to the VPS second-brain.
# Triggered by ~/Library/LaunchAgents/com.ultraagents.vault-sync.plist (every 5 min).
set -euo pipefail

LOCAL=/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/vault/
REMOTE=root@31.97.130.253:/srv/second-brain/

rsync -av --update \
  --exclude '.obsidian/' \
  --exclude '.trash/' \
  --exclude '.DS_Store' \
  --exclude '_system/log.md' \
  --exclude '_system/lint-report.md' \
  "$LOCAL" "$REMOTE"
