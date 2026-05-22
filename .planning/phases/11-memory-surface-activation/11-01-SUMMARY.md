---
phase: 11-memory-surface-activation
plan: 01
status: code-shipped (awaiting redeploy + live verification)
date: 2026-05-22
---

# Plan 11-01 — Memory surface activation (local code complete)

## What shipped

| Task | Commit | Change |
|------|--------|--------|
| 1 | `feat(11-01): pin BaseDb.id + add explicit Agent/Team ids` | `PostgresDb(id="ultra-brain-main", …)` + explicit `id="<slug>"` on every Agent/Team factory. |
| 2 | `feat(11-01): opt curator + ingest out of auto memory extraction` | `update_memory_on_run=False` on curator + ingest (D-06). |
| 3 | `feat(11-01): wire InstrumentedMemoryManager for OBS-01 logging` | New `agentos/instrumented_memory.py` (subclass of `MemoryManager`) emits `OBS-01 memory write: {path, agent_id, team_id, user_id, db_id, latency_ms, status, extracted_count, …}` around every `create_user_memories` / `acreate_user_memories` call. `app.py` switched to `InstrumentedMemoryManager`. |
| 4 | `test(11-01): MEM-03 unit tests for per-factory update_memory_on_run` | `tests/unit/test_agent_factories.py` — 6 tests, all green locally (0.72s). `pytest.ini` registers the `live` marker. |
| 5 | `test(11-01): MEM-01/MEM-02 live integration probes against VPS` | `tests/integration/test_memory_surface.py` — synthetic `POST /agents/chat/runs` + 5s memory-appearance SLA, plus `/config.os_database` assertion. Marked `pytest.mark.live`; runs only with `pytest -m live`. |

## Local verification

- `python -m py_compile agentos/app.py agentos/agents/*.py agentos/instrumented_memory.py` — OK.
- `python -c "from agentos.instrumented_memory import InstrumentedMemoryManager; from agno.memory.manager import MemoryManager; assert issubclass(InstrumentedMemoryManager, MemoryManager)"` — OK.
- `pytest tests/unit/test_agent_factories.py -v` — **6 passed in 0.72s**.
- `pytest tests/integration/test_memory_surface.py --collect-only` — 2 tests collected (deferred to post-deploy).

## Pending — operator action required

1. **Redeploy `uab-brain.service` on the VPS** so the running process picks up:
   - the pinned `PostgresDb.id`
   - the `InstrumentedMemoryManager` swap
   - the per-factory `update_memory_on_run` flip
2. **Run** `pytest -m live tests/integration/test_memory_surface.py` from a host with reach to `http://31.97.130.253:7000` (or set `UAB_AGENTOS_URL`).
3. **Capture** ≥1 OBS-01 log line from `journalctl -u uab-brain.service | grep "OBS-01 memory write"` and paste into this SUMMARY under "Post-deploy evidence".
4. **Confirm** `curl -sS http://31.97.130.253:7000/config | jq .os_database` returns `"ultra-brain-main"`.

## Post-deploy evidence

_(to be filled in by the operator)_

- Deployed git SHA:
- `/config.os_database`:
- MEM-01 elapsed-to-row:
- OBS-01 sample line:
- Surprises / flakes:

## Open items

- Plan 11-02 (supervisor + Telegram adapter wiring) blocked on the redeploy above so the real-Telegram MEM-01 verification path is clean.
