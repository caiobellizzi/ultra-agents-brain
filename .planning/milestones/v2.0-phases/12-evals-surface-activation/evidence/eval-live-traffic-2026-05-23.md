# 12-03 Task 1 — Live Traffic Evidence (EVAL-01 + OBS-01 eval path)

**Date:** 2026-05-23
**Host:** srv847330 (root@31.97.130.253)
**Service:** uab-brain.service
**Method:** curl `POST /agents/chat/runs` (Telegram surface deferred — same wrapper path)

## Bug found and fixed during verification

The plan 12-01 instance-level wrapper (`InstrumentedEvalRecorder.wrap(agent)`) was silently bypassed in the live HTTP path. Agno's `agno.os.utils.resolve_agent` → `get_agent_by_id(..., create_fresh=True)` calls `agent.deep_copy()` for every HTTP request to keep concurrent runs isolated. Pydantic deep-copy does not preserve attributes set via `instance.attr = closure` — the fresh copy lost the wrapped `arun` and reverted to the original `Agent.arun`. Result: HTTP runs completed normally with HTTP 200, but `ai.agno_eval_runs` stayed empty and no `agentos.eval` log line appeared.

Fix shipped in this same plan (commit immediately after this evidence file): `agentos.eval_recorder.patch_classes_for_recording(db)` replaces `Agent.run / arun / Team.run / arun` at the class level. Fresh deep_copy instances inherit the patched class methods, so every HTTP request now flows through the recorder.

## Redeploy

```bash
rsync agentos/eval_recorder.py agentos/app.py root@31.97.130.253:/opt/ultra-agents-brain/agentos/
ssh root@31.97.130.253 'systemctl restart uab-brain.service'
```

Result: `systemctl is-active uab-brain.service` → `active`. Startup logs show `Application startup complete` + `Uvicorn running on http://0.0.0.0:7000` at 2026-05-23 04:55:10 UTC.

## Live smoke

```bash
ssh root@31.97.130.253 'curl -sS -X POST "http://127.0.0.1:7000/agents/chat/runs" \
  -H "Content-Type: multipart/form-data" \
  -F "message=hello phase 12 round 2" \
  -F "stream=false" \
  -F "user_id=phase-12-smoke-2"'
```

Response: `HTTP 200`, run_id `6053a34f-23fb-4c55-a2de-077e907d1187`, status `COMPLETED`, response time 12.25s.

## OBS-01 log line (journalctl)

```
May 23 04:55:37 srv847330 uab-brain[3133158]: 2026-05-23 04:55:37,631 INFO agentos.eval OBS-01 eval write: {"path": "eval", "agent_id": "chat", "db_id": "ultra-brain-main", "row_id": "6053a34f-23fb-4c55-a2de-077e907d1187", "latency_ms": 12235, "status": "ok", "eval_type": "agent_as_judge", "model_provider": null, "model_id": null, "score": null, "case_id": null, "error_type": null, "error_msg": null}
```

D-15 schema parse:
- ✓ `path = "eval"`
- ✓ `agent_id = "chat"` (correct)
- ✓ `db_id = "ultra-brain-main"` (reads from instance, not hardcoded)
- ✓ `row_id = "6053a34f-..."` (matches the curl response run_id)
- ✓ `latency_ms = 12235` (positive integer)
- ✓ `status = "ok"`
- ✓ `eval_type = "agent_as_judge"`
- ✓ `score = null` (D-06 — metadata-only at write time, future scoring picks these up)
- ✓ `case_id = null` (D-15 — null for live-run path, populated for suite path)
- ⚠ `model_id = null`, `model_provider = null` — Agno's `RunOutput.model` is the string `"default-worker"` (not a `Model` object with `.id`/`.provider`). Wrapper's `_extract_model` returns `(None, None)` for string values. Known limitation; doesn't block EVAL-01 acceptance. Follow-up: read `response.model_provider_data.id` instead.

## DB confirmation (ai.agno_eval_runs)

```sql
SELECT run_id, agent_id, eval_type,
       eval_data->>'status' AS status,
       eval_data->>'latency_ms' AS lat_ms
FROM ai.agno_eval_runs
WHERE eval_type='agent_as_judge'
ORDER BY created_at DESC LIMIT 5;
```

```
count=2
{'run_id': '6053a34f-23fb-4c55-a2de-077e907d1187', 'agent_id': 'chat', 'eval_type': 'agent_as_judge', 'status': 'ok', 'lat_ms': '12235'}
{'run_id': '26de05ba-0f61-45f2-9c88-8d8cd8693da2', 'agent_id': 'chat', 'eval_type': 'agent_as_judge', 'status': 'ok', 'lat_ms': '14900'}
```

(The second row is from a pre-fix direct `await chat_agent.arun(...)` diagnostic — predates the HTTP-path fix.)

## EVAL-01 + OBS-01 (eval path) — verdict: PASSED

- HTTP path writes a row per non-streaming chat run.
- OBS-01 line emitted with all D-15 required fields (path/agent_id/db_id/row_id/latency_ms/status/eval_type/score/case_id).
- `model_id` / `model_provider` reporting is a documented follow-up — does not break the row write or the dashboard surface.
