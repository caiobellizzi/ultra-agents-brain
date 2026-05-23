---
phase: 12-evals-surface-activation
plan: 01
subsystem: evals
tags: [agno, eval, observability, obs-01, instrumented-recorder, async-to-thread]

requires:
  - phase: 11-memory-surface-activation
    provides: PostgresDb pinned to ultra-brain-main and instrumented_memory._emit pattern (mirrored here for OBS-01 schema parity)
provides:
  - InstrumentedEvalRecorder.wrap(agent) — post-run wrapper that writes one EvalRunRecord per Agent/Team .run / .arun call
  - OBS-01 eval log line (path="eval") emitted on every wrap call, success and error
  - Wiring of the recorder onto all 6 agents/team in agentos/app.py (chat, curator, ingest, query, research, supervisor_team)
affects: [evals, agentos.app, dashboard.evals, plan 12-02 suite hook, plan 12-03 verification]

tech-stack:
  added: []
  patterns:
    - Post-run wrapper pattern (decorator-style — RESEARCH F5, no Agno upgrade, no PostgresDb subclass)
    - asyncio.to_thread for sync DB writes inside async wrappers (RESEARCH F4)
    - OBS-01 emit helper mirrors agentos/instrumented_memory._emit for cross-path schema parity

key-files:
  created:
    - agentos/eval_recorder.py
    - tests/unit/test_eval_recorder.py
  modified:
    - agentos/app.py

key-decisions:
  - "D-01: post-run wrapper on Agent/Team arun/run, no Agno upgrade, no PostgresDb subclass"
  - "D-02: wrapper applied to all 6 agents/team (chat, query, research, supervisor, curator, ingest)"
  - "D-03: row payload — eval_input.user_message verbatim; eval_data carries output dump, latency_ms, model_id, model_provider, status"
  - "D-04: log-and-swallow on db.create_eval_run failure — agent reply still returns"
  - "D-05: read db.id from instance, never hardcode ultra-brain-main"
  - "D-06: per-run rows metadata-only at write time (eval_data.score = null)"
  - "D-07: eval_type=AGENT_AS_JUDGE (Pydantic enum rejects 'run' — RESEARCH F1)"
  - "D-08: async background scoring deferred — score=null left for future async worker to pick up"
  - "D-14: single OBS-01 hook point inside InstrumentedEvalRecorder for live runs"

patterns-established:
  - "Decorator-style instrumentation: wrap() mutates agent in place, stashes self on agent._eval_recorder for introspection"
  - "Failure isolation: external observability writes (DB row, log line) never propagate exceptions to user-facing agent calls"

requirements-completed: [EVAL-01, OBS-01]

duration: 12min
completed: 2026-05-23
---

# Phase 12-01: InstrumentedEvalRecorder Live-Run Write Path

**Every Agent/Team run now writes one EvalRunRecord (eval_type=AGENT_AS_JUDGE, score=null) and emits an OBS-01 structured log line — locked by five unit tests and applied to all six top-level objects in agentos/app.py.**

## What Shipped

| Artifact | Purpose |
|----------|---------|
| `agentos/eval_recorder.py` | `InstrumentedEvalRecorder` class — `wrap(agent)` replaces `agent.run` / `agent.arun` with closures that call the original, then build an `EvalRunRecord` via `_build_eval_record`, call `db.create_eval_run`, and emit one OBS-01 log line in all paths (success and DB error). Async path uses `asyncio.to_thread` so the sync DB write never blocks the event loop. |
| `agentos/app.py` | Six lines added: import the recorder, instantiate one bound to the shared `db`, loop through `(chat, curator, ingest, query, research, supervisor_team)` calling `_eval_recorder.wrap(_agent)` on each. No factory or `AgentOS(...)` kwargs changed. |
| `tests/unit/test_eval_recorder.py` | Five tests lock the contract: row-shape (sync), row-shape (async), DB-error swallow, OBS-01 D-15 schema completeness, app-level wiring of all 6 agents/team. |

## Test Status

```
5 passed in 6.32s
```

- `test_wrap_writes_row_on_success` — sync `agent.run("hi")` writes one row with `eval_type=AGENT_AS_JUDGE`, `run_id="r1"`, `agent_id="chat-test"`, `eval_data["score"] is None`, `eval_data["status"] == "ok"`, `eval_input == {"user_message": "hi"}`.
- `test_wrap_writes_row_on_success_async` — async `arun` mirrors sync behavior.
- `test_wrap_swallows_db_error` — `db.create_eval_run` raises `RuntimeError("boom")`; agent reply still returns; ERROR-level OBS-01 log emitted with `status="error"`, `error_type="RuntimeError"`, `error_msg.startswith("boom")`.
- `test_wrap_emits_obs01_schema` — every D-15 required field present in the parsed JSON payload: `path=eval`, `agent_id`, `db_id`, `row_id`, `latency_ms`, `status`, `eval_type=agent_as_judge`, `model_provider`, `model_id`, `score=null`, `case_id=null`.
- `test_app_wires_all_six_recorders` — importing `agentos.app` confirms each of the 6 objects has `_eval_recorder` set to an `InstrumentedEvalRecorder` whose `db` is the shared `agentos.app.db`.

## Threat Mitigations Verified

| Threat | Mitigation status |
|--------|-------------------|
| T-12-01: wrong eval_type rejected by Pydantic | LOCKED — `EvalType.AGENT_AS_JUDGE` constant referenced in source, asserted in tests |
| T-12-02: DB outage cascades to user-visible failure | LOCKED — `test_wrap_swallows_db_error` proves DB exceptions are swallowed |
| T-12-03: OBS-01 schema drift | LOCKED — `test_wrap_emits_obs01_schema` enumerates every D-15 field |
| T-12-04: new agent added without wrapper | LOCKED — `test_app_wires_all_six_recorders` enumerates all 6 objects |
| T-12-05: sync DB blocks async event loop | MITIGATED via `asyncio.to_thread(recorder._record, ...)` in the arun wrapper |
| T-12-06: hardcoded `db_id` | LOCKED — recorder reads `getattr(self.db, "id", None)`; the literal `"ultra-brain-main"` does NOT appear in `agentos/eval_recorder.py` |

## Self-Check: PASSED

- ✅ All 4 tasks executed and committed individually (RED tests → GREEN module → wire app → REFACTOR helper)
- ✅ 5/5 unit tests passing locally with `PYTHONPATH=. .venv/bin/pytest tests/unit/test_eval_recorder.py -q`
- ✅ `agentos/app.py` import smoke check confirms all 6 agents/team have `_eval_recorder` attribute
- ✅ `db.id == "ultra-brain-main"` reads correctly from the wrapper at runtime (uses the production SqliteDb fallback in test env)
- ✅ No production behavior beyond the wrapper: agent reply path unchanged on success and on DB failure
- ✅ No modifications to `.planning/STATE.md` or `.planning/ROADMAP.md` (orchestrator owns those writes)

## Handoff to Plan 12-02

Plan 12-02 wires the **suite** side — `evals/conftest.py` writes `EvalType.ACCURACY` rows from the 48-case suite via a `pytest_runtest_makereport` hook plus an opt-in `eval_recorder` fixture. The OBS-01 log schema established here is the contract that hook mirrors with `path="eval_suite"` and `case_id` populated.

## Handoff to Plan 12-03

Plan 12-03 verifies end-to-end on the deployed VPS:
- Operator redeploys `uab-brain.service` (systemd reload + restart) — the wrapper takes effect on next boot.
- Operator hits `POST /agents/chat/runs` once and confirms one row appears in `ai.agno_eval_runs` (`eval_type='agent_as_judge'`, `eval_data->>'score' IS NULL`) plus one `OBS-01 eval write: {...}` line in `journalctl -u uab-brain.service`.

## Commits in This Plan

| SHA | Subject |
|-----|---------|
| `7e1f144` | test(12-01): RED unit tests for InstrumentedEvalRecorder |
| `87f8463` | feat(12-01): InstrumentedEvalRecorder wraps Agent/Team for live eval rows |
| `00fa52d` | feat(12-01): wire InstrumentedEvalRecorder onto all 6 agents/team |
| `af3b2fc` | refactor(12-01): extract _build_eval_record helper |
