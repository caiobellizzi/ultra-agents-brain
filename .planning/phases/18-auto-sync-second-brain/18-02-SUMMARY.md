---
phase: "18-auto-sync-second-brain"
plan: "18-02"
subsystem: "vault-sync"
tags: ["pgvector", "reindex", "git-sync", "cron", "flock"]
dependency_graph:
  requires: ["18-01"]
  provides: ["reindex-vault.sh", "git-sync-reindex-trigger"]
  affects: ["vault-ingest", "knowledge-search"]
tech_stack:
  added: ["flock (util-linux)"]
  patterns: ["flock-guarded cron wrapper", "BEFORE/AFTER HEAD capture for conditional reindex"]
key_files:
  created:
    - scripts/reindex-vault.sh
  modified:
    - scripts/git-sync.sh
decisions:
  - "flock -n used (non-blocking) so concurrent reindex invocations skip gracefully and cron never breaks"
  - "reindex-vault.sh always exits 0 to prevent cron from entering error state"
  - "Reindex triggered only when BEFORE != AFTER and at least one .md file changed — no-op pulls stay cheap"
  - "Invocation via $(dirname $0)/reindex-vault.sh keeps path resolution relative to script location regardless of deploy path"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-27"
  tasks_total: 4
  tasks_completed: 4
  files_created: 1
  files_modified: 1
---

# Phase 18 Plan 02: Reindex helper + git-sync trigger + VPS deploy Summary

## One-liner

flock-guarded `reindex-vault.sh` wrapper with conditional trigger in `git-sync.sh` on `.md` changes after HEAD advance.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 18-02-A | Create scripts/reindex-vault.sh | 2761845 | Done |
| 18-02-B | Extend git-sync.sh pull branch with BEFORE/AFTER + reindex trigger | 2761845 | Done |
| 18-02-C | Commit both scripts | 2761845 | Done |
| 18-02-D | Deploy to VPS and verify end-to-end | 60df50b, ecdad1b | Done |

## What Was Built

**`scripts/reindex-vault.sh`** (21 lines):
- Sources `/opt/ultra-agents-brain/.env` for `POSTGRES_DSN_KNOWLEDGE`
- Uses `/opt/ultra-agents-brain/.venv/bin/python -m agentos.knowledge --reindex`
- Appends all output to `$APP_DIR/logs/reindex.log`
- Uses `flock -n` for non-blocking concurrency guard — concurrent runs log "another reindex in progress; skipping" and exit 0
- Always `exit 0` so cron is never broken by reindex failures

**`scripts/git-sync.sh` pull branch** (5 new lines):
- Captures `BEFORE=$(git rev-parse HEAD)` before merge
- Captures `AFTER=$(git rev-parse HEAD)` after merge
- Only invokes `reindex-vault.sh` when `BEFORE != AFTER` AND `git diff --name-only` includes at least one `.md` file
- No-op pulls (nothing fetched, or only non-.md files changed) skip reindex entirely

## VPS Deploy & Smoke Test Results

Scripts deployed via scp to `/opt/ultra-agents-brain/scripts/`. Two post-deploy fixes required:

- **`60df50b`** — `cd "$APP_DIR"` before flock: `agentos` is a local module in `/opt/ultra-agents-brain/`, not a pip package
- **`ecdad1b`** — `set -a` / `set +a` around `.env` source: bare assignments aren't inherited by flock subprocess, so `POSTGRES_DSN_KNOWLEDGE` wasn't reaching Python

Smoke tests (all passed):
- ✓ Reindex triggered on `.md` change: sentinel commit pushed to GitHub → `git-sync.sh pull` → `repos/ultra-agents-brain.md` indexed in 0.78s
- ✓ Concurrency guard: "another reindex in progress; skipping" logged, exit 0
- ✓ Full log entry: `[indexed] repos/ultra-agents-brain.md`, `Indexed 1 files (1554 skipped, 0 errors)`

## Deviations from Plan

Two fixes required during VPS deploy (see above). Core design unchanged.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes. The reindex script runs as `uabrain` with existing credentials sourced from `.env`.

## Self-Check: PASSED

- `scripts/reindex-vault.sh` exists, executable, syntax-valid, contains `flock -n`, sources `.env`, ends with `exit 0`
- `scripts/git-sync.sh` syntax-valid, contains `BEFORE=`, `AFTER=`, and `reindex-vault.sh` invocation inside guarded `if`
- Commit `2761845` exists and lists both files in `--stat`
