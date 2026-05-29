---
phase: 11-memory-surface-activation
plan: 03
status: complete
shipped: 2026-05-23
requirements: [OBS-01 (memory path — closeout)]
---

# Plan 11-03 — OBS-01 closeout SUMMARY

## What shipped

Extended `InstrumentedMemoryManager` with overrides for `update_memory_task` and `aupdate_memory_task`. These are the Agno entry points used when `enable_agentic_memory=True` (chat agent + supervisor team), which bypass the `create_user_memories` hook installed in 11-01. The overrides reuse the existing `_safe_count` / `_emit` helpers, so the OBS-01 log schema is identical across both paths.

`agent_id` / `team_id` are emitted as `null` on this path because Agno's `update_memory_task` signature only carries `task` and `user_id`. The operationally meaningful tag (`user_id`) is preserved, which is what OBS-01 requires to prove the agentic-tool path executed.

## Files touched

- `agentos/instrumented_memory.py` — 2 new methods (58 lines)
- `tests/unit/test_instrumented_memory.py` — new, 4 tests (81 lines)

## Commits

1. `feat(11-03): instrument update_memory_task for OBS-01 agentic-memory path`
2. `test(11-03): unit tests for update_memory_task OBS-01 emission`
3. `docs(11-03): OBS-01 closeout smoke evidence + SUMMARY` (this commit)

## Verification

- ✅ 4 new unit tests pass; 10/10 unit suite green (no regression on 11-01 factory tests).
- ✅ Pre-deploy journal grep on VPS returned zero OBS-01 lines for the agentic-memory path — gap confirmed.
- ✅ Post-deploy real-traffic smoke (operator Telegram message) produced the expected line within 10 s:
  `OBS-01 memory write: {"path":"memory","user_id":"7113965359","db_id":"ultra-brain-main","status":"ok","extracted_count":3,"latency_ms":14438,...}`
- ✅ DB row count for the operator user confirmed 9 total memories post-smoke, with `extracted_count=3` for this write.
- ✅ Evidence captured at `evidence/11-03-obs01-closeout.md`.

## OBS-01 closeout table

| Path | Hook | Status |
|------|------|--------|
| Auto-extraction (`create_user_memories`) | `InstrumentedMemoryManager.create_user_memories` / `acreate_user_memories` (11-01) | ✅ Satisfied |
| Agentic memory tool (`update_memory_task`) | `InstrumentedMemoryManager.update_memory_task` / `aupdate_memory_task` (11-03) | ✅ Satisfied |
| Explicit `db.upsert_user_memory()` (curl probes, UI button) | Out of scope — separate observability path | Deferred |

OBS-01 for the memory path is **fully satisfied**. Knowledge / Eval / Approvals paths remain scoped to phases 12 / 13 / 14.

## Open items / forward notes

- `agent_id` on the agentic-memory path requires upstream Agno changes (the tool would need to pass `agent_id` into `update_memory_task`). Tracked as a candidate Agno PR or a `MemoryTools` subclass in a later phase.
- Integration test SLA calibration (carried from 11-01) still pending; deferred to phase 15 polish.

## Rollback

Single-file revert of `agentos/instrumented_memory.py`. No DB migration. No config change.
