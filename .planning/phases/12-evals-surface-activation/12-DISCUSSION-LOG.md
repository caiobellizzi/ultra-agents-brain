# Phase 12 Discussion Log

**Date:** 2026-05-23
**Mode:** discuss (default), interactive AskUserQuestion
**Prior context loaded:** PROJECT.md, REQUIREMENTS.md, STATE.md, phase 10 AUDIT.md (§2 Evals), phase 10 DB-ID-DECISION.md, phase 11 CONTEXT.md, evals/conftest.py, evals/test_chat.py, datasets, baselines.

## Areas Selected by Operator

User selected all 4 proposed gray areas:
1. EVAL-01 write mechanism
2. Per-run scoring policy
3. EVAL-02 suite integration
4. Plan split + OBS-01 closeout

## Area 1 — EVAL-01 write mechanism

| Question | Options | Selected |
|---|---|---|
| How should each agent run produce an `agno_eval_runs` row? | (A) Post-run wrapper [recommended], (B) Upgrade Agno for `evals=` kwarg, (C) Factory-level monkey-patch decorator, (D) AgentOS lifecycle hook | **A — Post-run wrapper, mirror phase 11** |
| Which agents get the wrapper? | (A) All 6, (B) Conversational only, (C) Chat only | **A — All 6** |
| What goes into `eval_data` / `eval_input`? | (A) Full transcript (input + raw output + latency_ms + model_id), (B) Metadata-only (input_hash), (C) Per-agent via env var | **A — Full transcript** |
| Failure-mode policy on `create_eval_run()` error? | (A) Log-and-swallow [recommended], (B) Raise and fail run, (C) Log + swallow + circuit breaker | **A — Log and swallow** |

## Area 2 — Per-run scoring policy

| Question | Options | Selected |
|---|---|---|
| When does scoring happen? | (A) Metadata-only at run-time, suite scores [recommended]; (B) Async background scoring; (C) Synchronous judge per run; (D) Sync for chat only | **A — Metadata-only, suite scores** |
| Row tagging — distinguish run vs suite rows | (A) `eval_type` field 'run' vs 'accuracy'/'performance' [recommended]; (B) `eval_data.source` jsonb tag; (C) `eval_input.run_origin` | **A — `eval_type` field** |

## Area 3 — EVAL-02 suite integration

| Question | Options | Selected |
|---|---|---|
| Suite path to `agno_eval_runs` | (A) conftest fixture hooks each parametrized test [recommended]; (B) standalone CLI runner; (C) both; (D) replace Pydantic-stub tests with real agent calls | **A — conftest hook** |
| Keep baselines/*.json? | (A) Keep both [recommended]; (B) DB-only, drop baselines; (C) Keep baselines, skip DB writes when absent | **A — Keep both** |
| EVAL-03 tier swap verification | (A) Two-tier smoke + row diff assertion [recommended]; (B) Unit test mocking chat_model; (C) Both | **A — Two-tier smoke** |

## Area 4 — Plan split + OBS-01 closeout

| Question | Options | Selected |
|---|---|---|
| How to split phase 12 | (A) 3 plans mirroring phase 11 [recommended]; (B) 2 plans; (C) 1 plan | **A — 3 plans** |
| OBS-01 hook point | (A) Inside post-run wrapper, single hook [recommended]; (B) Subclass agno PostgresDb and override `create_eval_run`; (C) Both layers | **A — Inside wrapper** |
| OBS-01 log schema | (A) Mirror phase 11 base + eval-specific extras [recommended]; (B) Minimal phase 11 base only; (C) Separate `path='eval-run'` vs `'eval-suite'` | **A — Mirror + extras** |

## Scope Creep Redirected

None this session. Operator stayed on phase 12 scope throughout.

## Deferred Ideas Captured

- Async background scoring of run-level rows (v2.1+ candidate)
- PII / secret redaction in `eval_data` JSON (parallel to phase 11 MEM-04 candidate)
- DB-backed historical baselines replacing `baselines/*.json` (out of scope)

## Outcome

11 questions answered. All 4 areas resolved. 15 implementation decisions (D-01..D-15) captured in `12-CONTEXT.md`. Ready for `/gsd:plan-phase 12`.
