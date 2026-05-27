#!/usr/bin/env bash
# Pull-before-write + commit-after-write for the vault.
# Usage: git-sync.sh pull | push "commit message"
# Reads VAULT_VPS_PATH and VAULT_DEFAULT_BRANCH from environment.

set -euo pipefail

VAULT_DIR="${VAULT_VPS_PATH:-/srv/second-brain}"
BRANCH="${VAULT_DEFAULT_BRANCH:-main}"
REMOTE="${VAULT_REMOTE:-origin}"

cmd="${1:-pull}"
msg="${2:-vault: auto-sync $(date -u +%Y-%m-%dT%H:%M:%SZ)}"

cd "$VAULT_DIR"

case "$cmd" in
  pull)
    git fetch "$REMOTE" "$BRANCH" --quiet
    BEFORE=$(git rev-parse HEAD)
    git merge --ff-only "$REMOTE/$BRANCH" --quiet || {
      echo "git-sync: fast-forward failed; manual merge required" >&2
      exit 1
    }
    AFTER=$(git rev-parse HEAD)
    if [ "$BEFORE" != "$AFTER" ] && git diff --name-only "$BEFORE" "$AFTER" | grep -q '\.md$'; then
      "$(dirname "$0")/reindex-vault.sh" || true
    fi
    ;;
  push)
    git add -A
    git diff --cached --quiet && { echo "git-sync: nothing to commit"; exit 0; }
    git commit -m "$msg" --quiet
    git push "$REMOTE" "$BRANCH" --quiet
    ;;
  *)
    echo "Usage: git-sync.sh pull | push [message]" >&2
    exit 2
    ;;
esac
