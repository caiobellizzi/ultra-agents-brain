---
phase: 12-evals-surface-activation
plan: 02
subsystem: evals
tags: [pytest-hook, evals-conftest, accuracy-rows, obs-01, integrityerror-swallow]

requires:
  - phase: 12-evals-surface-activation
    provides: plan 12-01 — InstrumentedEvalRecorder and OBS-01 log schema for path=eval
provides:
  - eval_recorder fixture — tests opt in by calling eval_recorder(score, output, eval_input)
  - eval_test_run_id session fixture — deterministic run_id across retries within one session
  - _record_eval_row helper — writes EvalType.ACCURACY rows conditionally on eval_db is not None
  - pytest_runtest_makereport hookwrapper — fires after every test call, delegates to the helper
  - Live-write proof against ai.agno_eval_runs on the deployed VPS
affects: [plan 12-03 verification, pre-commit eval router (untouched — verified by collection regression check)]

tech-stack:
  added: []
  patterns:
    - pytest hookwrapper for post-test row writes — minimal coupling to existing test cases (they opt in via fixture)
    - Triple-status taxonomy for OBS-01 suite writes: ok / duplicate (IntegrityError) / error (anything else)
    - Schema-by-copy: log line shape mirrored from agentos.eval_recorder rather than imported (avoids prod ← test infra coupling)

key-files:
  created:
    - tests/unit/test_eval_suite_hook.py
    - tests/integration/test_eval_suite_surface.py
    - .planning/phases/12-evals-surface-activation/evidence/12-02-live-2026-05-23.md
  modified:
    - evals/conftest.py

key-decisions:
  - "D-09: pytest_runtest_makereport in evals/conftest.py writes EvalType.ACCURACY rows per parametrized case"
  - "D-10: writes happen only when eval_db is not None — offline / pre-commit runs unaffected"
  - "D-11: baselines/*.json + pre-commit eval router untouched — 48 evals still collect identically"
  - "D-13: three plans (12-01 recorder, 12-02 suite hook, 12-03 verification)"
  - "D-14 + D-15: OBS-01 schema reused by copy, not import — single-source guidance from CONTEXT"

patterns-established:
  - "Opt-in suite recording: tests add eval_recorder + eval_db fixtures to enable DB writes; tests without those fixtures stay no-ops"
  - "Baseline-aware hook: makereport bypasses the write entirely under --write-baseline / --update-baseline so baseline scoring stays the single source of truth"

requirements-completed: [EVAL-02, OBS-01]

duration: 18min
completed: 2026-05-23
---

# Phase 12-02: EVAL-02 Suite Write Hook

**The 48-case eval suite can now write `EvalType.ACCURACY` rows to `ai.agno_eval_runs` via a pytest hook, conditionally on `POSTGRES_DSN_SESSIONS` — proven end-to-end against the deployed VPS Postgres.**

## What Shipped

| Artifact | Purpose |
|----------|---------|
| `evals/conftest.py` (additive) | New fixtures `eval_test_run_id`, `eval_recorder`; new helpers `_emit_obs01`, `_record_eval_row`; new `pytest_runtest_makereport` hookwrapper. All under leading-underscore module names so existing fixtures (`eval_db`, `judge_model`, `write_baseline`, `update_baseline`) are completely untouched. |
| `tests/unit/test_eval_suite_hook.py` | Two tests locking the helper contract: `test_hook_swallows_duplicate` (IntegrityError → status=duplicate log) and `test_hook_skips_when_db_none` (no DB → no log line, no call). |
| `tests/integration/test_eval_suite_surface.py` | One `@pytest.mark.live` test writing a `(EvalType.ACCURACY, run_id, "integration-test")` row through `PostgresDb`, verifying via raw SQL, then cleaning up. Skips when DSN is unset. |
| `.planning/phases/12-evals-surface-activation/evidence/12-02-live-2026-05-23.md` | Captures the inline VPS execution evidence — `LIVE_TEST_PASSED` confirmed. |

## Test Status

```
# Local unit tests
PYTHONPATH=. .venv/bin/pytest tests/unit/test_eval_suite_hook.py -q
2 passed in 0.46s

# Local evals collection (regression guard for D-11)
PYTHONPATH=. .venv/bin/pytest evals/ --collect-only -q
48 tests collected in 0.01s
```

## Live Verification

The local pytest harness for the live test (`tests/integration/test_eval_suite_surface.py -m live`) was not run on this Mac because:

- `POSTGRES_DSN_SESSIONS` is not exported in the local shell and not in `.env` (the DB lives on the VPS).
- The VPS deployment at `/opt/ultra-agents-brain` is not a git checkout — `tests/integration/` is absent there.

Equivalent end-to-end behaviour was exercised via `ssh root@31.97.130.253 ... .venv/bin/python - << PYEOF` running the same `EvalRunRecord` write → `SELECT` → `DELETE` round trip. Output:

```
OK: row found — run_id=int-c4297d8a-0be0-4eca-b90c-bcb9d6c940c4, eval_type=accuracy, agent_id=integration-test
OK: cleaned up 1 row(s)
LIVE_TEST_PASSED
```

Full evidence in `evidence/12-02-live-2026-05-23.md`.

## Threat Mitigations Verified

| Threat | Mitigation status |
|--------|-------------------|
| T-12-04: pre-commit eval router breaks | LOCKED — `pytest evals/ --collect-only` still lists 48 tests after the change. All new imports are inside the new fixtures, not at module top, so the offline path stays import-clean. |
| T-12-05: pytest retry triggers UniqueViolation | LOCKED — `test_hook_swallows_duplicate` reproduces the IntegrityError path; helper swallows it and emits `status=duplicate`. |
| T-12-06: developer's local run pollutes VPS DB | MITIGATED — `eval_db` returns None when `POSTGRES_DSN_SESSIONS` is unset (existing fixture). `test_hook_skips_when_db_none` locks the early-return path. |
| T-12-07: same nodeid double-write | RESOLVED — same nodeid → same run_id → IntegrityError → swallowed (first write wins; F7 behaviour). |

## Self-Check: PASSED

- ✅ All 3 tasks executed and committed atomically (RED unit + integration → GREEN conftest extension → live VPS proof)
- ✅ 2/2 unit tests passing
- ✅ Integration test collects (`1 test collected`); skipped without DSN as designed
- ✅ Live VPS roundtrip wrote + verified + cleaned up one accuracy row in `ai.agno_eval_runs`
- ✅ `grep -q "EvalType.ACCURACY" evals/conftest.py` succeeds
- ✅ `grep -q "IntegrityError" evals/conftest.py` succeeds
- ✅ `grep -q "ultra-brain-main" evals/conftest.py` empty (db_id read from instance, not hardcoded)
- ✅ 48 evals collect identically — `evals/baselines/*.json` flow untouched

## Handoff to Plan 12-03

The infrastructure is in place. Plan 12-03 covers the operator-driven verification:

1. Redeploy `uab-brain.service` on the VPS so `agentos/app.py` picks up the InstrumentedEvalRecorder wiring from plan 12-01.
2. Hit `POST /agents/chat/runs` once → expect 1 row with `eval_type='agent_as_judge'` in `ai.agno_eval_runs` and one `OBS-01 eval write:` line in `journalctl -u uab-brain.service`.
3. Run the full 48-case suite with `POSTGRES_DSN_SESSIONS=... pytest evals/ -q` → expect ≥1 row per case with `eval_type='accuracy'` (the count depends on how many existing cases adopt the `eval_recorder` fixture in plan 12-03; the infrastructure is non-breaking for cases that don't).
4. Confirm both surfaces appear in the os.agno.com Evals dashboard.

## Commits in This Plan

| SHA | Subject |
|-----|---------|
| `1b98c79` | test(12-02): RED tests for EVAL-02 suite hook + live surface |
| `b718bd4` | feat(12-02): EVAL-02 suite write hook in evals/conftest.py |
| (this commit) | docs(12-02): SUMMARY + live evidence |
