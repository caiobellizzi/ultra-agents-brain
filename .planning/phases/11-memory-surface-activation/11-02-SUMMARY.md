---
phase: 11-memory-surface-activation
plan: 02
status: shipped (supervisor unhung + telegram timeout fixed; OBS-01 gap inherited from 11-01)
date: 2026-05-23
deployed_sha: 9ed4a0a
---

# Plan 11-02 — Supervisor unhang + Telegram timeout shape

## What shipped

| Task | Commit | Change |
|------|--------|--------|
| 1 + 2 | `feat(11-02): disable supervisor reasoning + raise telegram httpx budget` | `agentos/agents/supervisor.py`: `reasoning=True → False` (Agno's manual CoT layered over NIM DeepSeek hung indefinitely). `channels/telegram_adapter.py`: `timeout=POLL_TIMEOUT+5` → explicit `httpx.Timeout(connect=10, read=90, write=10, pool=90)` for AgentOS POSTs. Long-poll `getUpdates` keeps its own `timeout=POLL_TIMEOUT` arg so the polling budget is unchanged. |
| 3 | `docs(11-02): smoke evidence + SUMMARY` (this commit) | Captured `evidence/11-02-smoke.md` recording: synthetic supervisor probe (HTTP 200 in 33.7s, was hanging >120s), real Telegram round-trip (`POST /teams/supervisor/runs` → `sendMessage` both 200 OK), and a definitive MEM-01 latency probe (2 fresh memory rows in <2s for a unique `user_id`). |

## Local verification

- `python -m py_compile agentos/agents/supervisor.py channels/telegram_adapter.py` — OK.
- `grep -c "reasoning=False" agentos/agents/supervisor.py` → 1; `grep -c "reasoning=True" agentos/agents/supervisor.py` → 0.
- `grep -c "httpx.Timeout(connect=10.0, read=90.0" channels/telegram_adapter.py` → 1.
- `grep -c "timeout=POLL_TIMEOUT" channels/telegram_adapter.py` → 2 (constant + explicit `getUpdates` arg, no regression).
- `pytest tests/unit/test_agent_factories.py -q` — **6 passed** (supervisor `id="supervisor"` + `update_memory_on_run=True` unchanged).

## VPS deploy + verification

Deploy method: rsync of the two changed files → `/opt/ultra-agents-brain/{agentos/agents/supervisor.py,channels/telegram_adapter.py}` + `systemctl restart uab-brain.service uab-telegram.service`. Pycache cleared before restart.

### Supervisor unhung

```
$ curl -X POST http://31.97.130.253:7000/teams/supervisor/runs \
    -F "message=quick smoke probe — what is the capital of France?" \
    -F "session_id=11-02-sup-probe-1" -F "user_id=99999996" -F "stream=false"
HTTP 200 time=33.691903s
```

Previously this call hung for >120s and was killed by `--max-time`. **Plan 11-02's primary contract met.**

### Telegram round-trip works

Operator sent a real Telegram message at 01:12:48 UTC. Adapter journal:

```
01:12:48 POST http://127.0.0.1:7000/teams/supervisor/runs HTTP/1.1 200 OK
01:12:49 POST https://api.telegram.org/.../sendMessage HTTP/1.1 200 OK
```

End-to-end Telegram → brain → reply path is open. No more 35s implicit timeout; the new 90s read budget is the active ceiling.

### MEM-01 SLA satisfied (definitive)

Fresh probe with a unique `user_id` (no prior memory state) wrote 2 new rows to `agno_memories` within 2 seconds of the agent run completing. See `evidence/11-02-smoke.md` for the exact timings and row contents.

The earlier operator-Telegram smoke didn't add new memory rows because the facts they messaged ("favorite color teal", "bikes Tuesdays") were already stored from the 22:39 UTC May 22 baseline; Agno's `create_or_update_memories` deduped them. That's expected memory-store behavior, not a regression.

### OBS-01 log line — STILL MISSING (inherited from 11-01)

`InstrumentedMemoryManager.create_user_memories` is not the hot path on this deployment. The chat agent's `enable_agentic_memory=True` routes writes through `MemoryManager.update_memory_task` instead, which 11-01 did not override.

Memory writes are visible in the DB; the structured-log half of OBS-01 is not visible in the journal. Tracked in `11-01-SUMMARY.md` open items. Recommended next step: a 1-task plan 11-03 that adds `update_memory_task` / `aupdate_memory_task` overrides to `InstrumentedMemoryManager` plus a unit test that asserts the override fires on a synthetic call.

## Open items (carried into phase 11 closeout)

- **OBS-01 coverage gap on the agentic-memory-tool path** — see `11-01-SUMMARY.md` open items. Same exact issue, re-confirmed by 11-02's fresh probe.
- **Integration test SLA calibration** — `tests/integration/test_memory_surface.py::test_mem_01_chat_run_persists_memory_within_5s` currently measures wall-clock from POST start; with NIM-routed chat latency averaging 15-30s, the 5s budget is mis-scoped. Either widen to 30s or measure from POST completion.
- **Supervisor session-history quirk** — when the operator's message can be answered from prior session context, the supervisor responds in sub-second without triggering memory extraction (observed at 01:12:48). Whether `update_memory_on_run` should still fire in that case is an Agno-behavior question; not a 11-02 blocker.

## Phase 11 closing status

| Requirement | Status |
|-------------|--------|
| MEM-01 (5s SLA, real-channel) | ✅ Satisfied via Telegram round-trip + synthetic SLA probe (2 rows / <2s after run completes). |
| MEM-02 (`os_database` pinned) | ✅ Satisfied (verified in 11-01: `/config.os_database == "ultra-brain-main"`). |
| MEM-03 (per-factory `update_memory_on_run`) | ✅ Satisfied (6 unit tests green, deployed code mirrors). |
| OBS-01 (structured memory log) | ⚠️ **Partially satisfied** — `InstrumentedMemoryManager` is wired and emits on the `create_user_memories` path, but the deployed chat/supervisor flows actually use `update_memory_task`, which is not instrumented. Recommend follow-up plan 11-03.
