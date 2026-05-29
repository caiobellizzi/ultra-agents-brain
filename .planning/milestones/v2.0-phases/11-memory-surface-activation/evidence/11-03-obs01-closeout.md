# Plan 11-03 — OBS-01 closeout smoke evidence

**Date:** 2026-05-23
**Service:** uab-brain.service (VPS 31.97.130.253)
**Goal:** Confirm `OBS-01 memory write` log line fires on the agentic-memory-tool path after instrumenting `update_memory_task` / `aupdate_memory_task` in `InstrumentedMemoryManager`.

## Pre-deploy journal grep (gap confirmation)

```bash
ssh root@31.97.130.253 'journalctl -u uab-brain.service --since "10 min ago" | grep "OBS-01 memory write"'
# → NO_OBS01_LINES (gap confirmed)
```

The agentic-memory path produced zero OBS-01 lines, confirming the gap documented in `11-02-SUMMARY.md`.

## Deploy

```bash
rsync -avz agentos/instrumented_memory.py \
  root@31.97.130.253:/opt/ultra-agents-brain/agentos/instrumented_memory.py
ssh root@31.97.130.253 'find /opt/ultra-agents-brain/agentos -name __pycache__ -exec rm -rf {} +; \
  systemctl restart uab-brain.service'
# → service active
```

## Smoke trigger

Operator sent Telegram message to bot at ~03:34 UTC:

> `I really enjoy hiking on weekends`

## Post-deploy journal grep (pass criteria)

```
May 23 03:34:25 srv847330 uab-brain[2970763]: 2026-05-23 03:34:25,259 INFO agentos.memory
OBS-01 memory write: {
  "path": "memory",
  "agent_id": null,
  "team_id": null,
  "user_id": "7113965359",
  "db_id": "ultra-brain-main",
  "latency_ms": 14438,
  "status": "ok",
  "extracted_count": 3
}
```

All required fields present:

| Field | Value | Pass |
|-------|-------|------|
| `path` | `memory` | ✅ |
| `user_id` | `7113965359` (operator Telegram id) | ✅ |
| `db_id` | `ultra-brain-main` | ✅ |
| `status` | `ok` | ✅ |
| `extracted_count` | `3` (>=0) | ✅ |
| `latency_ms` | `14438` | ✅ |

`agent_id` / `team_id` are `null` — expected on the agentic-memory-tool path. See `11-03-PLAN.md` "Constraint discovered from Agno source" and "Open items".

## DB row confirmation

```bash
ssh root@31.97.130.253 'PGPASSWORD=... psql -h 127.0.0.1 -U uab -d agno_sessions \
  -t -c "SELECT COUNT(*) FROM ai.agno_memories WHERE user_id = '"'"'7113965359'"'"';"'
# → 9
```

Total memory rows for the operator after the smoke = 9. The OBS-01 line reports `extracted_count: 3` for this single write, meaning Agno extracted 3 facts from the "hiking on weekends" message into separate rows. Behavior matches expectations.

## Unit tests

10/10 unit tests green (6 from 11-01 factory tests + 4 new `test_instrumented_memory.py`):

```
tests/unit/test_agent_factories.py            6 passed
tests/unit/test_instrumented_memory.py        4 passed
```

## Conclusion

OBS-01 (memory path) fully satisfied. Both auto-extraction (via `create_user_memories`) and the agentic-memory-tool path (via `update_memory_task`) now emit structured log lines. Phase 11 carryover closed.
