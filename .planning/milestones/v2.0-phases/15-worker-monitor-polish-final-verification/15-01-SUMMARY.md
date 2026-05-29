---
phase: "15-worker-monitor-polish-final-verification"
plan: "15-01"
subsystem: "brief"
tags: [bugfix, tdd, lookback, inbox, daily-brief]
dependency_graph:
  requires: []
  provides: [MON-01-fix]
  affects: [ultra_brain/brief.py]
tech_stack:
  added: []
  patterns: [TDD RED/GREEN, lookback glob loop, seen_paths dedup set]
key_files:
  created:
    - tests/unit/test_brief.py
    - ultra_brain/llm.py
  modified:
    - ultra_brain/brief.py
decisions:
  - "lookback_days defaults to 2 so the fix is zero-config for existing callers"
  - "seen_paths set guards against duplicate file reads if same file matches two offsets (impossible with date-prefixed names, defensive)"
  - "llm.py copied from main repo (was untracked) to unblock import in worktree"
metrics:
  duration: "3m"
  completed: "2026-05-28"
  tasks_completed: 2
  tasks_total: 3
  files_created: 2
  files_modified: 1
---

# Phase 15 Plan 01: Fix daily-brief date-mismatch bug (MON-01) Summary

**One-liner:** `_read_inbox_items` now globs `lookback_days=2` prior calendar days so monitor-filed items from the previous evening are never silently dropped.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | RED: Write failing regression tests | d960574 | tests/unit/test_brief.py, ultra_brain/llm.py |
| 2 | GREEN: Fix _read_inbox_items | 7ac1e75 | ultra_brain/brief.py |
| 3 | REFACTOR: Clean up | skipped (code already clean) | — |

## What Was Built

Fixed the date-mismatch bug in `ultra_brain/brief.py::_read_inbox_items`. The function previously globbed `{day.isoformat()}-*.md` using only the single `day` argument. If the monitor ran late evening on day D and the brief ran morning of day D+1, all items filed on D were silently dropped.

**Fix:** Added `lookback_days: int = 2` parameter. The function now iterates `range(lookback_days)` and globs each prior day's Inbox files. A `seen_paths` set guards against reading the same file twice. The `daily_brief` caller passes no `lookback_days` argument — the default of 2 applies automatically.

**TDD Gate compliance:**
- RED commit `d960574`: `test(15-01): add RED regression tests` — `test_date_lookback_catches_yesterday_items` failed before fix (0 items returned), remaining 3 passed.
- GREEN commit `7ac1e75`: `feat(15-01): fix _read_inbox_items` — all 4 tests pass.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Missing ultra_brain/llm.py in worktree**
- **Found during:** Task 1 (import error when collecting test module)
- **Issue:** `ultra_brain/llm.py` was an untracked file in the main repo — not committed — so the worktree (based on ebc32d5) did not have it. `brief.py` imports `from . import llm` which failed at collection time.
- **Fix:** Copied `llm.py` from the main repo into the worktree and staged it alongside the tests in the Task 1 commit.
- **Files modified:** `ultra_brain/llm.py` (created)
- **Commit:** d960574

## Regression Check

Ran `PYTHONPATH=. pytest tests/ --ignore=tests/test_core.py -q` after the fix:
- 4 failures — all pre-existing, unrelated to brief.py changes (MEM-01 SLA, curator/research agent model config, monitor.move_to_trash attribute).
- 147 passed, 2 skipped. Zero regressions introduced.

## Known Stubs

None.

## Threat Flags

None — changes are pure filesystem-read logic with no network, auth, or new trust boundaries.

## Self-Check: PASSED

- [x] tests/unit/test_brief.py exists
- [x] ultra_brain/llm.py exists
- [x] ultra_brain/brief.py contains `lookback_days: int = 2`
- [x] ultra_brain/brief.py contains `timedelta` import
- [x] Commit d960574 exists (test)
- [x] Commit 7ac1e75 exists (feat)
