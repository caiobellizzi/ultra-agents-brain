---
phase: "07-wave-5-evals"
plan: "07-02"
subsystem: "evals"
tags: ["evals", "testing", "datasets", "integration-stubs"]
dependency_graph:
  requires: ["07-01"]
  provides: ["eval-datasets", "vault-seed-fixture", "integration-test-stubs"]
  affects: ["evals/"]
tech_stack:
  added: []
  patterns: ["parametrized-integration-stubs", "eval-seed-fixture", "smoke-integration-split"]
key_files:
  created:
    - "evals/fixtures/__init__.py"
    - "evals/fixtures/eval_vault_seed.md"
  modified:
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
    - "pytest.ini"
decisions:
  - "Integration tests validate case structure only (not live agent calls) — marked @pytest.mark.integration and excluded from default test runs"
  - "curator_cases use expected_actions_non_empty=False as conservative default — vault is clean in eval env"
  - "pytest.ini updated to register integration mark alongside existing smoke mark"
metrics:
  duration: "209 seconds"
  completed: "2026-05-21"
  tasks_completed: 4
  files_created: 2
  files_modified: 13
---

# Phase 07 Plan 02: Eval Coverage + Vault Seed Fixture Summary

## One-liner

Filled 18 vault-aware eval cases across 6 datasets, created deterministic vault seed fixture, and added 18 `@integration` parametrized test stubs covering all 6 agents.

## What Was Built

### Task 1: Vault Seed Fixture

Created `evals/fixtures/eval_vault_seed.md` — a stable markdown note tagged `eval-seed`, `vector-db`, `testing` describing PgVector, hybrid search, and the `all-MiniLM-L6-v2` embedding model. This gives eval cases a deterministic vault target to reference in citation assertions.

### Task 2: Dataset Files (18 cases total)

All 6 dataset files replaced TODOs with real vault-aware cases:

| Dataset | Cases | Key assertions |
|---------|-------|----------------|
| `chat_cases.py` | 3 | `expected_text_contains` list, `expected_citations_have_tag`, `max_latency_seconds` |
| `query_cases.py` | 3 | `expected_answer_contains` list, `expected_citations_have_tag` (eval-seed for cases 1+2) |
| `ingest_cases.py` | 3 | `expected_note_path_prefix`, `expected_min_tags`, `max_latency_seconds` |
| `research_cases.py` | 3 | `expected_min_findings`, `expected_min_next_questions`, `max_latency_seconds` |
| `curator_cases.py` | 3 | `expected_actions_non_empty`, `expected_errors_empty`, `max_latency_seconds` |
| `supervisor_routing.py` | 3 | `expected_agent` maps to query/research/ingest for `/query`, `/research`, `/ingest` prefix inputs |

### Task 3: Integration Test Stubs (6 test files)

Each of the 6 test files received:
- Import of the corresponding dataset
- `@pytest.mark.integration` + `@pytest.mark.parametrize` test that validates case structure (not live agent calls)

`pytest.ini` updated to register `integration` mark:
```ini
[pytest]
markers =
    smoke: fast schema-level assertions, no LLM calls
    integration: full agent runs, requires live services
```

### Task 4: Smoke Test Verification

```
30 passed, 18 deselected in 0.04s  (smoke run)
30 passed, 18 deselected in 0.01s  (not integration run)
```

Smoke tests remain exactly 30 passing with zero API calls.

## Deviations from Plan

None — plan executed exactly as specified. The user-provided task description took precedence over the plan frontmatter's higher-level intent. Integration tests validate case structure rather than making live agent calls, which matches the "structured for future live-agent runs" directive.

## Commits

| Hash | Message |
|------|---------|
| 102cd2e | test(evals): fill 18 eval cases, add vault seed fixture, integration test stubs |

## Known Stubs

The `@pytest.mark.integration` tests are intentional stubs — they validate dataset structure only and do not make live agent calls. Future work (plan 07-03 or later) should wire real agent calls into these tests when live services are available.

## Self-Check: PASSED

- evals/fixtures/eval_vault_seed.md: FOUND
- evals/fixtures/__init__.py: FOUND
- All 6 dataset files: FOUND
- Commit 102cd2e: FOUND
- 30 smoke tests passing
