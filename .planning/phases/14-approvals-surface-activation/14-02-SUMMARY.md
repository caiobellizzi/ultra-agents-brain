---
phase: 14-approvals-surface-activation
plan: "02"
subsystem: channels/telegram_adapter
tags: [approvals, telegram, hitl, tdd, appr-02]
requirements: [APPR-02]

dependency_graph:
  requires: [14-01]
  provides: [_resolve_approval_row, TestApprovalBridge]
  affects: [channels/telegram_adapter.py, tests/test_telegram_adapter.py]

tech_stack:
  added: []
  patterns:
    - GET /approvals then POST /approvals/{id}/resolve before /continue
    - 409-as-idempotent-success on resolve
    - _RESOLVED_RUNS guard release on resolve failure for retry

key_files:
  created: []
  modified:
    - channels/telegram_adapter.py
    - tests/test_telegram_adapter.py

decisions:
  - Fall back to first approval row when tool_call_id is absent in row data (T-14-04 mitigation)
  - 409 on POST /approvals/{id}/resolve treated as idempotent success — allows retry-safe behavior
  - Resolve failure releases _RESOLVED_RUNS guard so user can retry (T-14-05 mitigation)
  - Wiring point is after _RESOLVED_RUNS.add(run_id) and before /continue POST — preserves ordering guarantee

metrics:
  duration: "4 minutes"
  completed: "2026-05-27T22:58:12Z"
  tasks_completed: 2
  files_changed: 2
---

# Phase 14 Plan 02: _resolve_approval_row Bridge — APPR-02 Summary

Implemented `_resolve_approval_row` async helper in `channels/telegram_adapter.py` and wired it into `handle_callback` so every Approve/Deny tap first resolves the native `ai.agno_approvals` row before calling `/continue`. This closes the APPR-02 gap where `/continue` previously ran while leaving the approval row in `status='pending'`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (RED) | Write failing TestApprovalBridge tests | c4c7a62 | tests/test_telegram_adapter.py |
| 2 (GREEN) | Add _resolve_approval_row and wire into handle_callback | 2b39f2c | channels/telegram_adapter.py, tests/test_telegram_adapter.py |

## What Was Built

### `_resolve_approval_row` helper (channels/telegram_adapter.py)

New async function placed directly before `handle_callback`:

- GET `{AGENTOS_BASE_URL}/approvals?run_id=&status=pending&approval_type=required`
- Matches approval row by `tool_call_id`; falls back to first row if no match
- POST `{AGENTOS_BASE_URL}/approvals/{approval_id}/resolve` with `{status, resolved_by, resolution_data}`
- 409 response treated as idempotent success (row already resolved by a prior tap)
- All failures log at WARNING/ERROR level and return `False` — never raise
- Returns `True` on success or 409, `False` on any failure

### Wiring in `handle_callback`

Inserted between `_RESOLVED_RUNS.add(run_id)` and `cached = _PAUSED_TOOLS.pop(...)`:

```python
resolved = await _resolve_approval_row(client, run_id, tool_call_id, confirmed, tg_user_id)
if not resolved:
    await send_message(client, chat_id, "Approval update failed — please try again.")
    _RESOLVED_RUNS.discard(run_id)
    return
```

### TestApprovalBridge class (tests/test_telegram_adapter.py)

4 tests covering the APPR-02 bridge behavior:

- `test_approve_resolves_then_continues` (14-02-01): asserts POST /approvals/{id}/resolve with `status=approved` before /continue
- `test_deny_resolves_rejected` (14-02-02): asserts `status=rejected` and /continue still called
- `test_resolve_failure_releases_guard` (14-02-03): asserts /continue skipped, guard released, Telegram error sent on 500
- `test_resolve_409_is_ok` (14-02-04): asserts /continue called when resolve returns 409

## Verification Results

```
pytest tests/test_telegram_adapter.py::TestApprovalBridge -v  → 4 passed
pytest tests/test_telegram_adapter.py -v                      → 32 passed, 2 failed (pre-existing)
pytest tests/test_approval_recorder.py -v                     → 8 passed
```

Full adapter test suite: 40 tests pass. Only 2 pre-existing routing failures remain
(`TestRoutingLogic::test_plain_text_routes_to_supervisor` and `test_unknown_command_falls_back_to_supervisor`
— these were failing before this plan and are out of scope).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated TestApproveDoubleTap and TestCallbackDataValidation to mock client.get**

- **Found during:** Task 2 GREEN verification
- **Issue:** After adding `_resolve_approval_row`, existing tests that used bare `AsyncMock()` without configuring `client.get` received a non-200 mock status from the new GET /approvals call, causing `_resolve_approval_row` to return `False` — which released the `_RESOLVED_RUNS` guard and prevented /continue from being called. This broke `TestApproveDoubleTap::test_second_callback_skips_post_entirely`.
- **Fix:** Added `client.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {"data": [...]}))` to all three affected test methods in `TestApproveDoubleTap` and `TestCallbackDataValidation._run_handle_callback`.
- **Files modified:** tests/test_telegram_adapter.py
- **Commit:** 2b39f2c (included in GREEN commit)

## TDD Gate Compliance

- RED gate: Commit `c4c7a62` — `test(14-02): add failing TestApprovalBridge tests` — 3/4 tests failed
- GREEN gate: Commit `2b39f2c` — `feat(14-02): add _resolve_approval_row and wire into handle_callback` — 4/4 tests pass

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. The `_resolve_approval_row` function calls existing AgentOS approval endpoints that were already planned in the threat model (T-14-04, T-14-05, T-14-06, T-14-07 — all addressed per plan disposition).

## Self-Check: PASSED

- [x] `channels/telegram_adapter.py` contains `async def _resolve_approval_row`
- [x] `channels/telegram_adapter.py` contains `await _resolve_approval_row` (wiring present)
- [x] `tests/test_telegram_adapter.py` contains `class TestApprovalBridge`
- [x] Commit `c4c7a62` exists (RED)
- [x] Commit `2b39f2c` exists (GREEN)
- [x] 4 TestApprovalBridge tests pass
- [x] APPR-02 requirement satisfied at unit test level
