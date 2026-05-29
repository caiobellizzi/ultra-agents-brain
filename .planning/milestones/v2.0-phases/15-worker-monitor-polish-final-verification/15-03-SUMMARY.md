---
phase: "15-worker-monitor-polish-final-verification"
plan: "15-03"
subsystem: "observability"
tags: ["check-surfaces", "OBS-02", "retrospective", "smoke-checker"]
dependency_graph:
  requires: ["15-01", "15-02"]
  provides: ["OBS-02"]
  affects: ["scripts/check_surfaces.py", "Makefile", "RETROSPECTIVE.md"]
tech_stack:
  added: ["psycopg2 (raw vault count)", "agno.db.postgres.PostgresDb"]
  patterns: ["graceful local-mode fallback (no env var = exit 0)"]
key_files:
  created:
    - scripts/check_surfaces.py
    - RETROSPECTIVE.md
  modified:
    - Makefile
decisions:
  - "Use db.memory_table_name / eval_table_name / approvals_table_name attributes rather than hardcoding table name strings"
  - "Vault count uses separate POSTGRES_DSN_KNOWLEDGE (falls back to sessions DSN if unset)"
  - "Script exits 0 with local-mode warning when POSTGRES_DSN_SESSIONS unset; exits 1 only when surfaces have 0 rows or tables are missing"
metrics:
  duration: "~12 minutes"
  completed: "2026-05-28"
  tasks_completed: 3
  files_created: 2
  files_modified: 1
---

# Phase 15 Plan 03: check-surfaces + RETROSPECTIVE.md Summary

OBS-02 smoke checker (`make check-surfaces`) and v2.0 milestone retrospective delivered. Script queries row counts for all 4 AgentOS surfaces via PostgresDb attribute names (no hardcoded strings), exits 0 in local mode without POSTGRES_DSN_SESSIONS set.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Create scripts/check_surfaces.py | f3f0a29 | scripts/check_surfaces.py |
| 2 | Add check-surfaces Makefile target | 8da80df | Makefile |
| 3 | Write RETROSPECTIVE.md | e4093b6 | RETROSPECTIVE.md |

## Verification

- `python scripts/check_surfaces.py` with no env vars prints local-mode warning and exits 0 — PASSED
- No hardcoded table name strings in check_surfaces.py — PASSED (`grep agno_sessions` returns 0 matches)
- `scripts/check_surfaces.py` is 82 lines (>40 minimum) — PASSED
- `RETROSPECTIVE.md` is 65 lines (>50 minimum) — PASSED
- RETROSPECTIVE.md covers Phase 10 through Phase 18 — PASSED (11 references)
- Makefile contains `check-surfaces:` target — PASSED

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — no new network endpoints, auth paths, or schema changes introduced. `check_surfaces.py` is a read-only diagnostic tool.

## Self-Check: PASSED

- scripts/check_surfaces.py: FOUND
- RETROSPECTIVE.md: FOUND
- Makefile check-surfaces target: FOUND
- Commits f3f0a29, 8da80df, e4093b6: FOUND
