---
phase: 14-approvals-surface-activation
plan: "01"
subsystem: agentos
tags: [observability, approvals, logging, tdd, obs-01]
dependency_graph:
  requires: []
  provides: [approval-recorder, obs-01-approval-logging]
  affects: [agentos/app.py, agentos/approval_recorder.py]
tech_stack:
  added: []
  patterns: [instance-level-method-replacement, log-and-swallow, idempotency-sentinel]
key_files:
  created:
    - agentos/approval_recorder.py
    - tests/test_approval_recorder.py
  modified:
    - agentos/app.py
decisions:
  - "Used 'is True' sentinel check instead of truthiness to handle MagicMock auto-attributes in tests"
  - "Instance-level method replacement on db object (not class-level) — mirrors RESEARCH.md pattern D-09"
  - "Idempotency guard on instance attribute _approval_recorder_patched (not class attribute)"
metrics:
  duration: "~20 minutes"
  completed: "2026-05-27"
  tasks_completed: 2
  files_changed: 3
---

# Phase 14 Plan 01: Approval Recorder Implementation Summary

**One-liner:** OBS-01 instance-level DB method wrapper emitting structured JSON log lines for all three Agno approval lifecycle events (create/resolve/run_status).

## What Was Built

`agentos/approval_recorder.py` — a DB method interceptor that patches `db.create_approval`, `db.update_approval`, and `db.update_approval_run_status` on the shared db instance at startup. Each patched method records call latency, extracts relevant approval fields, and emits a structured OBS-01 JSON log line via `logging.getLogger("agentos.approval")`. The patch is idempotent and emit failures are non-fatal.

`tests/test_approval_recorder.py` — 8 unit tests covering the full approval lifecycle wrapper behavior.

`agentos/app.py` — two lines added immediately after the eval_recorder wiring: import and call of `patch_db_for_approval_recording(db=db)`.

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Write failing tests for approval_recorder.py | 83ae205 | tests/test_approval_recorder.py |
| 2 (GREEN) | Implement approval_recorder.py and wire into app.py | 8fb83c1 | agentos/approval_recorder.py, agentos/app.py, tests/test_approval_recorder.py |

## TDD Gate Compliance

- RED gate: `test(14-01)` commit `83ae205` — 8 tests fail with ModuleNotFoundError
- GREEN gate: `feat(14-01)` commit `8fb83c1` — all 8 tests pass
- REFACTOR: not needed, implementation is clean

## Verification Results

```
PASSED tests/test_approval_recorder.py::TestApprovalRecorder::test_create_approval_logs_ok
PASSED tests/test_approval_recorder.py::TestApprovalRecorder::test_idempotent_patch
PASSED tests/test_approval_recorder.py::TestApprovalRecorder::test_log_failure_nonfatal
PASSED tests/test_approval_recorder.py::TestApprovalRecorder::test_obs_log_on_create
PASSED tests/test_approval_recorder.py::TestApprovalRecorder::test_sqlite_fallback_no_503
PASSED tests/test_approval_recorder.py::TestApprovalRecorder::test_tool_name_in_approval_data
PASSED tests/test_approval_recorder.py::TestApprovalRecorder::test_update_approval_logs_resolve
PASSED tests/test_approval_recorder.py::TestApprovalRecorder::test_update_run_status_logs
8 passed in 0.37s
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] MagicMock sentinel truthiness caused patch to be a no-op**
- **Found during:** Task 2 (GREEN) — tests all passed import but `assertLogs` captured nothing
- **Issue:** `getattr(db, "_approval_recorder_patched", False)` on a MagicMock returns a MagicMock child attribute (truthy), causing `patch()` to return immediately without wrapping anything
- **Fix:** Changed to `getattr(db, "_approval_recorder_patched", None) is True` — only exits if the sentinel is literally `True`
- **Files modified:** agentos/approval_recorder.py
- **Commit:** 8fb83c1

**2. [Rule 1 - Bug] Wrong SqliteDb constructor argument in test**
- **Found during:** Task 2 (GREEN) — test 7 failed with TypeError
- **Issue:** Plan specified `SqliteDb(db_path=...)` but actual constructor argument is `db_file=`
- **Fix:** Updated test to use `SqliteDb(db_file=db_file)`
- **Files modified:** tests/test_approval_recorder.py
- **Commit:** 8fb83c1

**3. [Rule 3 - Blocking] Pre-commit hook failed in worktree — .venv not found**
- **Found during:** Task 2 commit attempt
- **Issue:** `tools/precommit_eval_router.sh` uses `.venv/bin/pytest` relative path; worktrees don't have a `.venv` directory
- **Fix:** Created `.venv` symlink in worktree pointing to main project's `.venv` (`ln -s /path/to/main/.venv .venv`)
- **Note:** Pre-existing worktree limitation; symlink not staged in git (it's a filesystem-level fix)

**4. [Observation] update_approval signature differs from plan**
- **Found during:** Task 1 (reading agno db base.py)
- **Plan specified:** `update_approval(approval_id: str, update_data: dict)`
- **Actual signature:** `update_approval(approval_id: str, expected_status: Optional[str] = None, **kwargs: Any)`
- **Fix:** Tests and implementation use correct `**kwargs` form (e.g. `db.update_approval("ap-1", status="approved")`)
- **No blocker:** Implementation adapted cleanly

## Known Stubs

None — all three approval lifecycle methods are fully wired with real OBS logging.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundary changes. The approval_recorder operates entirely in-process on the shared db instance. OBS log goes to stdout/stderr via the logging module. No new external surface.

## Self-Check: PASSED

- [x] `agentos/approval_recorder.py` exists: FOUND
- [x] `tests/test_approval_recorder.py` exists: FOUND
- [x] Commit `83ae205` (RED): FOUND
- [x] Commit `8fb83c1` (GREEN): FOUND
- [x] `patch_db_for_approval_recording` in `agentos/app.py`: FOUND (lines 72-73)
- [x] `_approval_recorder_patched` in `agentos/approval_recorder.py`: FOUND (lines 48, 162)
- [x] 8 tests pass: CONFIRMED
