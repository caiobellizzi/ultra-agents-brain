---
phase: 13-knowledge-surface-activation
plan: 02
status: complete
shipped_at: 2026-05-23
requirements: [KNOW-02, OBS-01]
---

# Plan 13-02 — InstrumentedKnowledge (read-path observability)

## What shipped

- **`agentos/instrumented_knowledge.py`** — new file. Defines
  `class InstrumentedKnowledge(Knowledge)` with overrides for `search()` and
  `asearch()`. Each call:
  - Times the underlying `super().search(...)` / `super().asearch(...)` call.
  - Bumps `access_count` once per **unique** `content_id` via
    `contents_db.get_knowledge_content()` + `upsert_knowledge_content()`.
    Async path off-threads the sync DB call via `asyncio.to_thread(...)`.
  - Emits one structured OBS-01 log line on the `agentos.knowledge` logger
    with the full access schema (`path`, `agent_id`, `db_id`, `op='search'`,
    `query` truncated to 200 chars, `hit_count`, `latency_ms`, `status`, `row_id`).
  - Log-and-swallows exceptions in the underlying search → returns `[]` so a
    flaky vector DB never crashes an agent reply (CONTEXT threat model).
- **`agentos/knowledge.py`** — one-line wire change: the success branch of
  `make_knowledge()` now returns `InstrumentedKnowledge(...)` instead of
  bare `Knowledge(...)`. Stub-fallback path (no DSN) unchanged.
- **`tests/unit/test_instrumented_knowledge.py`** — 7 unit tests. All green.
- **`tests/integration/test_instrumented_knowledge_live.py`** — 1
  `@pytest.mark.live` end-to-end test. Skips without DSNs.
- **`tests/conftest.py`** — `live_postgres_dsn_knowledge` +
  `live_postgres_dsn_sessions` fixtures (pytest.skip when unset).

## Tests

```
PYTHONPATH=. pytest tests/unit/test_instrumented_knowledge.py tests/unit/test_knowledge_reindex.py -q
............... [100%]
15 passed in 10.36s
```

7 new tests:
- `test_subclass_relationship` (R-07)
- `test_search_subclass_returns_documents` (D-03 happy path)
- `test_search_bumps_access_count_per_unique_hit` (D-03 + R-05 dedup)
- `test_search_swallows_exception_and_returns_empty` (D-03 log-and-swallow)
- `test_search_emits_obs01_log` (D-05 access schema, 200-char truncation)
- `test_asearch_emits_log_and_bumps_access_count` (D-03c sync+async parity)
- `test_make_knowledge_returns_instrumented` (R-07 wiring)

Live test verified to skip cleanly under `pytest -m live` without DSNs.

## Full-suite snapshot

`pytest tests/ -q -m "not live"` → **91 passed, 4 failed, 4 deselected**.
The 4 failures are the same pre-existing failures noted in 13-01 SUMMARY
(curator/research agent model-tier mismatches in `test_agentos.py` + 2 telegram
routing tests). Confirmed unchanged by 13-02 via `git stash` baseline.

## Deviations from PLAN

- **None substantive.** The implementation matches the plan's contract surface
  exactly. The live test handles `contents_db.get_knowledge_contents()`
  returning either a plain list or `(list, count)` tuple (Agno's real return
  shape) for forward compatibility.

## Requirements coverage

- ✅ **KNOW-02** — RAG-hit visible: every search bumps `access_count` per
  unique `content_id`; the AgentOS UI Knowledge tab will render bumping values
  as agent traffic flows (verified end-to-end by 13-03 once deployed).
- ✅ **OBS-01 (access path)** — structured INFO/ERROR log line per search call,
  with `agent_id=null` (ContextVar threading deferred per R-01).

## Owed by phase 13 (next plan)

- **13-03:** deploy to VPS, run reindex, hit AgentOS UI/curl `/knowledge/config`
  and `/knowledge/content`, confirm Available IDs becomes non-empty and search
  bumps `access_count` live. Flips Phase 13 status to Complete in ROADMAP.

## Key files

- `agentos/instrumented_knowledge.py` (+167 / new)
- `agentos/knowledge.py` (+2 / -2; just the import + class-name swap)
- `tests/unit/test_instrumented_knowledge.py` (+205 / new)
- `tests/integration/test_instrumented_knowledge_live.py` (+121 / new)
- `tests/conftest.py` (+20 / extending)

## Commits

```
git log --oneline -5
```

1. `test(13-02): RED — 7 unit tests for InstrumentedKnowledge`
2. `feat(13-02): GREEN — InstrumentedKnowledge wrapper + wire make_knowledge`
3. `test(13-02): live integration test + DSN fixtures (skip without env vars)`
4. `docs(13-02): SUMMARY.md` (this commit)
