---
phase: 12-evals-surface-activation
plan: 04
subsystem: evals
tags: [agno, evals, postgres, live-judge, pytest]

requires:
  - phase: 12-evals-surface-activation
    provides: Phase 12 eval recorder and suite write path from plans 12-01 through 12-03
provides:
  - Correct live parent eval rows using EvalType.PERFORMANCE
  - Deterministic suite accuracy run IDs
  - Optional async live judge worker producing child agent_as_judge rows
  - Policy and rubric helpers for privacy-gated live judging
affects: [agentos, evals, observability, maintenance]

tech-stack:
  added: []
  patterns:
    - Parent performance row plus child agent_as_judge row linked by eval_data.parent_run_id
    - Deterministic eval-suite identity from git HEAD plus dirty hash
    - Optional worker CLI behind python -m agentos live-judge

key-files:
  created:
    - agentos/eval_rubrics.py
    - agentos/eval_live_policy.py
    - agentos/live_judge.py
    - tests/unit/test_eval_live_policy.py
    - tests/unit/test_live_judge.py
    - .planning/phases/12-evals-surface-activation/deferred-items.md
  modified:
    - agentos/eval_recorder.py
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
    - docs/MAINTENANCE.md

key-decisions:
  - "Unjudged live rows are performance telemetry rows, not agent-as-judge rows."
  - "Live judging remains opt-in, sampled, privacy-gated, retry-limited, and asynchronous."
  - "Historical Untitled Evaluation rows are left untouched."

patterns-established:
  - "Live eval judging is represented as child rows linked to immutable parent run telemetry."
  - "Eval-suite rows use stable run IDs so duplicate writes are swallowed and logged."

requirements-completed: [EVAL-01, EVAL-02, EVAL-03, OBS-01]

duration: 22 min
completed: 2026-05-24
---

# Phase 12 Plan 04: Eval Row Semantics and Live Judge Worker Summary

**Live eval telemetry now writes dashboard-readable performance rows, deterministic suite accuracy rows, and optional child judge rows behind a privacy-gated worker**

## Performance

- **Duration:** 22 min implementation window, plus verification and close-out
- **Started:** 2026-05-24T16:33:56-03:00
- **Completed:** 2026-05-24T16:56:00-03:00
- **Tasks:** 6/6 complete
- **Files modified:** 18

## Accomplishments

- Corrected live recorder semantics from `agent_as_judge` to `performance`, with `name=live:<agent_id>` and `evaluated_component_name=<agent_id>`.
- Preserved suite scoring as `accuracy` rows with deterministic `suite:<agent_id>:<case_id>:<git_identity>` run IDs and duplicate-swallow logging.
- Added live judge policy/rubric helpers and a `python -m agentos live-judge` worker that writes linked child `agent_as_judge` rows.
- Documented operator row meanings, env vars, worker commands, privacy gates, and the non-migration stance for historical rows.

## Task Commits

1. **Task 1: Tests for corrected semantics** - `eef8578` (`test`)
2. **Task 2: Live recorder writes performance rows** - `2a7bd5a` (`feat`)
3. **Task 3: Deterministic suite identities and full suite adoption** - `b01c540` (`feat`)
4. **Task 4: Shared rubrics, policy helpers, and privacy gates** - `0a28c14` (`fix`)
5. **Task 5: Live judge worker and CLI** - `a3b1cee` (`feat`)
6. **Task 6: Docs and verification** - `4245cc8` (`docs`)
7. **Code review fix: Failed live-run status** - `4c0c417` (`fix`)

## Files Created/Modified

- `agentos/eval_recorder.py` - Builds unjudged live rows as `EvalType.PERFORMANCE` and marks sampled eligible rows pending for judging.
- `agentos/eval_rubrics.py` - Defines live rubrics for chat, query, and ingest.
- `agentos/eval_live_policy.py` - Parses live-judge env policy, sampling, privacy checks, and score normalization.
- `agentos/live_judge.py` - Discovers pending parent rows, applies policy gates, writes child judge rows, and updates parent judge status metadata.
- `agentos/__main__.py` - Adds `live-judge` CLI while keeping server startup as the default.
- `evals/conftest.py` and `evals/test_*.py` - Use deterministic suite identities and call `eval_recorder` across all six eval case files.
- `docs/MAINTENANCE.md` - Documents row meanings, env vars, worker commands, privacy behavior, and historical row handling.

## Decisions Made

- Live parent rows stay metadata-only and keep `score=None`; quality judgments live in separate child rows.
- Suite dirty identity only considers eval-relevant paths: `agentos/`, `evals/`, `tests/`, `ultra_brain/`, and `skills/`.
- The worker uses an isolated SQL helper for parent status updates until Agno exposes an eval-run update API.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

`make test` still fails after an elevated rerun, but the remaining failures are outside Plan 12-04 scope and are recorded in `deferred-items.md`:

- Memory surface SLA: row appears after ~17s vs a 5s test budget.
- Existing agent factory expectations for curator memory and research model routing.
- Existing Telegram adapter routing expectations for plain text and unknown commands.

## Verification

- `PYTHONPATH=. .venv/bin/pytest tests/unit/test_eval_recorder.py tests/unit/test_eval_suite_hook.py tests/unit/test_eval_live_policy.py tests/unit/test_live_judge.py -q` - passed, 20 tests after code-review fix.
- `PYTHONPATH=. .venv/bin/pytest evals/ --collect-only -q` - passed, 48 tests collected.
- `PYTHONPATH=. .venv/bin/pytest evals/ -q -m "not live"` - passed, 48 tests.
- `PYTHONPATH=. .venv/bin/python -m py_compile agentos/live_judge.py agentos/__main__.py` - passed.
- `PYTHONPATH=. .venv/bin/python -m agentos live-judge --help` - passed without starting the server.
- `make eval-smoke` - passed, 30 smoke tests.
- `make test` - failed on five out-of-scope items listed above.

## User Setup Required

None - live judging remains disabled by default and is configured via documented environment variables when the operator opts in.

## Next Phase Readiness

Phase 12 eval-row semantics are corrected for new rows. The verifier should treat historical `Untitled Evaluation` rows as intentionally untouched and should account for the out-of-scope `make test` failures separately from the eval path.

## Self-Check: PASSED

- Created files exist: `agentos/eval_rubrics.py`, `agentos/eval_live_policy.py`, `agentos/live_judge.py`, `tests/unit/test_eval_live_policy.py`, `tests/unit/test_live_judge.py`.
- Plan commits exist in git history: `eef8578`, `2a7bd5a`, `b01c540`, `0a28c14`, `a3b1cee`, `4245cc8`, `4c0c417`.
- Focused plan verification and eval smoke gates passed.
- Remaining `make test` failures are documented as out-of-scope in `deferred-items.md`.

---
*Phase: 12-evals-surface-activation*
*Completed: 2026-05-24*
