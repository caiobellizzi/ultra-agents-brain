---
phase: 07-wave-5-evals
plan: "07-03"
subsystem: testing
tags: [pytest, pre-commit, evals, baselines, shell]

requires:
  - phase: 07-02
    provides: eval test cases for all 6 agents (chat, query, research, ingest, curator, supervisor)

provides:
  - evals/baselines/accuracy_baseline.json — stub accuracy baselines with regeneration instructions
  - evals/baselines/performance_baseline.json — stub performance baselines with thresholds
  - tools/precommit_eval_router.sh — maps staged agent files to scoped smoke eval runs
  - .pre-commit-config.yaml — wires router as pre-commit hook
  - evals/conftest.py augmented with --write-baseline / --update-baseline CLI flags

affects: [wave-5-evals, pre-commit, ci]

tech-stack:
  added: []
  patterns:
    - "Pre-commit router pattern: staged file -> scoped pytest target (zero API cost for smoke)"
    - "Stub baseline pattern: placeholder JSONs committed with _note field and regeneration command"
    - "Baseline R/W helpers: load_baseline/save_baseline in conftest.py for test use"

key-files:
  created:
    - evals/baselines/accuracy_baseline.json
    - evals/baselines/performance_baseline.json
    - tools/precommit_eval_router.sh
    - .pre-commit-config.yaml
  modified:
    - evals/conftest.py

key-decisions:
  - "Run only smoke tests in pre-commit hook (zero API cost, <=15s per agent)"
  - "Stub baselines with avg_score=0.0 as placeholders; regenerate with EVAL_JUDGE_TIER=orchestrator pytest evals/ --write-baseline"
  - "EVALS_TO_RUN deduplication uses awk !seen[] to preserve insertion order"
  - "agentos/model.py, app.py, schemas.py trigger full evals/ suite (cross-cutting changes)"

patterns-established:
  - "Pre-commit scoping: case statement maps file paths to pytest targets"
  - "Baseline file format: JSON with _note/_generated_at metadata keys plus per-case score objects"

requirements-completed: []

duration: 8min
completed: 2026-05-21
---

# Phase 7 Plan 3: Baselines + Pre-commit Eval Router Summary

**Stub accuracy/performance baselines committed to evals/baselines/, pre-commit router script wiring staged agent files to scoped smoke evals in <=15s**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-21T02:06:00Z
- **Completed:** 2026-05-21T02:14:25Z
- **Tasks:** 5
- **Files modified:** 5

## Accomplishments

- `evals/conftest.py` extended with `--write-baseline` / `--update-baseline` pytest CLI flags plus `load_baseline` / `save_baseline` helpers
- Stub baselines committed to `evals/baselines/` — regenerate with `EVAL_JUDGE_TIER=orchestrator pytest evals/ --write-baseline`
- `tools/precommit_eval_router.sh` maps staged agent files to scoped smoke eval runs (zero API cost, <=15s per agent)
- `.pre-commit-config.yaml` wires the router as a `pre-commit` hook with `always_run: false`
- All 30 smoke tests continue to pass after conftest changes

## Task Commits

Each task was committed atomically:

1. **Tasks 1-5: baselines + router + conftest + pre-commit config** - `d0085d8` (test)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `evals/conftest.py` — added `pytest_addoption`, `write_baseline`/`update_baseline` fixtures, `load_baseline`/`save_baseline` helpers
- `evals/baselines/accuracy_baseline.json` — stub per-case accuracy scores with threshold 0.7
- `evals/baselines/performance_baseline.json` — stub per-agent timing thresholds
- `tools/precommit_eval_router.sh` — bash router: staged file -> scoped pytest smoke run
- `.pre-commit-config.yaml` — local hook wiring `tools/precommit_eval_router.sh`

## Decisions Made

- Smoke-only default for pre-commit (zero API cost): integration evals require explicit `EVAL_JUDGE_TIER=orchestrator pytest evals/`
- Stub baselines with `avg_score: 0.0` rather than no file — format is documented and importable immediately
- `awk '!seen[$0]++'` for dedup in router to preserve insertion order (vs `sort -u` which sorts alphabetically)
- Used `PYTHONPATH=. .venv/bin/pytest` in router (project convention, mirrors how pytest.ini is invoked)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `.venv/bin/pytest` is not present in the worktree (symlinked worktree shares code but not venv). Used `/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/.venv/bin/pytest` for verification only. The router script correctly references `.venv/bin/pytest` relative to the project root, which is where pre-commit runs it from.

## User Setup Required

To use the pre-commit hook: install `pre-commit` and run `pre-commit install` in the project root.

To regenerate real baselines (requires live LLM):
```bash
EVAL_JUDGE_TIER=orchestrator pytest evals/ --write-baseline
```

## Next Phase Readiness

- Wave 5 evals complete (07-01 scaffold, 07-02 test cases, 07-03 baselines + router)
- Pre-commit quality gate is wired and ready
- Baseline JSONs are stubs — regeneration with live LLM remains a manual step

---
*Phase: 07-wave-5-evals*
*Completed: 2026-05-21*

## Self-Check: PASSED

- `evals/baselines/accuracy_baseline.json` — FOUND
- `evals/baselines/performance_baseline.json` — FOUND
- `tools/precommit_eval_router.sh` — FOUND
- `.pre-commit-config.yaml` — FOUND
- `evals/conftest.py` modified with baseline flags — FOUND
- Commit `d0085d8` — FOUND (verified via git log)
- 30 smoke tests passing — VERIFIED
