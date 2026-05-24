---
phase: 12
plan: 04
slug: evals-surface-activation
status: passed
must_haves_total: 5
must_haves_passed: 5
verified: 2026-05-24
verifier: codex-inline
supersedes: 12-VERIFICATION.md
---

# Phase 12 Plan 04 — Corrective Verification Report

**Verdict: PASSED.** This corrective verification supersedes the 2026-05-23 Phase 12 row-semantics decision. New unjudged live telemetry rows are `performance` parent rows; suite cases remain scored `accuracy` rows; optional live judgments are child `agent_as_judge` rows linked by `eval_data.parent_run_id`.

## Corrective Must-Haves

| # | Must-have | Status | Evidence |
|---|-----------|--------|----------|
| 1 | Unjudged live agent rows use `EvalType.PERFORMANCE`, `name=live:<agent_id>`, and `evaluated_component_name=<agent_id>`. | Passed | `tests/unit/test_eval_recorder.py`; `agentos/eval_recorder.py` |
| 2 | Scored suite rows remain `EvalType.ACCURACY` with deterministic `suite:<agent_id>:<case_id>:<git_identity>` run ids. | Passed | `tests/unit/test_eval_suite_hook.py`; `evals/conftest.py`; all six `evals/test_*.py` call `eval_recorder`. |
| 3 | Judged live rows are separate child `EvalType.AGENT_AS_JUDGE` rows linked to parent performance rows via `eval_data.parent_run_id`. | Passed | `tests/unit/test_live_judge.py`; `agentos/live_judge.py` |
| 4 | Live judging is disabled by default, privacy-gated, sampled, retry-limited, and never blocks user-facing responses. | Passed | `tests/unit/test_eval_live_policy.py`; recorder only marks pending rows, worker handles judge calls. |
| 5 | Historical `Untitled Evaluation` rows are not mutated or deleted. | Passed | Implementation only creates new rows and updates current pending parent metadata; no migration/delete path exists. |

## Requirement Traceability

| Requirement | Status | Notes |
|-------------|--------|-------|
| EVAL-01 | Passed | Live runs create dashboard-visible eval rows as `performance` telemetry for new runs. |
| EVAL-02 | Passed | The 48-case eval suite records scored `accuracy` rows when `eval_db` is configured. Offline runs remain no-op for DB writes. |
| EVAL-03 | Passed | Judge tier/model is still surfaced through suite metadata and child live judge rows. |
| OBS-01 (eval path) | Passed | Recorder and suite helper emit structured eval-path logs; failure/duplicate paths are covered. |

## Automated Verification

- `PYTHONPATH=. .venv/bin/pytest tests/unit/test_eval_recorder.py tests/unit/test_eval_suite_hook.py tests/unit/test_eval_live_policy.py tests/unit/test_live_judge.py -q` — passed, 20 tests.
- `PYTHONPATH=. .venv/bin/pytest evals/ --collect-only -q` — passed, 48 tests collected.
- `PYTHONPATH=. .venv/bin/pytest evals/ -q -m "not live"` — passed, 48 tests.
- `PYTHONPATH=. .venv/bin/python -m py_compile agentos/live_judge.py agentos/__main__.py` — passed.
- `PYTHONPATH=. .venv/bin/python -m agentos live-judge --help` — passed without starting the server.
- `make eval-smoke` — passed, 30 smoke tests.
- `make test` — failed on five out-of-scope items documented in `deferred-items.md`.

## Code Review

`12-REVIEW.md` status is `clean` after one fix:

- `4c0c417` records wrapped agent exception paths with `eval_data.status="error"` instead of incorrectly marking failed live runs as `ok`.

## Drift / Gate Notes

- Schema drift check: no drift detected.
- Codebase drift check: warning only. It reports broad unmapped project structure because no `last_mapped_commit` is present; this is non-blocking by workflow contract.
- Live Postgres/model verification remains opt-in because it depends on deployed services and may cost money. Corrective semantics are locked by unit and offline eval tests.

## Superseded Verification

The earlier `12-VERIFICATION.md` accepted live parent rows as `EvalType.AGENT_AS_JUDGE`. Plan 12-04 supersedes that decision. Historical rows produced under the old semantics are intentionally left untouched.

## Phase 12 Status

Phase 12 is ready for human/operator review or the next workflow step. The remaining `make test` failures are not introduced by this phase and are tracked in `deferred-items.md`.
