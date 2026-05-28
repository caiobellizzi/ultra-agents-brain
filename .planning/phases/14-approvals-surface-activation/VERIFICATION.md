---
phase: 14
plan: 14-03
status: verified
created: 2026-05-27
verified: 2026-05-28
---

# Phase 14 — Approvals Surface Activation: Live Verification

## Summary

| Requirement | Status | Evidence |
|-------------|--------|----------|
| APPR-01: Pending row creation on /ingest | PASS | DB row `b9710cb8`, API returns `status='pending'` then `'approved'` |
| APPR-02 Approve: status='approved', resolved_by=telegram:… | PASS | `status='approved'`, `resolved_by='telegram:7113965359'`, `run_status='COMPLETED'` |
| APPR-02 Deny: status='rejected', resolved_by=telegram:… | PASS | `status='rejected'`, `resolved_by='telegram:7113965359'`, `run_status='COMPLETED'` |
| APPR-03: tool_name + args visible in approval row | PASS | `tool_name='ingest_to_vault'`, `tool_args={"source": "/tmp/uab-approval-smoke.md"}` |
| OBS-01: Structured journal log lines for approval path | PASS | op=create, op=resolve (×2), op=run_status (×4) observed |

---

## APPR-01 — Pending Row Creation

**Trigger:** `/ingest /tmp/uab-approval-smoke.md` sent in Telegram  
**run_id:** `9cb61ea8-0dd2-4226-b765-d459eced47a4`

**GET /approvals?run_id=9cb61ea8… (captured after Approve tap, showing final state):**
```json
{
    "data": [
        {
            "id": "b9710cb8-5fc0-4c32-bd87-9e03b0023635",
            "run_id": "9cb61ea8-0dd2-4226-b765-d459eced47a4",
            "session_id": "telegram-7113965359",
            "status": "approved",
            "approval_type": "required",
            "pause_type": "confirmation",
            "tool_name": "ingest_to_vault",
            "tool_args": {"source": "/tmp/uab-approval-smoke.md"},
            "agent_id": "ingest",
            "resolved_by": "telegram:7113965359",
            "resolved_at": 1779976230,
            "created_at": 1779976174,
            "run_status": "COMPLETED"
        }
    ],
    "meta": {"total_count": 1}
}
```

**OBS-01 create log (13:49:34 — row written at pause time):**
```
op: "create", tool_name: "ingest_to_vault", status_to: "pending", run_id: "9cb61ea8-..."
```

Row was created with `status='pending'` before any button was tapped. ✓

---

## APPR-02 — Approve Path

**psql — row after Approve tap:**
```
id                                   | agent_id | tool_name       | status   | run_status | resolved_by
b9710cb8-5fc0-4c32-bd87-9e03b0023635 | ingest   | ingest_to_vault | approved | COMPLETED  | telegram:7113965359
```

**OBS-01 resolve log (13:50:30 — within 1s of tap):**
```json
{"op": "resolve", "approval_id": "b9710cb8-...", "status_from": "pending", "status_to": "approved", "resolved_by": "telegram:7113965359"}
```

`status='approved'`, `resolved_by='telegram:7113965359'`, run continued to COMPLETED. ✓

---

## APPR-02 — Deny Path

**Trigger:** `/ingest /tmp/uab-denial-smoke.md`, Deny tapped  
**run_id:** `68e68436-c9f2-40d0-8637-f10f9b843c70`

**psql — row after Deny tap:**
```
id                                   | agent_id | tool_name       | status   | run_status | resolved_by
e3d07a6d-f4f9-4ec1-b66c-e6eae3f06c80 | ingest   | ingest_to_vault | rejected | COMPLETED  | telegram:7113965359
```

**OBS-01 resolve log (13:53:47 — 2s after create at 13:53:45):**
```json
{"op": "resolve", "approval_id": "e3d07a6d-...", "status_from": "pending", "status_to": "rejected", "resolved_by": "telegram:7113965359"}
```

`status='rejected'`, resolved within 2s of row creation. ✓

---

## APPR-03 — Tool Name and Args Visibility

**Telegram UI (screenshot confirmed):**
```
Approval required for the following action(s):
Tool: ingest_to_vault
Args: source=/tmp/uab-approval-smoke.md
[Approve]  [Deny]
```

**psql tool_args:**
```
tool_name       | tool_args
ingest_to_vault | {"source": "/tmp/uab-approval-smoke.md"}
```

Tool name and args visible both in Telegram inline message and in the DB row. ✓

---

## OBS-01 — Structured Approval Logs

All 4 expected log line types observed in `journalctl -u uab-brain.service`:

**op=create (approve run, 13:49:34):**
```json
{"path": "approval", "op": "create", "tool_name": "ingest_to_vault", "run_id": "9cb61ea8-...", "agent_id": "ingest", "status_to": "pending", "tool_args_summary": "{'source': '/tmp/uab-approval-smoke.md'}", "latency_ms": 11, "status": "ok"}
```

**op=run_status PAUSED (approve run, 13:49:34):**
```json
{"path": "approval", "op": "run_status", "run_id": "9cb61ea8-...", "run_status": "PAUSED", "latency_ms": 7, "status": "ok"}
```

**op=resolve approved (13:50:30):**
```json
{"path": "approval", "op": "resolve", "approval_id": "b9710cb8-...", "status_from": "pending", "status_to": "approved", "resolved_by": "telegram:7113965359", "latency_ms": 15, "status": "ok"}
```

**op=create (deny run, 13:53:45):**
```json
{"path": "approval", "op": "create", "tool_name": "ingest_to_vault", "run_id": "68e68436-...", "agent_id": "ingest", "status_to": "pending", "tool_args_summary": "{'source': '/tmp/uab-denial-smoke.md'}", "latency_ms": 14, "status": "ok"}
```

**op=resolve rejected (13:53:47):**
```json
{"path": "approval", "op": "resolve", "approval_id": "e3d07a6d-...", "status_from": "pending", "status_to": "rejected", "resolved_by": "telegram:7113965359", "latency_ms": 26, "status": "ok"}
```

All `path='approval'` OBS-01 log lines confirmed: create, resolve (approved), resolve (rejected), run_status (PAUSED/COMPLETED). ✓

---

## Notes

- The `@approval` decorator was missing from `ingest_to_vault` and `research_topic` in `agentos/tools/vault.py`. Agno only writes the `ai.agno_approvals` row when the tool has `approval_type="required"` set on the Function object. `@tool(requires_confirmation=True)` alone pauses the run but does not set `approval_type`. Fix committed as `fix(14): add @approval decorator to HITL tools` (2cb0eb9).
- The smoke ingest returned `[Errno 13] Permission denied` because `/tmp/uab-approval-smoke.md` was root-owned. Fixed with `chown uabrain`. The approval surface itself was unaffected.
