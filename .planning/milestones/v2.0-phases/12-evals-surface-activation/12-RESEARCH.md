# Phase 12 RESEARCH — Evals Surface Activation

**Researched:** 2026-05-23
**Goal:** Validate CONTEXT.md D-01 through D-15 against the live Agno 2.6.7 source and the existing codebase before planning.

CONTEXT.md is unusually complete; this document is a **validation pass**, not a redesign. Findings are listed by severity, then the validation architecture (Nyquist) and TDD slicing are derived.

---

## Findings (severity-ordered)

### F1 — CRITICAL: `EvalType` enum has no `'run'` value (D-07 needs revision)

`agno/db/schemas/evals.py:7-12` defines:

```python
class EvalType(str, Enum):
    ACCURACY = "accuracy"
    AGENT_AS_JUDGE = "agent_as_judge"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"
```

`EvalRunRecord.eval_type: EvalType` (Pydantic field) will reject `"run"` at validation time. CONTEXT D-07 (`eval_type='run'` for live agent runs) cannot ship as written.

**Resolution options (planner picks):**

1. **Use `EvalType.AGENT_AS_JUDGE` for live runs** — semantically closest (we capture agent output for later judgment), and the existing `citation_judge` stub in `agentos/agents/chat.py:25-37` already names itself an `AgentAsJudgeEval`. Live rows are unscored (`eval_data.score = null`) which signals "not-yet-judged". Phase 12 deferred async-judging fits cleanly into this shape.
2. **Use `EvalType.ACCURACY` for both and discriminate via `name=`** — e.g. `name="live-run"` vs `name="suite-accuracy"`. Mixes semantics; harder to dashboard-filter.
3. **Use `EvalType.RELIABILITY` for live runs** — wrong semantics; reliability is about run-to-run determinism.

**Recommendation: Option 1 (`AGENT_AS_JUDGE`)** — kept that way, the `/eval-runs?eval_type=agent_as_judge` filter cleanly returns live traffic; `?eval_type=accuracy` returns suite cases. D-08 (async background scoring deferred) maps naturally onto AGENT_AS_JUDGE rows with `eval_data.score = null`. Suite rows stay on `EvalType.ACCURACY` as CONTEXT specifies (D-09).

**Plan implication:** Plan 12-01 must use `EvalType.AGENT_AS_JUDGE` (not the string `'run'`) and the OBS-01 log's `eval_type` field carries that string verbatim. Update `eval_type` discriminator semantics in D-07 inside the plan's `must_haves.truths`.

### F2 — `EvalRunRecord.run_id: str` is REQUIRED

`agno/db/schemas/evals.py:30` — `run_id` is non-optional. The wrapper MUST generate one per call. The Agno `Agent.run()` / `arun()` results expose a `run_id` attribute on the response object (RunResponse / Team output object) — reuse that to keep wrapper rows correlatable to Agno's internal run telemetry.

If `RunResponse.run_id` is not available, fall back to `str(uuid.uuid4())`.

### F3 — `eval_input: Optional[Dict[str, Any]]` and `eval_data: Dict[str, Any]`

Both are dicts, not arbitrary JSON strings. Agno sanitizes `eval_input` and `eval_data` strings before write (`postgres.py:2222-2229`). The wrapper must pass dicts:

- `eval_input = {"user_message": <verbatim input>}` (or `{"messages": [...]}` for multi-turn)
- `eval_data = {"output": <model_dump of response>, "latency_ms": int, "model_id": str, "model_provider": str, "status": "ok"|"error", "score": null}`

### F4 — `create_eval_run()` is sync; agent `arun()` is async — bridge needed

`agno/db/postgres/postgres.py:2196` — `create_eval_run` is **synchronous** (uses `with self.Session()`). `Agent.arun()` is async. Calling sync DB inside an async wrapper will block the event loop for the duration of the insert (small payload, expected p99 < 50 ms per CONTEXT threat model row 5, but still a block).

**Options (planner picks):**

1. **`asyncio.to_thread(self.db.create_eval_run, eval_run)`** — non-blocking, recommended.
2. **Direct sync call** — acceptable if insert latency is verified <50 ms on the VPS, matches the simplicity of `InstrumentedMemoryManager` which also calls sync DB from sync hook.
3. **Use `AsyncPostgresDb.create_eval_run`** — would require switching `agentos/app.py` from `PostgresDb` to `AsyncPostgresDb`, which is a much larger blast radius (memory + sessions + knowledge all use the sync class today). Out of scope.

**Recommendation: Option 1** (`asyncio.to_thread`) for the async path (`arun`), direct sync call for the sync path (`run`). This pattern survives `db.create_eval_run` ever growing slow without leaking latency into chat replies. Add a comment pointing at this decision.

### F5 — `InstrumentedMemoryManager` pattern is a SUBCLASS, not a wrapper

`agentos/instrumented_memory.py:25` — `class InstrumentedMemoryManager(MemoryManager)` subclasses Agno's `MemoryManager` and overrides `create_user_memories` / `acreate_user_memories` / `update_memory_task` / `aupdate_memory_task`. The OBS-01 log helper `_emit` lives **inside the subclass** — there is no shared `agentos/obs.py` to factor it into.

CONTEXT D-13 calls the new module a "post-run wrapper on Agent/Team `arun()` / `run()`". That is **architecturally different** from the memory pattern: we cannot subclass every `Agent` — agents are constructed by factories, not subclassed. We need a **decorator-style wrapper** that monkey-patches `agent.arun` / `agent.run` on the constructed agent, or a thin facade that owns a reference to the agent and forwards `__call__` / `arun` / `run`.

**Recommendation:** **decorator-style wrapper applied to the constructed Agent in `app.py`** — keep the factory signatures unchanged, then apply `InstrumentedEvalRecorder.wrap(agent, db)` after construction. The wrapper replaces `agent.run` and `agent.arun` bound methods with closures that call the original then write the eval row. This matches CONTEXT D-13's "wrapper" language and avoids changing the 6 factory signatures.

This also means the OBS-01 helper duplicated from `instrumented_memory.py:_emit` lives **inside the recorder module** (D-14 — single hook point). No shared `agentos/obs.py` for now; refactor only if the log helper grows a third caller.

### F6 — Suite path: pytest hook design

`evals/conftest.py` already has session-scoped `eval_db` and `judge_model` fixtures. To capture per-case score + output, the cleanest hook is `pytest_runtest_makereport` — fires after the test function returns, has access to `item` (test node), `call` (phase + duration), and `report.passed`. The test itself must stash the per-case `score` / `output` on the request scope so the hook can read them.

**Pattern:**

```python
# in conftest.py
@pytest.fixture
def eval_recorder(request, eval_db, judge_model):
    """Per-test recorder; tests call .record(score, output, eval_input) and the
    teardown hook below writes a row to agno_eval_runs."""
    captured = {}
    def record(score, output, eval_input):
        captured.update({"score": score, "output": output, "eval_input": eval_input})
    request.node.captured_eval = captured  # for the hook
    yield record

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    if call.when != "call":
        return
    captured = getattr(item, "captured_eval", None)
    if not captured or item.config.getoption("--write-baseline"):
        return  # baseline mode skips DB write
    if eval_db := item.funcargs.get("eval_db"):
        # build EvalRunRecord and call eval_db.create_eval_run(...)
        ...
```

Tests opt in by depending on `eval_recorder` and calling `eval_recorder(score, output, eval_input)` once the case completes. Tests that don't depend on `eval_recorder` produce no row — keeps the change additive.

**Alternative (autouse fixture)** rejected: would force every test in `evals/` to write a row, including the smoke tests that don't have a meaningful score.

### F7 — `test_run_id` for pytest retries (CONTEXT threat row 6)

A pytest session id generated once at `pytest_configure` and injected as a fixture is sufficient. `run_id = f"{test_run_id}-{item.nodeid}"` makes retries idempotent at the row level — the same nodeid in the same session produces the same `run_id`, and `INSERT ... ON CONFLICT DO UPDATE` (already used elsewhere in the postgres driver) handles the retry without duplicate rows.

**Caveat:** `create_eval_run` itself does **not** use `ON CONFLICT` — it does a plain `postgresql.insert(table).values(...)`. A pytest retry would raise `UniqueViolation` on `run_id`. Options:
- Catch `IntegrityError` in the suite hook and log-and-swallow (mirrors D-04).
- Use a fresh `run_id` per retry (`{nodeid}-{attempt}`) — loses idempotence but avoids the exception.

**Recommendation:** catch + log-and-swallow. The OBS-01 log line carries `status="duplicate"` so retry behavior is observable; the row already exists from the first attempt.

### F8 — `GET /eval-runs` route confirmed

`agno/os/routers/evals/evals.py:71` and `agno/os/scopes.py:455` — route exists at `GET /eval-runs` with optional query params. The `db_id` param semantics are inherited from the standard agno router; verify on the VPS post-deploy with `curl ${BRAIN_URL}/eval-runs?db_id=ultra-brain-main` returning HTTP 200.

CONTEXT canonical refs already specify `/eval-runs` (not `/evals`); F8 just confirms.

### F9 — `agentos/agents/chat.py` `citation_judge` stub stays (or goes)

`agentos/agents/chat.py:25-37` builds an `AgentAsJudgeEval` instance but never uses it (the `_ = citation_judge` line is documented as a "wire later" stub). Phase 12 doesn't depend on it and shouldn't extend it — judging live `AGENT_AS_JUDGE` rows is explicitly deferred (D-08). Leave the stub untouched.

If the planner wants to silence the unused-variable noise, that's a discretionary tidy in 12-01 — not a requirement.

---

## Confirmation of CONTEXT decisions (no change needed)

| Decision | Source confirmation |
|---|---|
| D-01: wrapper, no subclass of `PostgresDb` | Confirmed — `create_eval_run` is on `PostgresDb`; wrapping at the agent level keeps the DB class untouched |
| D-02: apply to all 6 agents | `agentos/app.py:54-59` already constructs all 6; wrapper application is 6 lines in `app.py` after construction |
| D-03: full transcript shape | `eval_data: Dict[str, Any]` accepts arbitrary keys; matches CONTEXT |
| D-04: log and swallow | `InstrumentedMemoryManager._emit` already establishes the precedent |
| D-05: read `db.id` not hardcode | `db.id` is a public attribute on `BaseDb` (`agno/db/base.py:56-61`) |
| D-06: per-run rows metadata-only, score=null | `eval_data` is `Dict[str, Any]`; including `"score": None` is fine |
| D-09: pytest hook (conftest) | Confirmed approach in F6 above |
| D-10: conditional on `eval_db is not None` | Fixture already returns None when `POSTGRES_DSN_SESSIONS` unset |
| D-11: baselines/*.json stays | Pre-commit router untouched; this plan is additive |
| D-12: EVAL-03 two-tier smoke | No code blocker; operator runs the suite twice with the env var |
| D-13: three plans | Mirrors phase 11 layout exactly |
| D-14: single OBS-01 hook point | Wrapper owns the log emission for both paths |
| D-15: log schema | Compatible with `agentos.memory` log helper pattern |

---

## Validation Architecture (Nyquist input)

The Phase 12 verification protocol (CONTEXT §verification_protocol) drives six validation points. Mapping to Nyquist dimensions:

### V1 — Recorder correctness (D1: Behavior / D8: Validation)
- **Probe:** unit test `tests/unit/test_eval_recorder.py::test_wrap_writes_row_on_success`
- **Asserts:** wrapping an agent's `run()` and `arun()` calls `db.create_eval_run` once with `eval_type=AGENT_AS_JUDGE`, `eval_data["score"] is None`, `eval_data["latency_ms"] > 0`, `eval_data["model_id"]` present.
- **Coverage:** D-01, D-03, D-05, D-06, D-07-revised, F1, F4

### V2 — Recorder failure swallowed (D1: Behavior / D7: Resilience)
- **Probe:** unit test `test_wrap_swallows_db_error`
- **Asserts:** when `db.create_eval_run` raises, the wrapped agent's return value is unchanged; an OBS-01 error log line is emitted; no exception propagates to the caller.
- **Coverage:** D-04, F4

### V3 — OBS-01 log schema (D2: Telemetry)
- **Probe:** unit test `test_wrap_emits_obs01_schema`
- **Asserts:** the captured log record contains the 11 required fields from D-15 with correct types and `path == "eval"`.
- **Coverage:** D-14, D-15

### V4 — Conftest hook writes accuracy row (D1: Behavior)
- **Probe:** integration test `tests/integration/test_eval_suite_surface.py::test_single_case_writes_row` marked `@pytest.mark.live`
- **Asserts:** running one parametrized eval case end-to-end against a live `eval_db` produces exactly one new row in `ai.agno_eval_runs` with `eval_type='accuracy'` and `score` matching what the test computed.
- **Coverage:** D-09, D-10, F6, F7

### V5 — Tier swap propagation (D1: Behavior end-to-end)
- **Probe:** operator-driven smoke; `EVAL_JUDGE_TIER=private-worker pytest evals/chat/` then `EVAL_JUDGE_TIER=orchestrator pytest evals/chat/`; capture rows; assert `model_id` differs between the two sets.
- **Coverage:** D-12, EVAL-03 success criterion

### V6 — API + dashboard visibility (D1: Behavior, surface)
- **Probe:** `curl ${BRAIN_URL}/eval-runs?db_id=ultra-brain-main` returns 200 + non-empty `data[]`; operator-confirmed dashboard render.
- **Coverage:** F8, EVAL-01 success criterion

### V7 — Idempotence on pytest retry (D7: Resilience)
- **Probe:** unit test `test_suite_hook_swallows_duplicate_run_id`
- **Asserts:** calling the conftest hook twice with the same `run_id` produces one DB row and one OBS-01 `status="duplicate"` log line; no exception.
- **Coverage:** F7, threat row 6

---

## TDD Slicing (TDD mode is enabled)

- **TDD-eligible (`type: tdd`):**
  - `InstrumentedEvalRecorder.wrap_async()` — pure I/O wrapping logic with defined input (agent + db + run kwargs) and output (response + side-effect row + log line). RED: test_wrap_writes_row_on_success. GREEN: minimal wrapper. REFACTOR: extract `_build_eval_record`.
  - `InstrumentedEvalRecorder.wrap_sync()` — same shape, sync.
  - `_emit_obs01` log helper — pure function: dict in, log call out.
  - Conftest `record_eval_row(eval_db, captured, judge_model)` helper — pure function for V4.

- **Standard `type: execute`:**
  - Applying the wrapper in `agentos/app.py` (one-line glue per agent).
  - The conftest `pytest_runtest_makereport` hook (pytest hookimpl wiring; not naturally testable in isolation — V4 integration test covers it).
  - EVAL-03 two-tier smoke + VERIFICATION.md (documentation + operator action).

---

## Open question for the planner

`run_id` field on Agno's `RunResponse` / `TeamRunResponse` — confirm the attribute name. Quick grep:

```bash
grep -n "self\.run_id\|run_id:" .venv/lib/python3.13/site-packages/agno/agent/agent.py | head -5
```

If the attribute exists, use it; otherwise fall back to `uuid.uuid4()`. This is a "first task in 12-01" verification, not a research blocker — the fallback is safe either way.

---

## Plan split (CONTEXT D-13 unchanged)

- **12-01** — `agentos/eval_recorder.py` module: `InstrumentedEvalRecorder` class with `wrap(agent_or_team)` API, `_build_eval_record` helper, `_emit_obs01` log helper; apply wrapper in `agentos/app.py` to all 6 constructed agents/team; unit tests in `tests/unit/test_eval_recorder.py` covering V1, V2, V3. Resolves F1, F2, F3, F4, F5.
- **12-02** — Extend `evals/conftest.py`: `eval_recorder` fixture + `pytest_runtest_makereport` hookimpl + `test_run_id` session fixture; integration test in `tests/integration/test_eval_suite_surface.py` covering V4 and V7. Resolves F6, F7.
- **12-03** — EVAL-03 two-tier smoke procedure + VERIFICATION.md closeout covering V5 and V6.

---

## RESEARCH COMPLETE
