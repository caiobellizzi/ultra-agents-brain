---
phase: 14
plan: 14-03
status: in_progress
created: 2026-05-27
---

# Phase 14 — Approvals Surface Activation: Live Verification

## Summary

| Requirement | Status |
|-------------|--------|
| APPR-01: Pending row creation on /ingest | [PENDING] |
| APPR-02 Approve: status='approved' within 2s | [PENDING] |
| APPR-02 Deny: status='rejected' within 2s | [PENDING] |
| APPR-03: Tool name + args visible in approval row | [PENDING] |
| OBS-01: Structured journal log lines for approval path | [PENDING] |

---

## APPR-01 — Pending Row Creation

**Trigger:** `/ingest /tmp/uab-approval-smoke.md` sent in Telegram

**GET /approvals?run_id=<run_id>&status=pending:**
```
[PENDING]
```

**psql query (ai.agno_approvals):**
```
[PENDING]
```

---

## APPR-02 — Approve Path

**Tap: Approve button for pending run**

**psql query after tap:**
```
[PENDING]
```

Expected: `status='approved'`, `resolved_by='telegram:<user_id>'`, `run_status != 'paused'`

---

## APPR-02 — Deny Path

**Trigger:** `/ingest /tmp/uab-denial-smoke.md` sent in Telegram, then Deny tapped

**psql query after tap:**
```
[PENDING]
```

Expected: `status='rejected'`

---

## APPR-03 — UI Visibility

**AgentOS Approvals tab (https://os.agno.com):**
```
[PENDING]
```

Expected: `tool_name='ingest_to_vault'`, fixture path visible in tool_args

---

## OBS-01 — Structured Approval Logs

**journalctl | grep "path.*approval":**
```
[PENDING]
```

Expected: JSON log lines with `path='approval'`, `op='create'`, `op='resolve'`, `op='run_status'`
