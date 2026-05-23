---
phase: 13-knowledge-surface-activation
plan: 01
status: complete
shipped_at: 2026-05-23
requirements: [KNOW-01, KNOW-03, OBS-01]
---

# Plan 13-01 — Knowledge write path (reindex + make_knowledge wiring)

## What shipped

- **`agentos/knowledge.py`** rewritten end-to-end.
  - `make_knowledge()` now returns `Knowledge(name="ultra-brain-vault", vector_db=PgVector(...), contents_db=POSTGRES_DB)` — the **actual** RC-knowledge-not-registered fix. Without `name` + `contents_db`, AgentOS's `/knowledge/config` Available IDs stayed empty regardless of vault content.
  - `reindex(vault_path, knowledge) -> ReindexSummary` — pure, testable function. Walks `vault_path/**/*.md`, computes SHA-256 of file bytes, skips files whose recorded `metadata.file_sha256` matches, otherwise calls `Knowledge.insert(path=..., name=rel_path, metadata={file_sha256, rel_path, size, indexed_at_ms}, upsert=True)`. Per-file `try/except` keeps a bad file from aborting the whole run.
  - `cli_main(argv)` — `python -m agentos.knowledge --reindex` entry point. Prints `[indexed]/[skipped]/[error]` per file and a final `Indexed N files (M skipped, K errors) in Xs` summary. Exit 0 iff `errors == 0`.
  - Stub fallback (missing DSN or PgVector init failure) emits one WARNING log line on `agentos.knowledge` with structured JSON payload — no more silent stubs.
  - OBS-01 structured log line per file action (`indexed`/`skipped`/`error`) with all required fields: `path`, `agent_id`, `db_id`, `op`, `rel_path`, `sha256`, `action`, `content_bytes`, `latency_ms`, `status`, `row_id`.
- **`agentos/db.py`** — added module-level `POSTGRES_DB` singleton (PostgresDb id=`ultra-brain-main`, or `None` when DSN unset / import fails). This is the shared `contents_db` instance.
- **`agentos/app.py`** — `kb = make_knowledge()` replaces the `vault = VaultKnowledge(); vault.load(); kb = vault.knowledge` block. Removed `VaultKnowledge` import. The `AgentOS(knowledge=[kb], ...)` line and agent factory calls are unchanged.
- **`tests/conftest.py`** — new file. Provides `tmp_vault` fixture (creates empty vault dir + sets `VAULT_PATH`) and stamps `LITELLM_MASTER_KEY` for tests that need it.
- **`tests/unit/test_knowledge_reindex.py`** — new file. 8 unit tests lock D-01..D-05 + R-03/R-04. All green.
- **`tests/test_agentos.py`** — `TestKnowledgeImportable` rewritten for the new surface (`make_knowledge` + `ReindexSummary` + `reindex` stub-fallback shape).

## Tests

```
PYTHONPATH=. .venv/bin/pytest tests/unit/ -q
......................... [100%]
25 passed in 9.58s
```

8 new tests in `tests/unit/test_knowledge_reindex.py` all green:
- `test_make_knowledge_wires_contents_db_and_name` (D-01 / R-03)
- `test_stub_fallback_emits_warning` (D-04)
- `test_reindex_calls_insert_per_file` (D-01)
- `test_reindex_skips_unchanged_files` (D-02 / R-04)
- `test_reindex_continues_on_per_file_error` (D-01c)
- `test_reindex_twice_no_duplicate_rows` (D-02c / KNOW-03)
- `test_reindex_emits_obs01_log_per_file` (D-05)
- `test_reindex_cli_summary` (D-01b)

## Deviations from PLAN

1. **Added `POSTGRES_DB` to `agentos/db.py`** (5th file outside `<files_modified>`).
   - Reason: the plan's acceptance criterion required `make_knowledge()` to import `POSTGRES_DB` from `agentos.db`, but `agentos/db.py` did not previously export that symbol. Constructing PostgresDb inline inside `make_knowledge()` would create a second instance disjoint from `app.py`'s `db`, defeating the "shared instance" purpose called out in R-03.
   - The PostgresDb constructor is wrapped in `try/except` so local/test environments (no `psycopg2`) can still import `agentos.db` cleanly; `POSTGRES_DB` is `None` in that case and the stub-fallback path in `make_knowledge()` handles it.
   - `app.py` still constructs its own `db` (sessions PostgresDb-or-SqliteDb selector) — phase 14+ can consolidate by reusing `POSTGRES_DB` from `db.py`.

2. **Pre-existing test failures left untouched.** Four failures predate plan 13-01:
   - `tests/test_agentos.py::TestAgentsImportable::test_curator_agent_has_memory_and_output_schema`
   - `tests/test_agentos.py::TestAgentsImportable::test_research_agent_make_has_orchestrator_model_and_schema`
   - `tests/test_telegram_adapter.py::TestRoutingLogic::test_plain_text_routes_to_supervisor`
   - `tests/test_telegram_adapter.py::TestRoutingLogic::test_unknown_command_falls_back_to_supervisor`

   Confirmed via `git stash` baseline comparison — same 4 fail without 13-01 changes. Out of scope for this plan.

3. **Sentinel reindex on stub-fallback.** When `knowledge.vector_db is None`, `reindex()` logs an ERROR (`status="reindex-unavailable"`) and returns `ReindexSummary(0, 0, 0, 0, 0.0)` instead of attempting inserts. This matches CONTEXT D-04's "loud failure" intent.

## Requirements coverage

- ✅ **KNOW-01** — vault content writes land in `ai.vault` (vector_db) + `ai.agno_knowledge` (contents_db) once the VPS reindex runs (verification owned by 13-03).
- ✅ **KNOW-03** — idempotency via `upsert=True` + sha256-skip; locked by `test_reindex_twice_no_duplicate_rows`.
- ✅ **DIAG-BL-05** — tables auto-create on first `Knowledge.insert()` per Agno R-02 (verified at 13-03).
- ✅ **DIAG-BL-06** — stub fallback is loud (WARNING log), no more silent empty Knowledge.
- ✅ **OBS-01 (write path)** — one structured log line per file action with the full schema.

## Owed by phase 13 (next plans)

- **13-02:** InstrumentedKnowledge subclass for read-path observability (KNOW-02 + OBS-01 access path).
- **13-03:** Deploy + UI verification — run `python -m agentos.knowledge --reindex` on VPS, confirm `/knowledge/config` Available IDs becomes non-empty, the Knowledge tab renders rows, search returns hits.

## Key files

- `agentos/knowledge.py` (+248 / -45)
- `agentos/db.py` (+22 / -0)
- `agentos/app.py` (+3 / -6)
- `tests/conftest.py` (+18 / new)
- `tests/unit/test_knowledge_reindex.py` (+274 / new)
- `tests/test_agentos.py` (+18 / -27)

## Commits

```
git log --oneline --all --grep="13-01" --since="1 hour ago"
```

1. `test(13-01): RED — 8 unit tests for reindex + make_knowledge wiring`
2. `feat(13-01): GREEN — rewrite knowledge.py with reindex + make_knowledge wiring`
3. `feat(13-01): wire app.py to make_knowledge() + update legacy tests`
4. `docs(13-01): SUMMARY.md` (this commit)
