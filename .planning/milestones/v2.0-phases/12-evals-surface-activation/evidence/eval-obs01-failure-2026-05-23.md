# 12-03 Task 5 — OBS-01 failure-path evidence

**Date:** 2026-05-23
**Host:** srv847330 (root@31.97.130.253)
**Approach:** Direct invocation (VPS .venv lacks `pytest-asyncio`, so the unit test path was bypassed in favour of an equivalent inline script that targets the same `_record` swallow contract).

## Inline script

```python
class FailingDb:
    id = "failing-db"
    def create_eval_run(self, record):
        raise RuntimeError("synthetic DB outage for OBS-01 failure-path evidence")

class StubAgent:
    id = "obs01-failure-test"
    def run(self, *args, **kwargs): ...
    async def arun(self, *args, **kwargs):
        return SimpleNamespace(run_id="r-fail-1", content="x",
                               model=SimpleNamespace(id="m/x", provider="t"))

async def main():
    agent = StubAgent()
    recorder = InstrumentedEvalRecorder(db=FailingDb())
    recorder.wrap(agent)
    out = await agent.arun("hi")
    print("OUTPUT_RETURNED:", out.content)
```

## Output

```
ERROR:agentos.eval:OBS-01 eval write failed: {"path": "eval", "agent_id": "obs01-failure-test", "db_id": "failing-db", "row_id": null, "latency_ms": 1, "status": "error", "eval_type": "agent_as_judge", "model_provider": "t", "model_id": "m/x", "score": null, "case_id": null, "error_type": "RuntimeError", "error_msg": "synthetic DB outage for OBS-01 failure-path evidence"}
OUTPUT_RETURNED: x
```

## D-15 failure schema parse

- ✓ `path = "eval"`
- ✓ `status = "error"`
- ✓ `error_type = "RuntimeError"`
- ✓ `error_msg = "synthetic DB outage for OBS-01 failure-path evidence"` (truncated to 200 chars per the wrapper contract)
- ✓ `row_id = null` (the row was NOT written, so no id)
- ✓ All D-15 baseline fields still present (path, agent_id, db_id, latency_ms, eval_type, model_id, model_provider, score, case_id)
- ✓ Logged at ERROR level (vs INFO for the success path), routable separately in monitoring

## Swallow contract verified

`OUTPUT_RETURNED: x` confirms `agent.arun("hi").content == "x"` — the agent reply was returned unchanged even though `db.create_eval_run` raised. T-12-02 mitigation is locked.

## OBS-01 (eval path, failure side) verdict: PASSED

Failure-path log line is well-formed, carries D-15 fields, and survives a synthetic DB outage without breaking the caller.
