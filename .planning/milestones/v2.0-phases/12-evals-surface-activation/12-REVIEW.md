---
phase: 12-evals-surface-activation
status: clean
review_depth: standard
reviewed_at: 2026-05-24
reviewed_files:
  - agentos/eval_recorder.py
  - agentos/eval_rubrics.py
  - agentos/eval_live_policy.py
  - agentos/live_judge.py
  - agentos/__main__.py
  - evals/conftest.py
  - evals/test_chat.py
  - evals/test_curator.py
  - evals/test_ingest.py
  - evals/test_query.py
  - evals/test_research.py
  - evals/test_supervisor.py
  - tests/unit/test_eval_recorder.py
  - tests/unit/test_eval_suite_hook.py
  - tests/unit/test_eval_live_policy.py
  - tests/unit/test_live_judge.py
---

# Phase 12 Code Review

## Verdict

Clean after one in-scope fix.

## Findings

### Fixed During Review

| Severity | File | Finding | Fix |
|----------|------|---------|-----|
| Warning | `agentos/eval_recorder.py` | Wrapped agent exceptions were recorded with `eval_data.status="ok"` in the instance wrapper, and class-level patched paths skipped exception rows. This contradicted the plan's `ok`/`error` live parent status contract. | `4c0c417` records exception paths with `error=exc` and adds `test_wrap_marks_agent_exception_as_error_status`. |

### Open Findings

None.

## Verification

- `PYTHONPATH=. .venv/bin/pytest tests/unit/test_eval_recorder.py -q` - passed, 9 tests.
- `PYTHONPATH=. .venv/bin/pytest tests/unit/test_eval_recorder.py tests/unit/test_eval_suite_hook.py tests/unit/test_eval_live_policy.py tests/unit/test_live_judge.py -q` - passed, 20 tests.

## Residual Risk

`make test` still has out-of-scope failures documented in `deferred-items.md`; those are not caused by the Phase 12 eval-row changes.
