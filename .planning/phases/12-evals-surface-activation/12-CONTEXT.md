# Phase 12 CONTEXT — Evals Surface Activation

**Gathered:** 2026-05-23
**Status:** Ready for planning
**Source:** Discussion 2026-05-23 + phase 10 audit (RC-no-eval-harness) + phase 11 patterns.

<domain>
## Phase Boundary

Wire `db.create_eval_run()` so per-agent-run scores **and** the 48-case suite populate `ai.agno_eval_runs`, then verify the rows surface at `GET /eval-runs` and on the os.agno.com Evals tab. Mirror phase 11 patterns: pinned `db_id="ultra-brain-main"`, instrumented wrapper for OBS-01, post-run hook (no Agno upgrade, no vendor subclass).

**Deliverables (code):**
- `agentos/eval_recorder.py` — `InstrumentedEvalRecorder` post-run wrapper + structured logging
- Wrapper applied to all 6 agents (chat, query, research, supervisor, curator, ingest) in their factories
- `evals/conftest.py` extended with a pytest hook that writes one `eval_type='accuracy'` row per parametrized case
- Two-tier smoke procedure for EVAL-03 (`EVAL_JUDGE_TIER=private-worker` then `=orchestrator`)
- VERIFICATION.md closeout once dashboard shows rows for both run-level and suite-level entries

**Out of scope:**
- Knowledge surface (phase 13)
- Approvals surface (phase 14)
- worker.monitor polish (phase 15)
- PII redaction in `eval_data` JSON (track as backlog item)
- Auto-judging of run-level rows (async worker / queue) — explicitly deferred; run-level rows are metadata-only
- Replacing the pre-commit pytest router (stays as-is; baselines/*.json stays as the fast offline check)
- Bumping Agno past 2.6.7 to get the native `evals=` kwarg

</domain>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` — Phase 12 success criteria (4 items)
- `.planning/REQUIREMENTS.md` — EVAL-01, EVAL-02, EVAL-03, OBS-01 (eval path)
- `.planning/PROJECT.md` — architecture invariants (AgentOS = single source of truth; LiteLLM at 127.0.0.1:4000)

### Phase 10 audit findings (locked context)
- `.planning/phases/10-diagnostic-audit/AUDIT.md` §2 Evals surface (lines 93–139) — RC-no-eval-harness root cause; endpoint is `/eval-runs` (not `/evals`); `ai.agno_eval_runs` schema; `citation_judge` constructed but unused due to missing `evals=` kwarg on Agent in Agno 2.6.7
- `.planning/phases/10-diagnostic-audit/DB-ID-DECISION.md` — Option A locked (shared `db_id="ultra-brain-main"`)
- `.planning/phases/10-diagnostic-audit/BACKLOG.md` — open tech debt that is NOT phase 12 territory

### Phase 11 patterns to mirror
- `.planning/phases/11-memory-surface-activation/11-CONTEXT.md` D-08 (OBS-01 hook point pattern), D-13 (rollback strategy), D-11 (threat model template)
- `agentos/instrumented_memory.py` (existing) — reference implementation for the `Instrumented*` wrapper pattern
- `.planning/phases/11-memory-surface-activation/11-03-SUMMARY.md` — OBS-01 closeout pattern (structured log schema, unit test shape, smoke evidence)

### Existing codebase touch points
- `agentos/app.py` — where `PostgresDb(id="ultra-brain-main")` is constructed; where the recorder gets wired into each agent factory
- `agentos/agents/{chat,query,research,curator,ingest,supervisor}.py` — factories that will receive the wrapper
- `agentos/agents/chat.py:25-37, 75-77` — current `citation_judge` site that documents the missing `evals=` kwarg in Agno 2.6.7; phase 12 supersedes the held-back stub
- `agentos/model.py` — `chat_model(EVAL_JUDGE_TIER)` dispatch (LiteLLM tier routing); must not regress
- `evals/conftest.py` — `eval_db` fixture (returns `PostgresDb` when `POSTGRES_DSN_SESSIONS` set, else `None`); `judge_model` fixture (reads `EVAL_JUDGE_TIER`)
- `evals/test_*.py` — 6 files (chat/query/research/curator/ingest/supervisor); parametrized integration cases driven by `evals/datasets/*_cases.py`
- `evals/baselines/{accuracy,performance}_baseline.json` — current stub baselines (avg_score 0.0); STAYS as the pre-commit offline check
- `evals/datasets/*_cases.py` — case definitions (3 cases each for chat/query/research; curator/ingest/supervisor smaller)

### Agno framework (external — vendor source, do not edit)
- `agno/db/postgres/postgres.py:2196` — `PostgresDb.create_eval_run()` (sync)
- `agno/db/postgres/async_postgres.py:2001` — async variant
- `agno/db/base.py:61` — default table name `agno_eval_runs`
- https://docs.agno.com/ — eval/agent docs (reference only; do not depend on docs being correct, phase 10 already proved doc drift exists)

### AgentOS API
- `GET /eval-runs` — list endpoint that the os.agno.com dashboard hits (NOT `/evals`)
- Optional query param: `?db_id=ultra-brain-main`

</canonical_refs>

<code_context>
## Reusable Assets

- **`InstrumentedMemoryManager` (phase 11)** — drop-in subclass + structured-log pattern. Reuse the log emission helper if it's been factored out; otherwise mirror the schema verbatim.
- **`eval_db` fixture (already in conftest.py)** — returns `PostgresDb` instance or `None`. Suite path (EVAL-02) builds on this — no new DB plumbing needed.
- **Pre-commit eval router** — untouched. Continues comparing `accuracy_baseline.json` / `performance_baseline.json`. Phase 12 adds DB rows alongside, doesn't replace.
- **`chat_model(EVAL_JUDGE_TIER)`** — already routes by tier. Phase 12 only needs to ensure the tier value flows into `eval_data.model_id` / `model_provider`, not change the dispatcher.
- **`PostgresDb(id="ultra-brain-main")`** — pinned in phase 11. Recorder reads `db.id` directly; do not hardcode.

## Integration Points

- Recorder must be **idempotent under failure** — `create_eval_run()` errors log + swallow; agent reply still returns.
- Recorder must read `db_id` from the `PostgresDb` instance passed in, not hardcode the literal — keeps the Option A pin centralized.
- `eval_type` field is the discriminator: `'run'` for live runs, `'accuracy'` for suite cases (mirrors the existing `accuracy_baseline.json` naming). Performance baselines map to `eval_type='performance'`.
- conftest pytest hook fires **after** the test function returns, regardless of pass/fail. Failed tests still produce a row with `status='fail'`.

</code_context>

<decisions>
## Implementation Decisions

### Area 1 — EVAL-01 write mechanism

- **D-01:** Implement `InstrumentedEvalRecorder` as a **post-run wrapper** on Agent/Team `arun()` / `run()`. After each run completes, call `db.create_eval_run()` synchronously (in-band) with input, output, latency_ms, agent_id, db_id, model_id, model_provider. No Agno upgrade, no vendor subclass.
- **D-02:** Apply the wrapper to **all 6 agents**: `chat`, `query`, `research`, `supervisor`, `curator`, `ingest`. Curator + ingest already opted out of memory extraction in phase 11; eval recording is a different concern (we want operational visibility into bulk paths too).
- **D-03:** Row payload shape — **full transcript**: `eval_input` carries the user input verbatim; `eval_data` carries the Pydantic-dumped agent output, `latency_ms`, `model_id`, `model_provider`, `status`. Same risk profile as `agno_memories` (PII lives in DB) — track redaction as a future backlog item.
- **D-04:** Failure mode — **log and swallow**. If `create_eval_run()` raises (DB unreachable, schema mismatch, encoding error), emit OBS-01 with `status='error'`, `error_type`, `error_msg`; agent reply still returns. Mirrors phase 11 `MemoryManager` behavior. Eval recording is instrumentation, not a critical path.
- **D-05:** Wrapper must read `db_id` from the `PostgresDb` instance — never hardcode `"ultra-brain-main"`. Keeps the phase 11 Option A pin centralized.

### Area 2 — Per-run scoring policy

- **D-06:** Per-run rows are **metadata-only at write-time** — `eval_data.score = null`. Scoring is the 48-case suite's job (EVAL-02 path). No synchronous judge call inside the wrapper, no async worker. Zero added latency on user chat.
- **D-07:** `eval_type='run'` distinguishes live agent runs from suite rows. Suite rows use `eval_type='accuracy'` (default) or `eval_type='performance'` for the performance suite. Uses Agno's native `eval_type` column — no JSON-side filtering needed.
- **D-08:** Async background scoring of run-level rows is explicitly **out of scope for phase 12**. If we want it later, the row schema already supports it (score=null is a queue-able marker). Track as a future feature, not a tech-debt item.

### Area 3 — EVAL-02 suite integration

- **D-09:** Extend `evals/conftest.py` with a **pytest hook (`pytest_runtest_makereport` or autouse fixture)** that, for each parametrized case, calls `eval_db.create_eval_run(eval_type='accuracy', …)` with input, output, score, agent_id, db_id, judge_model_id. Pytest stays the runner. Pre-commit eval router unchanged.
- **D-10:** Suite rows are written **conditionally**: only when `eval_db is not None` (i.e., `POSTGRES_DSN_SESSIONS` is set). Offline / smoke runs without Postgres skip the write — pre-commit and dev loops don't require DB.
- **D-11:** Both persistence paths stay live: `evals/baselines/*.json` remains the fast offline check used by the pre-commit eval router; `agno_eval_runs` is the historical record + dashboard source. No migration off baselines/.
- **D-12:** EVAL-03 verification = **two-tier smoke**. Run the suite once with `EVAL_JUDGE_TIER=private-worker`, capture row count and a sample `model_id` from `eval_data`. Run again with `EVAL_JUDGE_TIER=orchestrator`, assert new rows show a different `model_provider` / `model_id`. Evidence captured in VERIFICATION.md. No mocked unit test for the tier dispatch — end-to-end only.

### Area 4 — Plan split + OBS-01 closeout

- **D-13:** **Three plans, mirroring phase 11**:
  - **12-01** — `InstrumentedEvalRecorder` + wrapper application to all 6 agent factories + OBS-01 (eval path) instrumentation + unit tests (`tests/unit/test_eval_recorder.py`).
  - **12-02** — `evals/conftest.py` pytest hook + `eval_db` conditional write + integration test that runs a single parametrized case end-to-end and asserts the row appears (`@pytest.mark.live`).
  - **12-03** — EVAL-03 two-tier smoke + VERIFICATION.md closeout (operator verifies dashboard shows both `eval_type='run'` and `eval_type='accuracy'` rows; both tiers represented).
- **D-14:** OBS-01 (eval path) hook point — **inside `InstrumentedEvalRecorder`**, single hook for both run-level and suite rows. The conftest fixture calls the same recorder, so one log site covers both paths. No vendor subclass of `PostgresDb`.
- **D-15:** OBS-01 log schema — **mirror phase 11 base + eval extras**. Required: `ts`, `level`, `path='eval'`, `agent_id`, `db_id`, `row_id`, `latency_ms`, `status`. Eval-specific: `eval_type`, `model_provider`, `model_id`, `score` (null for run-level), `case_id` (null for run-level). On failure: `status='error'`, `error_type`, `error_msg`, `row_id=null`.
  ```json
  {"ts": "2026-05-23T...", "level": "info", "path": "eval",
   "agent_id": "chat", "db_id": "ultra-brain-main",
   "row_id": "...", "latency_ms": 8421, "status": "ok",
   "eval_type": "run", "model_provider": "litellm",
   "model_id": "openai/gpt-4o", "score": null, "case_id": null}
  ```

### Claude's Discretion

- Module name: `agentos/eval_recorder.py` vs `agentos/instrumented_eval.py` (suggest the former for symmetry with phase 11's `instrumented_memory.py`).
- Exact pytest hook style (`pytest_runtest_makereport` vs autouse fixture) — planner picks based on which gives cleanest access to test output.
- Whether to factor the OBS-01 log helper out of `instrumented_memory.py` into a shared `agentos/obs.py` if it isn't already, to avoid duplicating the JSON dict construction.
- Exact ordering of `eval_data` keys.

</decisions>

<verification_protocol>
## Verification Protocol (phase-end gate)

After all 3 plans (12-01, 12-02, 12-03) ship + deploy:

1. **Live-traffic check (EVAL-01).** Send one real Telegram message to the chat agent. Within 5 s, `psql -c "SELECT count(*) FROM ai.agno_eval_runs WHERE eval_type='run' AND created_at > now()::date::bigint*1000"` returns ≥1.
2. **API check (EVAL-01).** `GET /eval-runs?eval_type=run` returns HTTP 200 with non-empty `data[]`.
3. **Suite check (EVAL-02).** `POSTGRES_DSN_SESSIONS=… pytest evals/` writes ≥18 new rows with `eval_type='accuracy'`. `pg_stat n_tup_ins` delta ≥ test count.
4. **Tier-swap check (EVAL-03).** Re-run the suite with `EVAL_JUDGE_TIER=orchestrator`. New rows show a different `model_id` in `eval_data` than the `private-worker` run. Captured in VERIFICATION.md.
5. **OBS-01 log check.** `journalctl -u uab-brain.service | grep '"path":"eval"'` shows one JSON line per write, well-formed, with all required fields. At least one `status='error'` line generated by a fault-injection test in 12-01.
6. **UI check.** Operator opens os.agno.com Evals tab. The dashboard renders both run-level and accuracy rows. (Operator-confirmed; no PNG required unless something looks wrong.)

If any of (1)–(6) fails: open a fix-up plan; do not declare phase 12 done.

</verification_protocol>

<threat_model>
## Threat Model

| Threat | Mitigation |
|---|---|
| `create_eval_run()` failure breaks user chat | Log-and-swallow (D-04); fault-injection test in 12-01 unit suite. |
| PII / secrets in `eval_data` JSON | Out of phase 12 scope. Track as backlog (parallel to phase 11 MEM-04 candidate). |
| Eval row count explodes (write per run × many runs) | Acceptable — `agno_eval_runs` is small JSON; no FK explosion. If we hit volume issues, add retention later. |
| Hardcoded `db_id` drifts from phase 11 pin | D-05 — read `db.id` from the instance, never hardcode. |
| Synchronous DB write adds latency to chat replies | Single insert per run with small payload; expected p99 < 50 ms. If higher, recorder moves to fire-and-forget `asyncio.create_task()` in a follow-up. |
| Suite hook double-writes when pytest retries | Use a `test_run_id` (generated once per pytest session) so retries replace not duplicate. |
| `EVAL_JUDGE_TIER` swap doesn't propagate to `eval_data.model_id` | EVAL-03 two-tier smoke directly proves it; no separate guard needed. |

</threat_model>

<deferred>
## Deferred Ideas (not phase 12)

- Async background scoring worker that judges run-level (eval_type='run') rows in the background — would auto-score prod traffic. Track for v2.1+.
- PII / secret redaction inside `eval_data` JSON before write. Track as joint backlog with phase 11 MEM-04 candidate.
- Dashboard query helpers (`make check-surfaces` row from REQUIREMENTS OBS-02) — that's phase 15 territory.
- Score-driven alerting (page when avg score drops below threshold) — feature for a later milestone.
- Replacing `baselines/*.json` with DB-backed historical baselines — premature optimization; baselines are working and offline-friendly.

</deferred>

<rollback>
## Rollback Strategy

- 12-01 is additive — new `agentos/eval_recorder.py` + 1-line wrapper application per agent factory. Rollback = `git revert`. `InstrumentedEvalRecorder` is a drop-in wrapper; if it has a bug, remove the wrapper application and the agents fall back to plain `Agent.arun()`.
- 12-02 is additive — new conftest hook + integration test. Rollback = `git revert`. No data migration.
- 12-03 is documentation — VERIFICATION.md only. No rollback needed.

</rollback>
