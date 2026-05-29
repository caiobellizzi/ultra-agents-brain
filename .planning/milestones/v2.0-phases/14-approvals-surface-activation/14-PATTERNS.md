# Phase 14: Approvals Surface Activation - Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 5
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `agentos/approval_recorder.py` (NEW) | service/instrumentation | event-driven (DB method patch) | `agentos/eval_recorder.py` | exact |
| `channels/telegram_adapter.py` (MODIFY) | adapter/controller | request-response (callback bridge) | `channels/telegram_adapter.py` (self) | self |
| `agentos/app.py` (MODIFY) | config/wiring | CRUD (startup instrumentation) | `agentos/app.py` (self, eval recorder wiring) | self |
| `tests/test_approval_recorder.py` (NEW) | test | event-driven | `tests/test_agentos.py`, `tests/test_telegram_adapter.py` | role-match |
| `tests/test_telegram_adapter.py` (MODIFY) | test | request-response | `tests/test_telegram_adapter.py` (self) | self |

---

## Pattern Assignments

### `agentos/approval_recorder.py` (NEW — instrumentation service)

**Primary analog:** `agentos/eval_recorder.py`
**Secondary analog:** `agentos/instrumented_memory.py` (for DB-method-patch approach)
**Tertiary analog:** `agentos/instrumented_knowledge.py` (for `_emit` schema discipline)

**Imports pattern** (from `agentos/eval_recorder.py` lines 1-14):
```python
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

log = logging.getLogger("agentos.approval")
log.setLevel(logging.INFO)
if not log.handlers and not logging.getLogger().handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(_h)
    log.propagate = False
```

**DB method patch pattern** (from `agentos/eval_recorder.py` `patch_classes_for_recording`, lines 141-200):
The approval recorder wraps DB-level methods (`create_approval`, `update_approval`,
`update_approval_run_status`) on the shared `db` instance — not on a class — because
approvals are written by Agno internals calling `db.<method>()` directly. This is
instance-level patching (not class-level like `eval_recorder`) because there is only
one shared `db` object that all routes and agents share.

Pattern to copy:
```python
class ApprovalRecorder:
    """Patches the shared db instance's approval methods with OBS-01 logging.
    Called once from app.py after db is constructed. Idempotent."""

    def __init__(self, db: Any) -> None:
        self.db = db

    def patch(self) -> None:
        if getattr(self.db, "_approval_recorder_patched", False):
            return
        self._wrap_method("create_approval", self._wrap_create)
        self._wrap_method("update_approval", self._wrap_update)
        self._wrap_method("update_approval_run_status", self._wrap_run_status)
        self.db._approval_recorder_patched = True

    def _wrap_method(self, name: str, wrapper_factory) -> None:
        original = getattr(self.db, name, None)
        if original is not None:
            setattr(self.db, name, wrapper_factory(original))
```

**Log-and-swallow pattern for OBS failures** (from `agentos/eval_recorder.py` lines 69-77):
```python
status = "ok"
error_type: Optional[str] = None
error_msg: Optional[str] = None
try:
    self.db.create_eval_run(record)
except Exception as exc:
    status = "error"
    error_type = exc.__class__.__name__
    error_msg = str(exc)[:200]
    # swallow — OBS-01 captures the failure; agent reply still returns.
```
**For approvals:** OBS write failures swallow; `update_approval` failures (the row-state bridge) must NOT swallow — they must surface a Telegram error (see D-16).

**`_emit` pattern** (from `agentos/instrumented_knowledge.py` lines 129-150):
```python
def _emit(self, *, ...) -> None:
    record: dict = {
        "path": "approval",
        "op": "create|resolve|run_status",   # per call site
        "agent_id": agent_id,
        "run_id": run_id,
        "approval_id": approval_id,
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "status_from": status_from,
        "status_to": status_to,
        "run_status": run_status,
        "resolved_by": resolved_by,
        "latency_ms": latency_ms,
        "status": status,        # "ok" | "error"
    }
    if status == "error":
        record["error_type"] = error_type
        record["error_msg"] = error_msg
        log.error("OBS-01 approval write failed: %s", json.dumps(record, default=str))
    else:
        log.info("OBS-01 approval write: %s", json.dumps(record, default=str))
```
Field set from CONTEXT.md D-11: `ts`, `level`, `path='approval'`, `op`, `agent_id`, `user_id`,
`run_id`, `approval_id`, `tool_call_id`, `tool_name`, `status_from`, `status_to`, `run_status`,
`latency_ms`, `status='ok|error'`. Truncate `tool_args` to a short safe summary — do not log raw args.

**Function signature for `patch_db_for_approval_recording`** (mirrors `patch_classes_for_recording` in `eval_recorder.py` line 120):
```python
def patch_db_for_approval_recording(db: Any) -> None:
    """Instance-level patch of db.create_approval / update_approval /
    update_approval_run_status so OBS-01 log lines are emitted for every
    approval lifecycle event. Idempotent."""
    recorder = ApprovalRecorder(db=db)
    recorder.patch()
```

---

### `channels/telegram_adapter.py` (MODIFY — add `_resolve_approval_row` helper)

**Analog:** self — extend `handle_callback` (lines ~340-420 of the existing file)

**Where to insert:** After the `_RESOLVED_RUNS.add(run_id)` guard and before the `confirmed = ...` line. The helper is called once before the existing `/continue` POST.

**Bridge helper pattern** (new function, modelled after the existing `send_approval_buttons` helper):
```python
async def _resolve_approval_row(
    client: httpx.AsyncClient,
    run_id: str,
    tool_call_id: str,
    confirmed: bool,
    tg_user_id: int,
) -> None:
    """Look up the native AgentOS approval row and resolve it.

    D-06: look up by run_id + approval_type='required' + status='pending',
    match tool_call_id; then POST /approvals/{approval_id}/resolve.
    Failures are logged but do NOT suppress the /continue call (D-16).
    """
    status_value = "approved" if confirmed else "rejected"
    resolved_by = f"telegram:{tg_user_id}"
    try:
        list_resp = await client.get(
            f"{AGENTOS_BASE_URL}/approvals",
            params={"run_id": run_id, "status": "pending", "approval_type": "required"},
        )
        if list_resp.status_code != 200:
            log.warning("_resolve_approval_row: GET /approvals returned %s", list_resp.status_code)
            return
        data = list_resp.json()
        rows = data.get("data") or []
        # Match by tool_call_id when multiple requirements exist (D-06)
        approval_id = None
        for row in rows:
            row_tool_call_id = (row.get("tool_execution") or {}).get("tool_call_id")
            if row_tool_call_id == tool_call_id or not row_tool_call_id:
                approval_id = row.get("id")
                break
        if not approval_id:
            log.warning("_resolve_approval_row: no pending approval row for run %s / tool_call_id %s", run_id, tool_call_id)
            return
        resolve_resp = await client.post(
            f"{AGENTOS_BASE_URL}/approvals/{approval_id}/resolve",
            json={"status": status_value, "resolved_by": resolved_by},
        )
        if resolve_resp.status_code not in (200, 201):
            log.warning("_resolve_approval_row: resolve returned %s: %s", resolve_resp.status_code, resolve_resp.text[:200])
    except httpx.RequestError as exc:
        log.error("_resolve_approval_row network error: %s", exc)
    except Exception as exc:
        log.error("_resolve_approval_row unexpected error: %s", exc)
```

**Integration point in `handle_callback`** — insert call AFTER `_RESOLVED_RUNS.add(run_id)`:
```python
# D-05/D-06: resolve native approval row before continuing the run
await _resolve_approval_row(client, run_id, tool_call_id, confirmed, tg_user_id)
# then existing /continue POST follows unchanged
```

**Existing guard to preserve** (from `handle_callback`, existing lines — do not remove):
```python
if run_id in _RESOLVED_RUNS:
    log.debug("Ignoring duplicate callback for already-resolved run %s", run_id)
    return
_RESOLVED_RUNS.add(run_id)
```
The `_RESOLVED_RUNS` guard must remain first and unchanged. `_resolve_approval_row` is called after the guard fires, not before.

---

### `agentos/app.py` (MODIFY — wire approval recorder on startup)

**Analog:** self — copy the eval recorder wiring pattern (existing lines ~47-52):
```python
# Existing eval recorder wiring (reference):
from agentos.eval_recorder import patch_classes_for_recording
patch_classes_for_recording(db=db)
```

**New wiring to add** (immediately after the eval recorder block):
```python
# OBS-01 / APPR-01: instrument DB approval methods with structured logging
from agentos.approval_recorder import patch_db_for_approval_recording
patch_db_for_approval_recording(db=db)
```

**Placement rule:** Must come AFTER `db` is constructed (Postgres or Sqlite fallback block) and AFTER `patch_classes_for_recording(db=db)`, so both eval and approval instrumentation are in place before AgentOS routes start serving requests.

---

### `tests/test_approval_recorder.py` (NEW)

**Primary analog:** `tests/test_telegram_adapter.py` — class-per-scenario, `AsyncMock`/`MagicMock`, `setUp` clears module state
**Secondary analog:** `tests/test_agentos.py` — DB method patching tests (if applicable)

**Test file structure** (copy from `tests/test_telegram_adapter.py` lines 1-20):
```python
"""Behavioral tests for agentos/approval_recorder.py.

Covers:
  OBS-01  — create_approval / update_approval / update_approval_run_status emit structured log lines
  FAULT   — DB method exceptions are logged and swallowed; original exception still propagates
  IDEM    — patch_db_for_approval_recording is idempotent (second call is a no-op)
"""
from __future__ import annotations

import json
import logging
import unittest
from unittest.mock import MagicMock, patch
```

**Module re-import helper pattern** (from `tests/test_telegram_adapter.py` lines 15-27):
```python
def _import_recorder():
    import importlib, sys
    for key in list(sys.modules):
        if "approval_recorder" in key:
            del sys.modules[key]
    import agentos.approval_recorder as mod
    return mod
```

**DB mock pattern for instrumentation tests:**
```python
class TestApprovalRecorderLogging(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        # Simulate a real approval dict returned by create_approval
        self.db.create_approval.return_value = {
            "id": "appr-1",
            "run_id": "run-1",
            "status": "pending",
            "tool_call_id": "tc-1",
            "tool_name": "ingest_to_vault",
        }

    def test_create_approval_emits_obs_log_on_success(self):
        from agentos.approval_recorder import patch_db_for_approval_recording
        patch_db_for_approval_recording(self.db)
        with self.assertLogs("agentos.approval", level="INFO") as cm:
            self.db.create_approval({"id": "appr-1", "run_id": "run-1", "status": "pending"})
        self.assertTrue(any("OBS-01" in line and "create" in line for line in cm.output))

    def test_create_approval_db_error_is_logged_and_swallowed(self):
        # OBS write failure: the wrapped call raises; original exception propagates
        # but the log line is still emitted before re-raise
        ...

    def test_patch_is_idempotent(self):
        from agentos.approval_recorder import patch_db_for_approval_recording
        patch_db_for_approval_recording(self.db)
        patch_db_for_approval_recording(self.db)  # second call must be a no-op
        # create_approval should still only be wrapped once
        self.db.create_approval({"id": "x"})
        self.assertEqual(self.db.create_approval.call_count, 0)  # original replaced, not double-wrapped
```

**Fault injection pattern** (from `tests/test_telegram_adapter.py` `TestApproveDoubleTap.test_non_409_error_releases_resolved_marker_for_retry`):
```python
def test_update_approval_db_failure_logs_error(self):
    from agentos.approval_recorder import patch_db_for_approval_recording
    self.db.update_approval.side_effect = RuntimeError("pg gone")
    patch_db_for_approval_recording(self.db)
    with self.assertLogs("agentos.approval", level="ERROR") as cm:
        with self.assertRaises(RuntimeError):
            self.db.update_approval("appr-1", status="approved")
    self.assertTrue(any("error" in line.lower() for line in cm.output))
```

---

### `tests/test_telegram_adapter.py` (MODIFY — add `TestApprovalBridge` class)

**Analog:** self — append a new class following the established `class TestApproveDoubleTap` pattern

**New class to add at the bottom** (before `if __name__ == "__main__"`):
```python
class TestApprovalBridge(unittest.TestCase):
    """D-05/D-06/D-08 — _resolve_approval_row is called before /continue;
    approve resolves status='approved'; deny resolves status='rejected';
    _RESOLVED_RUNS guard still fires first; network errors in bridge do not
    suppress the /continue call (D-16 log-and-continue semantics)."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _import_adapter_with_env()

    def setUp(self):
        self.mod._RESOLVED_RUNS.clear()
        self.mod._PAUSED_TOOLS.clear()

    def _make_query(self, run_id: str, action: str = "approve") -> dict:
        return {
            "id": "cq-bridge",
            "message": {"chat": {"id": 111}},
            "from": {"id": 999},
            "data": f"{action}:{run_id}:ingest:tc-abc-123",
        }

    def _run(self, run_id: str, action: str, client_mock) -> None:
        import asyncio
        asyncio.run(self.mod.handle_callback(client_mock, self._make_query(run_id, action)))

    def test_approve_calls_resolve_with_approved_status(self):
        """POST /approvals/{id}/resolve receives status='approved' for approve tap."""
        ...

    def test_deny_calls_resolve_with_rejected_status(self):
        """POST /approvals/{id}/resolve receives status='rejected' for deny tap."""
        ...

    def test_bridge_network_error_does_not_suppress_continue(self):
        """If GET /approvals throws a network error, /continue is still called."""
        ...

    def test_resolve_row_called_before_continue(self):
        """call order: answerCallbackQuery, GET /approvals, POST /resolve, POST /continue."""
        ...
```

**Mock pattern for HTTP sequence** (from `TestApproveDoubleTap.test_409_already_continued_is_swallowed`):
```python
async def _post(url, *args, **kwargs):
    if "resolve" in url:
        return MagicMock(status_code=200, json=lambda: {"id": "appr-1", "status": "approved"})
    if "continue" in url:
        return MagicMock(status_code=200, json=lambda: {"content": "done"}, text="")
    return MagicMock(status_code=200, json=lambda: {})

async def _get(url, *args, **kwargs):
    if "approvals" in url:
        return MagicMock(status_code=200, json=lambda: {
            "data": [{"id": "appr-1", "tool_execution": {"tool_call_id": "tc-abc-123"}}]
        })
    return MagicMock(status_code=200, json=lambda: {})

client = AsyncMock()
client.post = AsyncMock(side_effect=_post)
client.get = AsyncMock(side_effect=_get)
```

---

## Shared Patterns

### Logger boilerplate (OBS-01)
**Source:** `agentos/instrumented_memory.py` lines 13-22 / `agentos/eval_recorder.py` lines 13-19
**Apply to:** `agentos/approval_recorder.py`
```python
log = logging.getLogger("agentos.approval")
log.setLevel(logging.INFO)
if not log.handlers and not logging.getLogger().handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(_h)
    log.propagate = False
```

### Log-and-swallow for OBS write failures
**Source:** `agentos/eval_recorder.py` lines 69-76
**Apply to:** `agentos/approval_recorder.py` — the OBS `_emit()` call itself
**Exception:** the `update_approval` call (the row-state bridge) MUST NOT swallow — D-16 requires surfacing a Telegram error if that fails.

### `_emit` JSON serialization
**Source:** `agentos/instrumented_knowledge.py` lines 129-150
**Apply to:** `agentos/approval_recorder.py`
```python
log.info("OBS-01 approval write: %s", json.dumps(record, default=str))
log.error("OBS-01 approval write failed: %s", json.dumps(record, default=str))
```

### Idempotent patch guard
**Source:** `agentos/eval_recorder.py` lines 143-145
**Apply to:** `agentos/approval_recorder.py`
```python
if getattr(cls, "_eval_recorder_patched", False):
    continue
# approval equivalent:
if getattr(self.db, "_approval_recorder_patched", False):
    return
```

### `asyncio.to_thread` for sync DB calls from async context
**Source:** `agentos/eval_recorder.py` lines 56-60
**Apply to:** `channels/telegram_adapter.py::_resolve_approval_row` — the function is already `async`; the `httpx.AsyncClient` calls are async-native so this is not needed for the bridge itself. Apply only if a sync DB call is made directly (which the bridge avoids by going through the HTTP API).

### Test module re-import helper
**Source:** `tests/test_telegram_adapter.py` lines 15-27 (`_import_adapter_with_env`)
**Apply to:** `tests/test_approval_recorder.py` — use a simpler `_import_recorder()` without env mocking (no module-level env requirements in the recorder).

### Test `setUp` state clearing
**Source:** `tests/test_telegram_adapter.py` `TestApproveDoubleTap.setUp` (lines ~190-193)
**Apply to:** `tests/test_telegram_adapter.py::TestApprovalBridge.setUp` and `tests/test_approval_recorder.py` test classes that patch `db` state.
```python
def setUp(self):
    self.mod._RESOLVED_RUNS.clear()
    self.mod._PAUSED_TOOLS.clear()
```

---

## No Analog Found

All 5 files have analogs. No files require falling back to RESEARCH.md patterns exclusively.

---

## Key Agno Source Facts (for planner)

- `db.create_approval(approval_data: dict) -> dict` — inserts into `ai.agno_approvals`; called by Agno internals when a run pauses.
- `db.update_approval(approval_id, expected_status='pending', **kwargs) -> dict | None` — returns `None` if row not found or already resolved (409-equivalent logic).
- `db.update_approval_run_status(run_id, run_status: RunStatus) -> int` — bulk update by run_id.
- `GET /approvals?run_id=<id>&status=pending&approval_type=required` — returns `PaginatedResponse` with `data` list; each row has `id`, `tool_execution.tool_call_id`, `status`, `run_status`.
- `POST /approvals/{approval_id}/resolve` — body: `{"status": "approved"|"rejected", "resolved_by": "<str>", "resolution_data": {...}}`. Returns 409 if already resolved.
- Router source: `.venv/lib/python3.13/site-packages/agno/os/routers/approvals/router.py` lines 164-213.
- Auth gate: `require_approval_resolved` in `agno/os/auth.py` blocks `/continue` if `approval_type=required` row is still `pending` AND auth is enabled. Resolving the row BEFORE calling `/continue` prevents this.

## Metadata

**Analog search scope:** `agentos/`, `channels/`, `tests/`, `.venv/lib/python3.13/site-packages/agno/`
**Files scanned:** 8 source files + 2 Agno vendor files
**Pattern extraction date:** 2026-05-27
