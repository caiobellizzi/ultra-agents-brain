---
phase: 14
slug: approvals-surface-activation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-27
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` / `pyproject.toml` |
| **Quick run command** | `pytest tests/test_approval_recorder.py tests/test_telegram_adapter.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_approval_recorder.py tests/test_telegram_adapter.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | APPR-01 | — | `create_approval` DB method wrapped and OBS log emitted | unit | `pytest tests/test_approval_recorder.py::test_create_approval_logs_ok -x` | ❌ Wave 0 | ⬜ pending |
| 14-01-02 | 01 | 1 | APPR-01 | — | OBS log emitted on approval creation with required fields | unit | `pytest tests/test_approval_recorder.py::test_obs_log_on_create -x` | ❌ Wave 0 | ⬜ pending |
| 14-01-03 | 01 | 1 | APPR-03 | — | `tool_name` and `tool_args` visible in approval row | unit | `pytest tests/test_approval_recorder.py::test_tool_name_in_approval_data -x` | ❌ Wave 0 | ⬜ pending |
| 14-01-04 | 01 | 1 | OBS-01 | — | `update_approval` emits resolve OBS log | unit | `pytest tests/test_approval_recorder.py::test_update_approval_logs_resolve -x` | ❌ Wave 0 | ⬜ pending |
| 14-01-05 | 01 | 1 | OBS-01 | — | `update_approval_run_status` emits run_status OBS log | unit | `pytest tests/test_approval_recorder.py::test_update_run_status_logs -x` | ❌ Wave 0 | ⬜ pending |
| 14-01-06 | 01 | 1 | OBS-01 | — | Logging failure is non-fatal (log and swallow, never blocks approval) | unit | `pytest tests/test_approval_recorder.py::test_log_failure_nonfatal -x` | ❌ Wave 0 | ⬜ pending |
| 14-01-07 | 01 | 1 | D-14 | — | SqliteDb fallback does not 503 on `GET /approvals` | unit | `pytest tests/test_approval_recorder.py::test_sqlite_fallback_no_503 -x` | ❌ Wave 0 | ⬜ pending |
| 14-02-01 | 02 | 2 | APPR-02 | Duplicate-tap double-resolve | Telegram Approve calls `/approvals/{id}/resolve` then `/runs/{run_id}/continue` | unit | `pytest tests/test_telegram_adapter.py::TestApprovalBridge::test_approve_resolves_then_continues -x` | ❌ Wave 0 | ⬜ pending |
| 14-02-02 | 02 | 2 | APPR-02 | Wrong row match | Telegram Deny resolves with status=rejected | unit | `pytest tests/test_telegram_adapter.py::TestApprovalBridge::test_deny_resolves_rejected -x` | ❌ Wave 0 | ⬜ pending |
| 14-02-03 | 02 | 2 | APPR-02 | Resolve-then-continue gap | Resolve failure sends Telegram error and releases `_RESOLVED_RUNS` guard | unit | `pytest tests/test_telegram_adapter.py::TestApprovalBridge::test_resolve_failure_releases_guard -x` | ❌ Wave 0 | ⬜ pending |
| 14-02-04 | 02 | 2 | APPR-02 | Duplicate-tap | 409 on resolve is idempotent success | unit | `pytest tests/test_telegram_adapter.py::TestApprovalBridge::test_resolve_409_is_ok -x` | ❌ Wave 0 | ⬜ pending |
| 14-03-01 | 03 | 3 | APPR-01 | — | `GET /approvals` returns pending row after smoke trigger | integration (VPS) | manual — `curl "http://localhost:7777/v1/approvals?run_id=<run_id>"` | n/a | ⬜ pending |
| 14-03-02 | 03 | 3 | APPR-02 | — | Telegram Approve → row flips to approved within 2 seconds | integration (VPS) | manual — `psql` check | n/a | ⬜ pending |
| 14-03-03 | 03 | 3 | APPR-02 | — | Telegram Deny → row flips to rejected within 2 seconds | integration (VPS) | manual — `psql` check | n/a | ⬜ pending |
| 14-03-04 | 03 | 3 | APPR-03 | — | `tool_name='ingest_to_vault'` and fixture path in `tool_args` visible in row | integration (VPS) | manual — `psql` / API check | n/a | ⬜ pending |
| 14-03-05 | 03 | 3 | OBS-01 | — | Structured log lines for creation, resolve, and run_status update appear in journald | integration (VPS) | manual — `journalctl` grep | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_approval_recorder.py` — unit tests for DB method wrapping and OBS log emission (7 tests for APPR-01, APPR-03, OBS-01, D-14)
- [ ] `tests/test_telegram_adapter.py` — extend with `TestApprovalBridge` class (4 tests for APPR-02 Telegram bridge)
- [ ] `agentos/approval_recorder.py` — new module with DB method wrapping and `_emit` helper

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pending row appears in `ai.agno_approvals` after smoke trigger | APPR-01 | Requires live Agno run on VPS with Telegram message | 1. SSH to VPS. 2. `/ingest /tmp/uab-approval-smoke.md` in Telegram. 3. `psql $POSTGRES_DSN -c "SELECT id, status, tool_name FROM ai.agno_approvals WHERE status='pending' ORDER BY created_at DESC LIMIT 1;"` |
| Telegram Approve flips row to approved | APPR-02 | Requires live Telegram callback and timing assertion | 1. Trigger pending row per APPR-01. 2. Tap Approve in Telegram. 3. Within 2s: `psql` check status='approved' and `run_status` not 'paused'. |
| Telegram Deny flips row to rejected | APPR-02 | Requires live Telegram callback | Same as Approve but tap Deny — expect status='rejected'. |
| AgentOS UI shows tool name and args | APPR-03 | Browser inspection | Open AgentOS UI approvals list while row is pending — verify `ingest_to_vault` and fixture path visible. |
| OBS log lines appear in journald | OBS-01 | Systemd service output | `journalctl -u agentos --since "1 minute ago" \| grep '"op": "approval'` — should show create, resolve, run_status events. |

---

## Security Notes

| Threat | STRIDE | Mitigation |
|--------|--------|------------|
| Duplicate Approve tap double-resolves | Tampering | `_RESOLVED_RUNS` guard + 409 idempotency on resolve |
| Wrong approval row matched (multiple pending) | Tampering | Match by `tool_call_id`, not just "latest pending" |
| Resolve succeeds but continue fails — tool skipped silently | Repudiation | OBS log `op='resolve'` + Telegram error + `_RESOLVED_RUNS.discard` for retry |
| OBS log args dump leaks sensitive data | Info Disclosure | `tool_args_summary` truncated ~100 chars; smoke inputs are non-sensitive |
| Telegram user ID spoofed in `resolved_by` | Spoofing | `tg_user_id` from `query["from"]["id"]` (Telegram-signed) — acceptable for phase 14 |
