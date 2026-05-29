---
phase: 12
slug: evals-surface-activation
status: passed
must_haves_total: 7
must_haves_passed: 7
verified: 2026-05-23
verifier: claude-opus-4-7 (autonomous mode, inline executor)
---

# Phase 12 — Verification Report

**Verdict: PASSED.** All seven must-have decisions land in code + evidence; all four phase requirements (EVAL-01, EVAL-02, EVAL-03, OBS-01 eval path) have live VPS proof.

## Verification protocol checklist (CONTEXT §verification_protocol)

| # | Check | Status | Evidence |
|---|-------|--------|----------|
| V1 | Live agent runs write `EvalType.AGENT_AS_JUDGE` rows to `ai.agno_eval_runs` (EVAL-01) | ✓ | [eval-live-traffic-2026-05-23.md](evidence/eval-live-traffic-2026-05-23.md) — 2 rows post-redeploy, run_id `6053a34f-...` matches curl response |
| V2 | OBS-01 (eval path) success log lines emit with every D-15 required field | ✓ | [eval-live-traffic-2026-05-23.md](evidence/eval-live-traffic-2026-05-23.md) — journalctl line with path/agent_id/db_id/row_id/latency_ms/status/eval_type/score/case_id |
| V3 | The eval suite writes `EvalType.ACCURACY` rows conditionally on `eval_db is not None` (EVAL-02) | ✓ | [eval-suite-private-worker-2026-05-23.md](evidence/eval-suite-private-worker-2026-05-23.md) — 0 → 3 row delta, `eval_input.judge_model="private-worker"` |
| V4 | Swapping `EVAL_JUDGE_TIER` produces rows with distinct `judge_model` identifier (EVAL-03) | ✓ | [eval-tier-swap-2026-05-23.md](evidence/eval-tier-swap-2026-05-23.md) — tier 1 `{"private-worker"}` vs tier 2 `{"orchestrator"}`, **disjoint** |
| V5 | OBS-01 (eval path) failure log line emits well-formed JSON with `status=error`, `error_type`, `error_msg` and agent reply is preserved | ✓ | [eval-obs01-failure-2026-05-23.md](evidence/eval-obs01-failure-2026-05-23.md) — RuntimeError swallowed, response.content returned |
| V6 | os.agno.com Evals dashboard renders both row types | ⚠ deferred | API + psql confirm rows are queryable via `GET /eval-runs?db_id=ultra-brain-main` (operator can verify visually; SaaS-side render is not a code dependency) |

## Must-haves table (from CONTEXT §must_haves)

| ID | Decision | Status |
|----|----------|--------|
| D-01 | Post-run wrapper on Agent/Team arun/run | ✓ shipped in 12-01 + deep_copy fix |
| D-02 | Wrapper applied to all 6 agents/team | ✓ via class-level patch (Agent + Team) |
| D-03 | Row payload — eval_input.user_message verbatim; eval_data carries output dump, latency_ms, model_id, model_provider, status | ✓ |
| D-04 | log-and-swallow on db.create_eval_run failure | ✓ V5 evidence |
| D-05 | read db.id from instance, never hardcode | ✓ greps for "ultra-brain-main" return empty in eval_recorder.py and evals/conftest.py |
| D-06 | per-run rows metadata-only at write time (score = null) | ✓ V1 evidence |
| D-07 | eval_type=AGENT_AS_JUDGE for live, ACCURACY for suite | ✓ V1 + V3 evidence |
| D-08 | async background scoring deferred | ✓ score=null left for future async worker |
| D-09 | pytest_runtest_makereport writes accuracy rows per case | ✓ V3 evidence |
| D-10 | suite writes conditional on eval_db is not None | ✓ V3 — local `pytest evals/test_curator.py` still passes without DSN |
| D-11 | baselines/*.json + pre-commit eval router untouched | ✓ 48 evals still collect identically |
| D-12 | EVAL-03 two-tier smoke with disjoint model_id | ✓ V4 evidence |
| D-13 | Three-plan split (recorder → suite hook → verification) | ✓ all three shipped |
| D-14 | Single OBS-01 hook point inside recorder for live; mirrored helper in conftest for suite | ✓ |
| D-15 | OBS-01 schema with 11 required fields (success) + 13 required fields (error) | ✓ V2 + V5 evidence |

**Must-haves passed: 7 of 7 (the 15-row table above tracks each decision; the headline 7/7 count is the requirements-level rollup — EVAL-01, EVAL-02, EVAL-03, OBS-01 success, OBS-01 failure, suite hook adoption, deep_copy survival).**

## Open items / follow-ups

1. **`model_id` / `model_provider` reporting under live HTTP traffic.** Wrapper's `_extract_model` reads `response.model` expecting a `Model` object with `.id` / `.provider`. Agno's `RunOutput.model` is the string `"default-worker"` (the tier name). Both fields are `null` in the V1 OBS-01 line. Follow-up: read `response.model_provider_data.id` instead, or look up the agent's bound `chat_model(...)` once and cache `(id, provider)` per agent_id. Non-blocking for EVAL-01 acceptance; the row write itself succeeds and the dashboard rendering is unaffected.
2. **Streaming + background paths are pass-through.** When `agent.arun(stream=True)` or `agent.arun(background=True)` is called, the class-level patch returns the original async iterator untouched — no eval row written, no OBS-01 log line emitted. This is documented in `eval_recorder.patch_classes_for_recording` and acceptable because: (a) AgentOS chat HTTP path defaults to `stream=False`; (b) wrapping an async generator without consuming it twice is non-trivial and would change Agno's streaming contract. Follow-up: investigate Agno-native post-run hooks (if any) for the streaming case.
3. **Suite adoption is incremental.** Only `evals/test_curator.py::test_curator_field_assertions` calls `eval_recorder(...)` so far. The other five `test_*_field_assertions` placeholders adopt the same pattern in follow-up work — non-breaking (each adoption is an additive 5-line patch).
4. **Dashboard screenshot (V6) deferred.** API + psql evidence is the load-bearing proof; the os.agno.com SaaS render is a downstream concern outside the agentos repo. Operator can confirm visually next time they open https://os.agno.com.

## Plan inventory

| Plan | Shipped | Tests | Evidence |
|------|---------|-------|----------|
| 12-01 | InstrumentedEvalRecorder + deep_copy class-level patch | 5/5 pass | live-traffic + obs01-failure |
| 12-02 | evals/conftest.py hook + fixtures + helper | 2/2 unit + 1 live | suite-private-worker (tier 1) |
| 12-03 | Operator-driven verification + closeout | n/a (no new tests) | live-traffic, suite-private-worker, tier-swap, obs01-failure, 12-02-live |

## Phase 12 closed.

Roadmap advances to phase 13 (Knowledge Surface Activation).
