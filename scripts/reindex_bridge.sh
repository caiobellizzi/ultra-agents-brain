#!/usr/bin/env bash
# Post-commit hook: triggers codebase-memory-mcp reindex + writes ARCHITECTURE.md to vault.
#
# Install per repo:
#   cp scripts/reindex_bridge.sh .git/hooks/post-commit && chmod +x .git/hooks/post-commit
#
# This hook is non-blocking — exits 0 always so it never prevents commits.

# Resolve repo root from wherever the hook runs
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ROOT" ]; then
  echo "[reindex_bridge] WARNING: could not determine repo root via git; skipping." >&2
  exit 0
fi

# Derive slug: basename of repo root, lowercased, spaces/underscores → hyphens
REPO_SLUG="$(basename "$REPO_ROOT" | tr '[:upper:]' '[:lower:]' | tr ' _' '--')"

# Vault path: prefer env var, fall back to ~/Documents/second-brain
VAULT_PATH="${VAULT_PATH:-$HOME/Documents/second-brain}"

# codebase-memory-mcp project name: mirrors what the tool uses (path-derived)
# The tool uses the full path with slashes replaced by dashes
REPO_ROOT_CLEAN="${REPO_ROOT#/}"          # strip leading /
PROJECT_NAME="${REPO_ROOT_CLEAN//\//-}"   # replace / with -

ARCH_TMP="/tmp/uab-arch-summary-${REPO_SLUG}.txt"

# ── Step 1: Check codebase-memory-mcp is available ──────────────────────────
if ! command -v codebase-memory-mcp >/dev/null 2>&1; then
  echo "[reindex_bridge] WARNING: codebase-memory-mcp not found on PATH; skipping reindex." >&2
  exit 0
fi

# ── Step 2: Trigger detect_changes + reindex ────────────────────────────────
echo "[reindex_bridge] Detecting changes for project: $PROJECT_NAME" >&2
if ! codebase-memory-mcp cli detect_changes "{\"project\":\"$PROJECT_NAME\"}" >/dev/null 2>&1; then
  echo "[reindex_bridge] WARNING: detect_changes failed (project may not be indexed yet); attempting index_repository." >&2
  if ! codebase-memory-mcp cli index_repository "{\"path\":\"$REPO_ROOT\"}" >/dev/null 2>&1; then
    echo "[reindex_bridge] WARNING: index_repository failed; skipping architecture export." >&2
    exit 0
  fi
fi

# ── Step 3: Export architecture summary ─────────────────────────────────────
echo "[reindex_bridge] Exporting architecture for project: $PROJECT_NAME" >&2
if ! codebase-memory-mcp cli get_architecture "{\"project\":\"$PROJECT_NAME\"}" >"$ARCH_TMP" 2>/dev/null; then
  echo "[reindex_bridge] WARNING: get_architecture failed; skipping vault write." >&2
  exit 0
fi

# Verify the output is non-empty and looks like valid content (not just an error JSON)
if [ ! -s "$ARCH_TMP" ]; then
  echo "[reindex_bridge] WARNING: architecture output is empty; skipping vault write." >&2
  exit 0
fi

# ── Step 4: Write vault/repos/<slug>/ARCHITECTURE.md ────────────────────────
VAULT_REPO_DIR="$VAULT_PATH/vault/repos/$REPO_SLUG"
# Try without /vault/ prefix if standard path doesn't exist or vault is the root
if [ ! -d "$VAULT_PATH/vault" ]; then
  VAULT_REPO_DIR="$VAULT_PATH/repos/$REPO_SLUG"
fi

mkdir -p "$VAULT_REPO_DIR" || {
  echo "[reindex_bridge] WARNING: could not create $VAULT_REPO_DIR; skipping vault write." >&2
  exit 0
}

ARCH_MD="$VAULT_REPO_DIR/ARCHITECTURE.md"
ISO_TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

{
  echo "# Architecture — $REPO_SLUG"
  echo ""
  echo "Updated: $ISO_TS"
  echo ""
  echo "---"
  echo ""
  cat "$ARCH_TMP"
} > "$ARCH_MD"

echo "[reindex_bridge] Architecture written to $ARCH_MD" >&2

# Cleanup
rm -f "$ARCH_TMP"

# Always exit 0 — post-commit hooks must never block commits
exit 0
