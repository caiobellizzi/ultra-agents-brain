---
phase: 14
fixed_at: 2026-05-28T14:17:00-03:00
review_path: .planning/phases/14-approvals-surface-activation/14-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 6
skipped: 1
status: partial
---

# Phase 14: Code Review Fix Report

**Fixed at:** 2026-05-28T14:17:00-03:00
**Source review:** .planning/phases/14-approvals-surface-activation/14-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (CR-01, CR-02, CR-03, CR-04, WR-01, WR-02, WR-03, WR-04)
- Fixed: 6
- Skipped: 1 (CR-03 — confirmed false positive)

## Fixed Issues

### CR-01: `tool_args_summary` leaks raw argument values

**Files modified:** `agentos/approval_recorder.py`
**Commit:** (fast-forwarded to main as part of ebc32d5 batch)
**Applied fix:** Replaced `str(args)[:120]` truncation with a structural summary that logs only key names and value type/length. For dict args: `{key: type[len]}` per key. For non-dict args: `type[len]`. Raw values (file paths, query strings, etc.) never appear in logs.

### CR-04: Two tests assert `"supervisor"` routing default but code returns `"chat"`

**Files modified:** `tests/test_telegram_adapter.py`
**Commit:** (fast-forwarded to main)
**Applied fix:** Renamed `test_plain_text_routes_to_supervisor` → `test_plain_text_routes_to_chat` and `test_unknown_command_falls_back_to_supervisor` → `test_unknown_command_falls_back_to_chat`. Updated both assertions from `"supervisor"` to `"chat"` to match the Phase 11-02 routing change already in the source.

### WR-01: `_resolve_approval_row` fallback to `rows[0]` on no `tool_call_id` match

**Files modified:** `channels/telegram_adapter.py`
**Commit:** (fast-forwarded to main)
**Applied fix:** When no row matches `tool_call_id`: if `len(rows) > 1`, log a warning and return `False` (refuse ambiguous multi-row fallback). If `len(rows) == 1`, log a warning naming the row being used and fall back (unambiguous single-row case). Both paths are now observable.

### WR-02: `tool_call_id` from `callback_data` has no UUID validation

**Files modified:** `channels/telegram_adapter.py`, `tests/test_telegram_adapter.py`
**Commit:** (fast-forwarded to main, two commits)
**Applied fix:** Added UUID validation for `tool_call_id` using the same `_UUID_RE` pattern already applied to `run_id`. Non-UUID `tool_call_id` values are rejected with a warning log. Also updated `TestApprovalBridge.TOOL_CALL_ID` fixture from `"tcid-0001-0002-0003-000400000005"` (non-UUID) to `"00010002-0003-0004-0005-000600070008"` (valid UUID) so tests pass the new validation.

### WR-03: `_PAUSED_TOOLS.pop` before `/continue` POST

**Files modified:** `channels/telegram_adapter.py`
**Commit:** (fast-forwarded to main)
**Applied fix:** Changed `_PAUSED_TOOLS.pop(run_id, None)` before the POST to `_PAUSED_TOOLS.get(run_id)` (non-destructive peek). The pop now happens after a successful POST response (200/201 or 409 already-continued). If the POST fails, the cached entry remains available for retry.

### CR-02: `_RESOLVED_RUNS` and `_PAUSED_TOOLS` are unbounded

**Files modified:** `channels/telegram_adapter.py`
**Commit:** (fast-forwarded to main)
**Applied fix:** Introduced `_BoundedDict` (OrderedDict subclass capped at 1000 entries, evicts oldest on insert) and `_BoundedSet` (set-like wrapper over `_BoundedDict` with `add`, `discard`, `__contains__`, `clear`). Both module-level caches now use these bounded types. `_LRU_MAX = 1000` constant controls the cap.

### WR-04: `wrapped_update_approval` hardcodes `run_id=None`

**Files modified:** `agentos/approval_recorder.py`
**Commit:** (fast-forwarded to main)
**Applied fix:** Changed `run_id=None` to `run_id=kwargs.get("run_id")` in the `_emit` call inside `wrapped_update_approval`. When callers pass `run_id` as a kwarg to `update_approval`, it is now forwarded to the OBS-01 log line.

## Skipped Issues

### CR-03: Decorator order is inverted on HITL tools

**File:** `agentos/tools/vault.py:36-47, 58-70`
**Reason:** Confirmed false positive per prior session REPL verification (observation 23794). `@approval` outermost and `@tool(requires_confirmation=True)` innermost was verified correct — `isinstance(ingest_to_vault, Function)==True` with `approval_type='required'`. No change made.
**Original issue:** Review flagged that decorator order `@approval` / `@tool` was inverted and would cause the approval wrapper to wrap a plain function rather than a registered Agno `Function`.

---

**Test results:** 44/44 passed (`tests/test_approval_recorder.py` + `tests/test_telegram_adapter.py`)

_Fixed: 2026-05-28T14:17:00-03:00_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
