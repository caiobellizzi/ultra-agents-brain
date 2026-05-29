---
phase: 11-memory-surface-activation
plan: 01
status: deployed + partially verified (OBS-01 emission has a known gap)
date: 2026-05-22
deployed_sha: 4498867
---

# Plan 11-01 — Memory surface activation

## What shipped

| Task | Commit | Change |
|------|--------|--------|
| 1 | `feat(11-01): pin BaseDb.id + add explicit Agent/Team ids` | `PostgresDb(id="ultra-brain-main", …)` + explicit `id="<slug>"` on every Agent/Team factory. |
| 2 | `feat(11-01): opt curator + ingest out of auto memory extraction` | `update_memory_on_run=False` on curator + ingest (D-06). |
| 3 | `feat(11-01): wire InstrumentedMemoryManager for OBS-01 logging` | New `agentos/instrumented_memory.py` (subclass of `MemoryManager`) emits `OBS-01 memory write: {path, agent_id, team_id, user_id, db_id, latency_ms, status, extracted_count, …}` around every `create_user_memories` / `acreate_user_memories` call. `app.py` switched to `InstrumentedMemoryManager`. |
| 4 | `test(11-01): MEM-03 unit tests for per-factory update_memory_on_run` | `tests/unit/test_agent_factories.py` — 6 tests, all green locally. `pytest.ini` registers the `live` marker. |
| 5 | `test(11-01): MEM-01/MEM-02 live integration probes against VPS` | `tests/integration/test_memory_surface.py` — synthetic `POST /agents/chat/runs` + 5s memory-appearance SLA, plus `/config.os_database` assertion. Marked `pytest.mark.live`. |
| follow-up | `fix(11-01): force agentos.memory logger to INFO so OBS-01 lines emit` | Force `agentos.memory` logger to INFO + attach a StreamHandler when none exist on logger or root, so OBS-01 INFO lines don't get dropped under uvicorn/systemd's WARNING default. |

## Local verification

- `python -m py_compile agentos/app.py agentos/agents/*.py agentos/instrumented_memory.py` — OK.
- `python -c "from agentos.instrumented_memory import InstrumentedMemoryManager; from agno.memory.manager import MemoryManager; assert issubclass(InstrumentedMemoryManager, MemoryManager)"` — OK.
- `pytest tests/unit/test_agent_factories.py -v` — **6 passed in 0.72s**.

## VPS deploy + verification (2026-05-22 ~00:50 UTC)

Deploy method: rsync `agentos/` → `/opt/ultra-agents-brain/agentos/` on `31.97.130.253` + `systemctl restart uab-brain.service`.

### ✅ MEM-02 satisfied — `os_database` pin live

```
$ curl -sS http://31.97.130.253:7000/config | python3 -c "import sys,json;
  c=json.load(sys.stdin); print(c['os_database'], c['databases'])"
ultra-brain-main ['ultra-brain-main']
```

Every agent in `/config.agents[]` carries its slug `id` (chat, curator, ingest, query, research) and the supervisor team's `id == "supervisor"`. The `memory.dbs[0].db_id == "ultra-brain-main"`. (DIAG-BL-01 precondition met.)

### ✅ MEM-03 satisfied — per-factory `update_memory_on_run` enforced

Unit-test suite (6 tests) green locally; deployed code mirrors the test fixtures. Direct import on the VPS confirms `type(memory).__name__ == "InstrumentedMemoryManager"` and `memory.db.id == "ultra-brain-main"`.

### ⚠️ MEM-01 partially satisfied — memory writes happen, SLA met from localhost

Synthetic POST from VPS localhost (matches `evidence/experiment-2026-05-22.md` shape):

```
POST http://127.0.0.1:7000/agents/chat/runs  (user_id=mem-test-1779497312)
→ HTTP 200, 16.8s
→ rows in /memories?user_id=… : 2 (visible 1s after POST returned)
```

The 16.8s POST latency is the chat agent's NIM inference time, not the memory write path. The memory write itself is sub-second after the agent run completes. **MEM-01 SLA (≤ 5s memory appearance) is met when measured from POST completion**, which matches the experiment baseline.

The `tests/integration/test_memory_surface.py` SLA test as written measures elapsed-from-POST-start, which on this VPS includes the 16s agent latency — that's a test calibration issue, not a memory-path regression. Recommendation: either (a) raise `SLA_SECONDS` to 30 in the test, or (b) document that the SLA is from-POST-completion and refactor the test accordingly. Tracking in `Open items` below.

### ⚠️ OBS-01 — emission gap on the agentic-memory-tool path

Synthetic POSTs that exercise the `chat` agent **do not** emit `OBS-01 memory write` log lines in `journalctl -u uab-brain.service`, even though memory rows are correctly written.

Root cause hypothesis: the `chat` factory sets both `enable_agentic_memory=True` (LLM can call the memory tool agentically) **and** `update_memory_on_run=True` (auto-extract at end of run). The current `chat` response — "Got it! I've saved that you love the color teal…" — is the LLM acknowledging an agentic *tool* invocation, which goes through `MemoryManager.update_memory_task → run_memory_task` (Agno `_default_tools.py:51`). `update_memory_on_run` then sees that memory rows already exist for the message and short-circuits the `create_user_memories` call — bypassing the OBS-01 hook.

Plan 11-01 only instruments `create_user_memories` / `acreate_user_memories`. To close OBS-01 on the agentic-memory path, instrumentation must also wrap `update_memory_task` and `aupdate_memory_task` (and likely `run_memory_task` for consistency). See `Open items`.

## Open items (follow-up work, not 11-01 scope)

- **OBS-01 coverage gap on agentic-memory-tool path.** Extend `InstrumentedMemoryManager` to also override `update_memory_task` / `aupdate_memory_task` (and possibly `run_memory_task` / `arun_memory_task`). Should be a small additive change with new unit-test coverage. Recommended as plan 11-03 or appended to plan 11-02 since both touch the memory write path.
- **Integration test SLA calibration.** `tests/integration/test_memory_surface.py::test_mem_01_chat_run_persists_memory_within_5s` measures wall-clock from POST start; with NIM-routed chat latency averaging 10-20s, the 5s budget is incorrect. Either raise to 30s or measure from POST completion.
- **Plan 11-02 readiness.** Supervisor + Telegram adapter wiring can proceed against the deployed `ultra-brain-main` pin. The agentic-memory instrumentation gap above does not block 11-02 itself.
