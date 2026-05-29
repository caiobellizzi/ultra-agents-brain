# Phase 13 RESEARCH — Knowledge Surface Activation

**Date:** 2026-05-23
**Agno version in venv:** 2.6.7 (`.venv/lib/python3.13/site-packages/agno`)
**Source of all citations:** files under `.venv/lib/python3.13/site-packages/agno/`. Line numbers refer to that tree unless otherwise noted.

This document answers the 10 open items raised in `13-CONTEXT.md` so the planner can lock decisions without re-investigation.

---

## R-01. Agno 2.6.7 `Knowledge` API surface

### Insert
- **Primary insert method:** `Knowledge.insert(...)` — `knowledge/knowledge.py:91-156` (sync), `Knowledge.ainsert(...)` — `knowledge/knowledge.py:177-224` (async).
- Signature (sync):
  ```python
  def insert(self,
      name: Optional[str] = None,
      description: Optional[str] = None,
      path: Optional[str] = None,
      url: Optional[str] = None,
      text_content: Optional[str] = None,
      metadata: Optional[Dict[str, Any]] = None,
      topics: Optional[List[str]] = None,
      remote_content: Optional[RemoteContent] = None,
      reader: Optional[Reader] = None,
      include: Optional[List[str]] = None,
      exclude: Optional[List[str]] = None,
      upsert: bool = True,
      skip_if_exists: bool = False,
      auth: Optional[ContentAuth] = None,
  ) -> None
  ```
- `Knowledge.insert_many(contents: List[ContentDict])` also exists (`knowledge.py:356-355`); not needed for our per-file loop.
- ⚠ **CONTEXT.md uses `Knowledge.add_content()` — that name does NOT exist on the Knowledge class.** There is a *module-level* helper `add_content(...)` at `knowledge.py:3424`, but the canonical method on the Knowledge instance is `insert(...)`. Plan must use `knowledge.insert(...)`.

### Search
- `Knowledge.search(query, max_results=None, filters=None, search_type=None) -> List[Document]` — `knowledge/knowledge.py:508-547`.
- `Knowledge.asearch(query, max_results=None, filters=None, search_type=None) -> List[Document]` — `knowledge/knowledge.py:549-595`.
- Both wrap the inner `vector_db.search` / `vector_db.async_search` call in `try/except`, log `log_error(...)`, and return `[]` on exception. **Agents never see the exception** — they see an empty hit list.
- **Critical for OBS-01:** Because Agno swallows errors internally, our wrapper cannot rely on a Python exception to detect a search failure. The wrapper must time the call, count returned hits, and log `status:"ok"` always (latency_ms + hit_count tell the story).

### Other surface
- `Knowledge.get_content(...)`, `Knowledge.get_content_by_id(...)`, `Knowledge.remove_content_by_id(...)` and async variants — not needed in 13-01/13-02.
- `Knowledge.remove_vectors_by_metadata({"rel_path": ...})` — `knowledge.py:765` — useful in backlog "knowledge-gc on vault delete"; not in phase 13.

### Does `search()` receive `agent_id`?

**No.** Knowledge.search() is called by the agent's tool runtime with `(query, ...)` only — no agent identity is threaded through. Looking at `agno/agents/agent.py` references the agent invokes `knowledge.search(...)` directly. Three options to thread `agent_id`:

1. **`contextvars.ContextVar` set by the agent factory** — agent wraps each run in `agent_id_ctx.set(self.id)`; the wrapper reads it. Most idiomatic.
2. **Per-agent Knowledge subclasses** — each agent gets a Knowledge instance bound to its id. Wasteful (re-embeds elsewhere) and violates "single Knowledge" decision.
3. **Accept `agent_id=None` in OBS-01 logs for phase 13** — defer correlation to a future OBS-02 pass.

**Recommendation:** Option 3 (`agent_id=None`) for phase 13 — keeps scope tight. ContextVar can land in a follow-up; CONTEXT.md D-03 explicitly says "if passable via context."

---

## R-02. PgVector auto-migration (resolves DIAG-BL-05)

**Conclusion: auto-creates on first connect when defaults are kept. No explicit migration step required.**

Trace:
1. `Knowledge.__post_init__()` — `knowledge/knowledge.py:58-65`:
   ```python
   if self.vector_db and not self.vector_db.exists():
       self.vector_db.create()
   ```
   Runs unconditionally as long as `vector_db` is provided.

2. `PgVector.create()` — `vectordb/pgvector/pgvector.py:225-242`:
   - `CREATE EXTENSION IF NOT EXISTS vector;`
   - `CREATE SCHEMA IF NOT EXISTS ai;` (gated by `create_schema=True`, default).
   - `self.table.create(self.db_engine)` — emits the table DDL.

3. Table columns are defined at `vectordb/pgvector/pgvector.py:170-205` — includes `id`, `name`, `content_hash` (indexed), `content_id`, `meta_data JSONB`, plus the embedding vector. **All columns we need for dedup + filtering exist as first-class columns or in `meta_data` JSONB.**

4. `ai.agno_knowledge` (the contents table) is auto-created by `PostgresDb._get_or_create_table(table_type="knowledge", create_table_if_not_found=True)` — `db/postgres/postgres.py:486-491`. The first call to `contents_db.upsert_knowledge_content(...)` invokes `_get_table("knowledge", create_table_if_not_found=True)` → `db/postgres/postgres.py:2118` → creates the table if missing. Default `create_schema=True` (`db/postgres/postgres.py:84`).

5. Table schema for `ai.agno_knowledge` — `db/postgres/schemas.py:58-72` (KNOWLEDGE_TABLE_SCHEMA): `id (PK)`, `name`, `description`, `metadata (JSONB)`, `type`, `size`, `linked_to`, `access_count (BigInt)`, `status`, `status_message`, `created_at`, `updated_at`, `external_id`.

**Implication for phase 13:**
- No `psql` migration is needed.
- The fix for "RC-knowledge-not-registered" is purely application-side: `make_knowledge()` must pass `contents_db=PostgresDb(...)` so `ai.agno_knowledge` gets created on the first reindex run (R-03 explains why this matters for `/knowledge/config`).
- DIAG-BL-05 ("agno_knowledge DB has zero tables") closes when the first reindex executes — the table gets created by the upsert path during normal operation.

**One operational gotcha:** the DSN `POSTGRES_DSN_KNOWLEDGE` must point at a database where the `ai` schema can be created (CREATE permission). On the VPS the production DB user already owns `ai.*` from phase 11 (memory uses the same DSN convention) — verify before the first reindex.

---

## R-03. `/knowledge/config` Available IDs (resolves RC-knowledge-not-registered)

**Root cause of the empty `Available IDs: []`:** `make_knowledge()` does not pass `contents_db` to the `Knowledge(...)` constructor.

Trace:
- Router code path: `os/routers/knowledge/knowledge.py:115-118` calls `get_knowledge_instance(knowledge_instances, db_id, knowledge_id)`.
- `get_knowledge_instance` lives in `os/utils.py:350-399`. **Critical line 354:**
  ```python
  for knowledge in knowledge_instances:
      if not knowledge.contents_db:
          continue          # ← skipped entirely
  ```
- After filtering, the function builds Available IDs via `_generate_knowledge_id(name, contents_db.id, knowledge_table_name)` — `os/utils.py:315-325`:
  ```python
  id_seed = f"{db_id}:{table_name}:{name}"
  hash_hex = hashlib.sha256(id_seed.encode()).hexdigest()
  return f"{hash_hex[:8]}-{hash_hex[8:12]}-{hash_hex[12:16]}-{hash_hex[16:20]}-{hash_hex[20:32]}"
  ```

**What must be wired:**
1. `make_knowledge()` constructs `Knowledge(name="ultra-brain-vault", vector_db=PgVector(...), contents_db=PostgresDb(id="ultra-brain-main", db_url=POSTGRES_DSN_SESSIONS))`.
   - **Reuse the SAME `PostgresDb(id="ultra-brain-main")` instance** that phase 11 already wires up (D-04 of phase 11). Do **not** create a new PostgresDb — instance identity matters for shared `db_id`.
   - `name` is required; without it `_generate_knowledge_id` falls back to `f"knowledge_{contents_db.id}"`. We prefer the explicit name.
2. After reindex completes, `/knowledge/config` returns Available IDs containing a single UUID-shaped string derived from `("ultra-brain-main", "agno_knowledge", "ultra-brain-vault")`.
3. `/knowledge/content?db_id=ultra-brain-main` returns HTTP 200 with `data[]` populated from `ai.agno_knowledge` rows. The route is `os/routers/knowledge/knowledge.py:484-528` — it lists rows via `contents_db.get_knowledge_contents(...)`.

**Note on `contents_db` DSN:** AgentOS expects `contents_db.id == "ultra-brain-main"` (phase 11 lock). The DSN used to construct that PostgresDb in phase 11 is `POSTGRES_DSN_SESSIONS` (the same DB that holds memory/eval rows). PgVector uses a separate DSN (`POSTGRES_DSN_KNOWLEDGE`) for the embedding storage. **Two DSNs, one shared `db_id`** — this is the v1.5 pattern, do not break it.

---

## R-04. Hash storage choice (D-02a)

**Recommendation: Option 1 — store `file_sha256` in `ai.agno_knowledge.metadata` JSONB.** No side-table needed.

### Why Agno's native content_hash is NOT enough

`Knowledge._build_content_hash(content)` — `knowledge/knowledge.py:2209-2275` — for a path-input content, hashes the string `"{name}:{description}:{path}"`, **NOT the file bytes.** Two consequences:

1. **`skip_if_exists=True` would wrongly skip a file whose content changed** (path unchanged = hash unchanged = skipped). This breaks the use-case where the operator edits a vault note and reindexes.
2. **`upsert=True` re-embeds every file every run** — wasteful but row-count idempotent. PgVector's `upsert(content_hash, docs, metadata)` (`vectordb/pgvector/pgvector.py:425-440`) deletes existing rows for that hash then re-inserts. So **KNOW-03's "no duplicate rows" is natively satisfied by `upsert=True`**.

### Idempotency vs. cost-skip — two independent concerns

| Concern | Mechanism |
|---|---|
| **KNOW-03 row-count idempotency** | `upsert=True` (Agno default) — handled natively. Reindex twice → same row count. |
| **Cost-skip (avoid re-embedding unchanged files)** | Compute `sha256(file_bytes)` ourselves; check stored hash; skip the `insert()` call entirely if match. |

### Why Option 1 (metadata JSONB on `ai.agno_knowledge`)

- `ai.agno_knowledge.metadata` is already a JSONB column (`db/postgres/schemas.py:62`). No new schema.
- `Knowledge.insert(path=..., metadata={"file_sha256": "...", "rel_path": "..."})` writes the metadata via the `_load_from_path` → `_handle_vector_db_insert` flow; that metadata is then upserted into `ai.agno_knowledge` via `upsert_knowledge_content` (`db/postgres/postgres.py:2108-2210`, which maps the `metadata` field per `field_mapping` lines ~2138).
- Lookup before reindex: call `contents_db.get_knowledge_contents(...)` filtered by `name=rel_path` (we set `name=rel_path` explicitly to make this queryable). Compare `metadata.file_sha256` to the current file's sha256; skip insert if equal.
- ⚠ `get_knowledge_contents` returns ALL rows for the db_id — phase 13 vaults are small (low-thousands of `.md` files), so an in-memory dict keyed by `name` is acceptable. If the vault grows past ~50k files, revisit.

### Why NOT Option 2 (PgVector `vault.meta_data` JSONB)

- PgVector's `meta_data` is per-document-chunk, not per-file. One markdown file produces multiple chunk rows (chunking is enabled in the embedder default). Reading "is this file's sha256 in the store" would require an aggregation across chunks.
- `ai.agno_knowledge` is per-content-file (one row per `insert()` call) — exactly what we want.

### Why NOT Option 3 (side-table `ai.uab_knowledge_hashes`)

- Extra schema to migrate + maintain.
- Risk of drift vs Agno's row state (CONTEXT.md threat model already flags this).
- No benefit over Option 1 since Agno already gives us a JSONB metadata column on the per-file table.

### Locked decision for the planner

- Reindex passes `name=str(rel_path_from_vault_root)` and `metadata={"file_sha256": sha, "rel_path": str(rel_path), "size": bytes, "indexed_at_ms": epoch_ms}` to `Knowledge.insert(...)`.
- Reindex calls `contents_db.get_knowledge_contents(...)` once at the start, builds a `{name: metadata}` lookup, and skips `insert()` for files whose `metadata.file_sha256` matches the current file bytes.
- Use `upsert=True, skip_if_exists=False` (Agno defaults) on every `insert()` call — guarantees row-count idempotency for the "file changed" case.

---

## R-05. KNOW-02 RAG-hit surface (D-03b)

**Conclusion: Agno does NOT emit any access/hit event natively when `Knowledge.search()` runs.** No row is written. The `access_count` column on `ai.agno_knowledge` exists but is never incremented by Agno code.

Evidence:
- `Knowledge.search()` and `Knowledge.asearch()` — `knowledge.py:508-595` — do not touch `contents_db` at all. They only call `vector_db.search(...)`.
- `access_count` references in agno: `knowledge.py:2393` (initializer sets it to `0` on first row insert). No `+=` or `UPDATE access_count = access_count + 1` anywhere in the agno tree (verified by `grep -rn "access_count" agno/`).
- `/knowledge/search` route (`os/routers/knowledge/knowledge.py:770-877`) is a thin shim — calls `knowledge.asearch(...)` and returns results. Does NOT write a row.

### Path to make hits "visible in UI"

The os.agno.com Knowledge tab shows rows from `ai.agno_knowledge`. The columns it renders include `access_count`, `updated_at`, and `metadata` (verified by reading the React fetch contract via the `/knowledge/content` route response shape — `os/routers/knowledge/knowledge.py:484-528`, returns `KnowledgeRow.to_dict()`).

**Wrapper strategy for KNOW-02:**
1. After `super().search(query)` returns `List[Document]`, for each hit:
   - Read `doc.meta_data` to extract `content_id` (Agno writes the parent Content.id into each chunk's meta_data — verified in `vectordb/pgvector/pgvector.py:380-395` which sets `record["content_hash"]` and pulls `meta_data` from `Document.meta_data`).
   - `contents_db.get_knowledge_content(content_id)` → fetch current `KnowledgeRow`.
   - Bump `access_count` by 1, set `updated_at` to now.
   - Call `contents_db.upsert_knowledge_content(updated_row)`.
2. Emit OBS-01 `op:"search"` log line with `hit_count`, `latency_ms`, `query`.

**Cost of the per-hit upsert:** N=hit_count DB writes per search. With `max_results=10` default, that's up to 10 small UPDATEs per agent turn. Acceptable for the v1.5 traffic profile; revisit only if RAG QPS exceeds ~5/s on the VPS.

**De-dup safety:** if a single search returns the same content_id in multiple chunk hits (large file split across chunks), bump access_count once per *unique* content_id per search call (use a set).

**Fallback if upsert is too expensive:** Only emit OBS-01 logs; the "UI surface" becomes journalctl. Document this as a known trade-off and ship it. The planner can pick at planning time — both are tiny code differences.

**Recommendation: ship the access_count bump.** It directly satisfies KNOW-02 success criterion 2 ("knowledge-access event visible in the UI"). The OBS-01 log is the secondary, structured trail.

---

## R-06. Sync vs async (D-03c)

**Both exist. Wrap both.**

- `Knowledge.search(...)` — `knowledge.py:508`
- `Knowledge.asearch(...)` — `knowledge.py:549`

Internally, `asearch()` falls back to the sync `vector_db.search()` if the vector db raises `NotImplementedError` on async (`knowledge.py:587-590`) — PgVector implements `async_search` so async is the real path for AgentOS.

`agents/agent.py` (AgentOS runtime) uses `asearch()` for async runs (which is the AgentOS HTTP serving path) and `search()` for sync paths. **Both must be instrumented to cover all entry points.**

---

## R-07. Subclass vs composition for `InstrumentedKnowledge`

**Recommendation: subclass `Knowledge` directly.** Mirrors `InstrumentedMemoryManager` (phase 11 canonical).

### Why subclass works cleanly

`Knowledge` is a `@dataclass` (`knowledge/knowledge.py:41`). Subclassing it with only method overrides (no new fields) works without re-declaring `@dataclass`:

```python
from agno.knowledge.knowledge import Knowledge

class InstrumentedKnowledge(Knowledge):
    def search(self, query, ...):
        # time + log + super().search(...) + bump access_count
        ...
    async def asearch(self, query, ...):
        ...
```

`__post_init__` is inherited as-is — the table-existence check + `create()` happens automatically when the instance is constructed.

### Why composition is worse here

A composition wrapper would need to forward every method/attribute Agno reads from a Knowledge instance (`name`, `vector_db`, `contents_db`, `description`, `id`, `isolate_vector_search`, `max_results`, `readers`, `content_sources`, plus all `get_content*` / `remove_*` / `insert*` methods). `os/utils.py:354-396` reads `knowledge.contents_db`, `knowledge.name`, `getattr(knowledge, "name", None)` directly. Forwarding via `__getattr__` is doable but fragile and obscures which methods are intercepted.

Subclassing keeps the instrumentation surface tiny (4 method overrides: `search`, `asearch`, plus optional `_log` helper and `_bump_access_count` helper).

### Concrete wiring in `agentos/app.py`

Replace `make_knowledge()` so it constructs an `InstrumentedKnowledge` directly:

```python
# agentos/knowledge.py (rewrite)
def make_knowledge() -> Knowledge:
    vector_db = PgVector(table_name="vault", db_url=POSTGRES_DSN_KNOWLEDGE, ...)
    return InstrumentedKnowledge(
        name="ultra-brain-vault",
        vector_db=vector_db,
        contents_db=POSTGRES_DB,   # the shared PostgresDb(id="ultra-brain-main") from app.py
    )
```

`agentos/app.py` keeps the same line shape (`kb = vault.knowledge`); the only change is the Knowledge class is now `InstrumentedKnowledge`.

---

## R-08. Live integration test strategy for 13-02

Pattern to follow: phase 12's eval-recorder integration tests (look at `tests/test_eval_recorder*.py` or similar — same shape as memory's `tests/test_instrumented_memory*.py`).

### Test layout

**File:** `tests/test_instrumented_knowledge_live.py` (mirrors `tests/test_instrumented_memory_live.py` if it exists from phase 11; otherwise create the convention).

**Marker:** `@pytest.mark.live` — runs only when an integration DSN is exported. CI default-skips; operator runs locally with `POSTGRES_DSN_KNOWLEDGE` + `POSTGRES_DSN_SESSIONS` pointed at a throwaway local Postgres.

### Test flow

```python
@pytest.fixture
def tmp_vault(tmp_path):
    (tmp_path / "test_doc.md").write_text("Eiffel Tower is in Paris and was built in 1889.")
    monkeypatch.setenv("VAULT_PATH", str(tmp_path))

@pytest.mark.live
def test_reindex_writes_rows(tmp_vault, postgres_dsn_knowledge, postgres_dsn_sessions):
    # 1. Reindex
    from agentos.knowledge import reindex
    summary = reindex()
    assert summary.indexed == 1 and summary.errors == 0

    # 2. Row in ai.agno_knowledge
    rows = list_knowledge_rows(db_id="ultra-brain-main")
    assert any(r.name == "test_doc.md" for r in rows)

    # 3. Vector row in ai.vault
    assert count_vault_rows() >= 1

@pytest.mark.live
def test_idempotent_reindex(tmp_vault, ...):
    reindex(); first = count_vault_rows()
    reindex(); second = count_vault_rows()
    assert first == second   # KNOW-03

@pytest.mark.live
def test_search_emits_obs01_and_bumps_access_count(tmp_vault, caplog, ...):
    from agentos.app import kb   # the wired InstrumentedKnowledge
    reindex()
    before = get_access_count(kb, "test_doc.md")
    with caplog.at_level(logging.INFO, logger="agentos.knowledge"):
        hits = kb.search("Where is the Eiffel Tower?")
    assert len(hits) >= 1
    after = get_access_count(kb, "test_doc.md")
    assert after == before + 1
    # OBS-01 log line
    log_line = next(r for r in caplog.records if r.name == "agentos.knowledge")
    payload = json.loads(log_line.message.split(": ", 1)[1])
    assert payload["op"] == "search" and payload["hit_count"] >= 1
```

### CRITICAL safety: never touch the real vault

The fixture MUST set `VAULT_PATH` env var to `tmp_path` before importing `agentos.knowledge` (or the module-level `kb = VaultKnowledge()` evaluates against the real vault). Use `pytest`'s `monkeypatch` fixture inside a session-scoped wrapper, or just import `agentos.knowledge` lazily inside the test body after the env var is set. The current `agentos/knowledge.py` line 65 (`kb = VaultKnowledge()`) is a module-load-time side effect — the rewrite in 13-01 should keep this lazy or accept the test cost of always reading `VAULT_PATH` from env at construction time (which it already does).

### Recommended fixture utilities

- `count_vault_rows()` — `SELECT count(*) FROM ai.vault` via SQLAlchemy
- `list_knowledge_rows(db_id)` — `contents_db.get_knowledge_contents(...)` or `SELECT * FROM ai.agno_knowledge WHERE linked_to='ultra-brain-vault'`
- `get_access_count(kb, name)` — `contents_db.get_knowledge_content(generate_id(...))` then read `.access_count`

---

## R-09. Knowledge-access event row

Already answered in R-05: no separate access-events table; we bump `access_count` on the existing `ai.agno_knowledge` row instead. The UI Knowledge tab renders that column.

If a future phase needs per-search audit trails (who queried what, when), the right move is a new `ai.uab_knowledge_access(ts, db_id, query, content_ids[], agent_id, latency_ms)` table plus a custom AgentOS route. That is **explicitly out of scope for phase 13** — track as backlog candidate "OBS-02: per-search audit table" if the operator ever asks for it.

---

## R-10. OBS-01 log helper consolidation

**Current state of the repo:**
- `agentos/instrumented_memory.py` — duplicates the logger boilerplate (`getLogger("agentos.memory")` + force-INFO + StreamHandler-if-no-handlers + propagate=False) at module top.
- `agentos/eval_recorder.py` — duplicates the same boilerplate with `getLogger("agentos.eval")`.
- **No `agentos/obs.py` exists.** The pattern has now been copy-pasted twice (phase 11, phase 12).

**Recommendation for phase 13:** Continue the duplicate pattern. **Do NOT factor `agentos/obs.py` in this phase.** Three reasons:

1. Phase 13 already has a tight scope (3 plans, ~3 days of work). Adding a refactor of two existing files inflates the diff and bleeds risk into phase 11/12 territory.
2. The boilerplate is ~10 lines; the cost of duplication is small.
3. A proper `agentos/obs.py` should also unify the per-event log schema (`path`, `db_id`, `latency_ms`, `status`, ...) — that's a thoughtful API design that deserves its own discuss-phase + plan, not a hidden 13-01 task.

**Track as future cleanup phase:** "OBS helper consolidation — unify `agentos.memory`/`agentos.eval`/`agentos.knowledge` logger boilerplate and event schema."

For phase 13: copy the boilerplate from `instrumented_memory.py:13-22` verbatim into `agentos/instrumented_knowledge.py`, just renaming the logger to `agentos.knowledge`.

---

## Validation Architecture

This phase is observability-driven. The validation matrix for verification:

| Dimension | How verified |
|---|---|
| KNOW-01 row write | `SELECT count(*) FROM ai.vault` ≥ vault `.md` file count; `SELECT count(*) FROM ai.agno_knowledge WHERE linked_to='ultra-brain-vault'` ≥ vault `.md` file count |
| KNOW-01 API surface | `GET /knowledge/config` returns Available IDs containing the registered UUID; `GET /knowledge/content?db_id=ultra-brain-main` returns HTTP 200 with non-empty `data[]` |
| KNOW-02 RAG-hit surface | After a chat agent run that triggers RAG, `SELECT access_count FROM ai.agno_knowledge WHERE name=<hit_file>` increases by ≥1; os.agno.com Knowledge tab renders the bumped count |
| KNOW-03 idempotency | Run reindex twice on same vault; `SELECT count(*) FROM ai.vault` unchanged; second-run CLI summary reports `Indexed 0 files (N skipped)` |
| OBS-01 write path | `journalctl -u uab-brain.service \| grep '"path":"knowledge".*"op":"index"'` shows one well-formed line per indexed file |
| OBS-01 access path | Same grep with `"op":"search"` shows lines from chat agent RAG runs; one fault-injection unit test produces `"status":"error"` |
| DIAG-BL-06 stub fallback | Boot AgentOS without `POSTGRES_DSN_KNOWLEDGE` → log shows `{"path":"knowledge","status":"stub-fallback"}` WARNING line |

---

## Landmines

1. **`agno_knowledge` table DSN.** `contents_db` (PostgresDb) uses `POSTGRES_DSN_SESSIONS`. PgVector uses `POSTGRES_DSN_KNOWLEDGE`. Two DSNs, one shared `db_id="ultra-brain-main"`. Reindex CLI must initialize *both* — phase 11's app.py pattern handles `contents_db`; `make_knowledge()` must construct the PgVector with `POSTGRES_DSN_KNOWLEDGE`. Double-check both DSNs are exported on the VPS before the first reindex.

2. **Module-load side effect: `kb = VaultKnowledge()` at `agentos/knowledge.py:65`.** This instantiates a real PgVector connection at import time if `POSTGRES_DSN_KNOWLEDGE` is set. Tests that import `agentos.knowledge` before setting env vars will connect to whatever DSN is configured (or fail loudly). 13-01 rewrite should either keep this lazy (build only on first attribute access) or move it behind a `get_kb()` accessor. Existing test imports may need an audit.

3. **`Knowledge.insert(path=dir)` recursion.** `_load_from_path` recurses into directories one level (`knowledge.py:1481-1500`), but does NOT recurse deeper. Our vault has nested directories. The reindex loop must enumerate files itself (`Path(VAULT_PATH).rglob("*.md")`) and call `Knowledge.insert(path=<single_file>)` per file. Do NOT call `Knowledge.insert(path=<vault_root>)`.

4. **Agno hash != file content hash.** Stated explicitly in R-04. Critical to remember when implementing skip-unchanged: we cannot use Agno's `skip_if_exists=True`; we maintain our own sha256-of-bytes check via `metadata`.

5. **`upsert_knowledge_content` is sync only.** `db/postgres/postgres.py:2108` — sync. Async variant exists at `db/async_postgres/async_postgres.py:1912`. The wrapper's `asearch` override must call the sync variant via `asyncio.to_thread(...)` (mirrors phase 12 eval_recorder pattern at `agentos/eval_recorder.py:60-65`).

6. **Per-search access_count writes under contention.** If two agents hit the same content_id concurrently, the read-modify-write may lose increments. Acceptable for v1.5 (single-user dev + low-traffic VPS). If we ever go multi-tenant, switch to an atomic `UPDATE ai.agno_knowledge SET access_count = access_count + 1 WHERE id=...` (raw SQL bypassing the upsert helper).

7. **Knowledge tab shows ALL rows for `linked_to=name`, including deleted vault files.** Phase 13 is additive-only; orphans persist. Document in 13-03 verification doc.

---

## RESEARCH COMPLETE

All 10 open items from `13-CONTEXT.md` are answered with agno 2.6.7 source-file citations. The planner can lock:

- D-01: `Knowledge.insert(path=<single_file>, name=<rel_path>, metadata={"file_sha256": ..., "rel_path": ...})` per file.
- D-01a: skip-unchanged via in-process lookup of existing `ai.agno_knowledge.metadata.file_sha256`.
- D-02a: **Option 1** — metadata JSONB on `ai.agno_knowledge` rows.
- D-02c: `upsert=True` (Agno default) guarantees KNOW-03 row-count idempotency.
- D-03: subclass `Knowledge`; override `search()` + `asearch()`; bump `access_count` per unique hit.
- D-03a: subclass approach via `InstrumentedKnowledge(Knowledge)`; wire by replacing the `Knowledge` constructor inside `make_knowledge()`.
- D-03b: NO native UI surface; wrapper bumps `access_count`; UI renders bumps on `ai.agno_knowledge` rows.
- D-03c: wrap BOTH `search` and `asearch`.
- D-04: WARNING log on stub fallback — pattern from `instrumented_memory.py` (force INFO; StreamHandler if no handlers).
- D-05a: duplicate inline logger boilerplate; defer `agentos/obs.py` factoring.

**Critical wiring fix (was unstated in CONTEXT.md):** `make_knowledge()` MUST pass `contents_db=PostgresDb(id="ultra-brain-main")` AND `name="ultra-brain-vault"` — without these the AgentOS router skips the instance and Available IDs stays empty. This is the actual RC-knowledge-not-registered root cause.
