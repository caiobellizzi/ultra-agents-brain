#!/usr/bin/env bash
# Post-commit hook: triggers codebase-memory-mcp reindex.
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

# codebase-memory-mcp project name: mirrors what the tool uses (path-derived)
# The tool uses the full path with slashes replaced by dashes
REPO_ROOT_CLEAN="${REPO_ROOT#/}"          # strip leading /
PROJECT_NAME="${REPO_ROOT_CLEAN//\//-}"   # replace / with -

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
    echo "[reindex_bridge] WARNING: index_repository failed; skipping." >&2
    exit 0
  fi
fi

# Always exit 0 — post-commit hooks must never block commits
exit 0
