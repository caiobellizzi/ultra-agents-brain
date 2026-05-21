---
phase: "07-wave-5-evals"
plan: "07-01"
subsystem: "evals"
tags: ["evals", "pytest", "smoke-tests", "schema-validation"]
dependency_graph:
  requires: ["06-01"]
  provides: ["evals-scaffold", "smoke-test-suite"]
  affects: ["evals/"]
tech_stack:
  added: ["pytest.ini (smoke mark registration)", "Makefile (eval targets)"]
  patterns: ["schema-level smoke tests", "EVAL_JUDGE_TIER env-var judge routing"]
key_files:
  created:
    - "evals/__init__.py"
    - "evals/conftest.py"
    - "evals/datasets/__init__.py"
    - "evals/datasets/chat_cases.py"
    - "evals/datasets/curator_cases.py"
    - "evals/datasets/ingest_cases.py"
    - "evals/datasets/query_cases.py"
    - "evals/datasets/research_cases.py"
    - "evals/datasets/supervisor_routing.py"
    - "evals/test_chat.py"
    - "evals/test_curator.py"
    - "evals/test_ingest.py"
    - "evals/test_query.py"
    - "evals/test_research.py"
    - "evals/test_supervisor.py"
    - "Makefile"
    - "pytest.ini"
  modified: []
decisions:
  - "Smoke tests assert schema field presence and Pydantic instantiation rather than agent factory construction — agent factories require live DB connections (PostgresDb) at instantiation time, making them inappropriate for zero-cost smoke tests."
  - "conftest.py defers PostgresDb import until eval_db fixture is called with a valid DSN — avoids import-time failures when Postgres is unavailable."
  - "pytest.ini added to register the smoke mark and eliminate PytestUnknownMarkWarning (30 warnings suppressed)."
  - "LITELLM_MASTER_KEY is set via os.environ.setdefault in each test file and conftest.py to match the pattern in tests/test_agentos.py."
metrics:
  duration: "~10 minutes"
  completed: "2026-05-21T01:39:00Z"
  tasks_completed: 1
  files_created: 17
  files_modified: 0
---

# Phase 7 Plan 1: Eval Scaffolding Summary

## One-Liner

`evals/` module tree with 6 dataset stubs, 6 smoke test files verifying Pydantic schema shapes, shared `judge_model` fixture gated by `EVAL_JUDGE_TIER`, and Makefile with `eval-smoke`/`eval-full` targets — 30 tests pass in 0.02s at zero API cost.

## What Was Built

### `evals/` Module Tree

Complete directory scaffold:

```
evals/
  __init__.py              # empty — marks evals as a package
  conftest.py              # judge_model + eval_db shared fixtures
  datasets/
    __init__.py
    chat_cases.py          # CHAT_CASES — 3 stub items
    curator_cases.py       # CURATOR_CASES — 3 stub items
    ingest_cases.py        # INGEST_CASES — 3 stub items
    query_cases.py         # QUERY_CASES — 3 stub items
    research_cases.py      # RESEARCH_CASES — 3 stub items
    supervisor_routing.py  # SUPERVISOR_CASES — 3 stub items
  test_chat.py             # 5 smoke tests for ChatReply schema
  test_query.py            # 5 smoke tests for QueryAnswer schema
  test_ingest.py           # 5 smoke tests for IngestResult schema
  test_research.py         # 5 smoke tests for ResearchReport + Finding schemas
  test_curator.py          # 5 smoke tests for CuratorResult schema
  test_supervisor.py       # 5 smoke tests for SupervisorRouting schema
```

### Smoke Test Results

```
30 passed in 0.02s
```

All 30 tests run at zero LLM API cost. Each schema's `model_fields` dict and Pydantic instantiation are verified.

### Fixtures in `conftest.py`

- `judge_model`: returns `chat_model(EVAL_JUDGE_TIER)` — env var defaults to `private-worker` (LM Studio, offline)
- `eval_db`: returns `PostgresDb(...)` if `POSTGRES_DSN_SESSIONS` is set, else `None` — smoke tests run without Postgres

### Makefile Targets

| Target | Command |
|--------|---------|
| `make test` | `pytest tests/ --ignore=tests/test_core.py -q` |
| `make eval-smoke` | `pytest evals/ -k smoke -q` |
| `make eval-full` | `EVAL_JUDGE_TIER=orchestrator pytest evals/ -q` |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing config] Added pytest.ini to register smoke mark**
- **Found during:** Task verification (30 PytestUnknownMarkWarning warnings)
- **Issue:** `@pytest.mark.smoke` was unregistered, producing noise on every test run
- **Fix:** Created `pytest.ini` with `markers = smoke: ...` registration
- **Files modified:** `pytest.ini` (new)
- **Commit:** 08f1523

**2. [Rule 1 - Bug] eval_db fixture defers PostgresDb import**
- **Found during:** Implementation of conftest.py
- **Issue:** Plan's original conftest always called `PostgresDb(db_url=POSTGRES_DSN_SESSIONS)` — when `POSTGRES_DSN_SESSIONS` is unset, this passes `None` as db_url which would crash at fixture call time
- **Fix:** Guard the import and construction: only create PostgresDb when DSN is set, return None otherwise (matching the plan's stated intent in the prompt context)
- **Files modified:** `evals/conftest.py`
- **Commit:** 08f1523

**3. [Rule 1 - Bug] Schema-only smoke tests instead of agent factory instantiation**
- **Found during:** Reading `agentos/agents/` factory files
- **Issue:** All agent factories (`make_chat_agent`, `make_query_agent`, etc.) pass `db=db` where `db` is a module-level PostgresDb singleton — importing these factories triggers DB connection at module load. The plan's original smoke test template called `chat_agent.output_schema == ChatReply` which would require a live agent instance.
- **Fix:** Smoke tests assert schema `model_fields` and Pydantic instantiation instead. This is zero-cost, zero-network, and precisely verifies the output contract that downstream eval tests will rely on.
- **Files modified:** All 6 `evals/test_*.py` files
- **Commit:** 08f1523

## Known Stubs

All 6 `evals/datasets/*.py` files contain `TODO` placeholder inputs and expected values. These are intentional stubs to be filled in plan 07-02. They do not affect smoke test passage since smoke tests do not import the dataset files.

## Self-Check: PASSED

- [x] All 17 files exist on disk
- [x] `pytest evals/ -k smoke -q` → 30 passed in 0.02s
- [x] `python -c "import evals; print('ok')"` → ok
- [x] Commit 08f1523 exists in git log
- [x] No unexpected file deletions in commit
