# AUDIT.md — AgentOS surface diagnostic (phase 10)

> Phase 10 / Plan 01 output. Read-only audit of the four AgentOS write paths on the production VPS (`root@31.97.130.253`, AgentOS at `http://31.97.130.253:7000`, agno 2.6.7).
> Captured 2026-05-22. Backing evidence: `.planning/phases/10-diagnostic-audit/evidence/`.
> Read-only attestation: pg_stat snapshots before/after are byte-identical (see Appendix A).
>
> UI screenshots were **deferred at operator authorization**, but the operator manually verified the dashboard state on 2026-05-22: **memory tab renders data; evals, knowledge, approvals tabs render no data.** Section 4 per surface records that direct observation; PNG capture can be added later if a finding needs forensic detail (e.g. Network-tab request shape).

## Summary matrix

| Surface | Write fn (Agno src) | DB table | Row count | API status | UI shows? | Root-cause tag |
|---|---|---|---|---|---|---|
| memory | `PostgresDb.upsert_user_memory()` @ `agno/db/postgres/postgres.py:1653` (also async @ `async_postgres.py:1532`); contract @ `agno/db/base.py:264` | `ai.agno_memories` (agno_sessions DB) | **1** | `GET /memories` → 200, 1 item | **Yes (operator-confirmed)** — dashboard renders the workshop-user row | **RC-memory-thin-usage** *(working but only one user has interacted)* |
| evals  | `PostgresDb.create_eval_run()` @ `agno/db/postgres/postgres.py:2196` (also async @ `async_postgres.py:2001`) | `ai.agno_eval_runs` | **0** | `GET /eval-runs` → 200, empty | **No (operator-confirmed)** — empty state | **RC-no-eval-harness** *(no agent run has ever invoked `db.create_eval_run`)* |
| knowledge | `PostgresDb.upsert_knowledge_content()` @ `agno/db/postgres/postgres.py:2108` (also async @ `async_postgres.py:1912`) | `ai.agno_knowledge` (in agno_sessions DB); separate Postgres DB `agno_knowledge` is empty | **0** in `ai.agno_knowledge`; **0 tables** in the `agno_knowledge` DB itself | `GET /knowledge/content` → **400** (`Available IDs: []`); with the registered `db_id` → **404** (`Knowledge instance with db_id '…' not found`) | **No (operator-confirmed)** — empty / error state | **RC-knowledge-not-registered** *(POSTGRES_DSN_KNOWLEDGE is wired but no `Knowledge` instance is registered with AgentOS — see Section 3 below)* |
| approval | `PostgresDb.create_approval()` @ `agno/db/postgres/postgres.py:4813` (router @ `agno/os/routers/approvals/router.py:19` — uses `os_db` only, does **not** accept `db_id`) | `ai.agno_approvals` | **0** | `GET /approvals` → 200, empty | **No (operator-confirmed)** — empty state | **RC-no-hitl-trigger-yet** *(3 vault tools + ingest tool decorated with `requires_confirmation=True`, but no agent run has invoked them in production yet — table is empty rather than gated)* |

Stable identifiers (referenced by phases 11–14): `RC-memory-thin-usage`, `RC-no-eval-harness`, `RC-knowledge-not-registered`, `RC-no-hitl-trigger-yet`.

---

## 1. Memory surface

### Section 1 — Expected write path

- Agno write: `PostgresDb.upsert_user_memory()` at `agno/db/postgres/postgres.py:1653` (sync) and `agno/db/postgres/async_postgres.py:1532` (async). Base contract: `agno/db/base.py:264` (sync) / `:1274` (async). Default table name: `"agno_memories"` per `agno/db/base.py:59`.
- Project-side gating: every agent enables agentic memory writes — see `evidence/write-gate-grep.txt`:
  - `agentos/agents/chat.py:43` — `enable_agentic_memory=True`, `update_memory_on_run=True`
  - `agentos/agents/curator.py:25-26`, `query.py:43-44`, `research.py:31-32`, `ingest.py:29-30`, `supervisor.py:49-50` — same pair
- Shared `MemoryManager` is constructed once at `agentos/app.py:45-49` and passed to every factory.

### Section 2 — DB schema + row evidence

From `evidence/psql.txt` (schema `ai`, agno_sessions DB):

```
                        Table "ai.agno_memories"
   Column   |       Type        | Nullable | Default
------------+-------------------+----------+---------
 memory_id  | character varying | not null |
 user_id    | character varying |          |
 agent_id   | character varying |          |
 team_id    | character varying |          |
 topics     | jsonb             |          |
 updated_at | bigint            |          |
 memory     | jsonb             | not null |
Indexes: PRIMARY KEY (memory_id); idx_agno_memories_user_id

 row_count
-----------
         1

 memory_id                            | user_id  | topics                     | updated_at
--------------------------------------+----------+----------------------------+------------
 923150df-b1d9-4390-b04b-c765bbaccf0b | workshop | ["work", "coding", "task"] | 1779476451
```

pg_stat (Appendix A): `agno_memories` n_tup_ins=1, n_tup_upd=1, n_tup_del=0 — write path is exercised.

### Section 3 — AgentOS API response

`GET http://31.97.130.253:7000/memories` (no auth, no `db_id`) → HTTP 200 (file: `evidence/memories.json`):

```json
{"data":[{"memory_id":"923150df-…","memory":"User completed an 'aider' task …",
          "topics":["work","coding","task"],"user_id":"workshop",
          "updated_at":"2026-05-22T19:00:51Z"}],
 "meta":{"page":1,"limit":20,"total_pages":1,"total_count":1}}
```

`GET /memories?db_id=e9a76996-9f0a-535a-bd92-c215f571af96` returns **identical** body (`evidence/memories-with-id.json`) — falsifies the prior "stale db_id" hypothesis for memory: API works with or without the explicit param.

### Section 4 — UI state

**Operator-confirmed 2026-05-22:** the os.agno.com Memory tab **renders data** — consistent with the single `workshop`-user row returned by `GET /memories`. PNG capture was deferred. The dashboard request shape (with/without `db_id`) is not material here because the API returns the same body either way (Section 3 above).

### Section 5 — Root-cause hypothesis

**Primary tag: `RC-memory-thin-usage`.** The memory surface is functionally correct (Sections 1–3 prove: gating enabled on all 5 agents, write path exercised, API returns the row). The single row reflects production traffic: only the `workshop` user has interacted with the brain enough to trigger `update_memory_on_run`. Phases 11–14 should treat this as a working surface — any "missing memory" UX issue is a **usage signal**, not a wiring bug. (No secondary tag.)

---

## 2. Evals surface

### Section 1 — Expected write path

- Agno write: `PostgresDb.create_eval_run()` at `agno/db/postgres/postgres.py:2196` (sync) / `async_postgres.py:2001` (async). Default table: `"agno_eval_runs"` per `agno/db/base.py:61`.
- Trigger: an `Eval` / `AgentAsJudgeEval` instance attached to an `Agent` via `evals=[…]`. **Current Agno does not accept `evals=` on Agent** — see comment at `agentos/agents/chat.py:75-77`: *"The current Agno version does not accept an `evals=` kwarg on Agent."* The `citation_judge` (`AgentAsJudgeEval`) is constructed but **unused** (`agentos/agents/chat.py:25-37`, with `_ = citation_judge` at the bottom).
- Standalone runner: nothing in `agentos/` or `ultra_brain/` invokes `db.create_eval_run` directly.

### Section 2 — DB schema + row evidence

```
                       Table "ai.agno_eval_runs"
          Column          |   Type            | Nullable
--------------------------+-------------------+----------
 run_id                   | character varying | not null
 eval_type                | character varying | not null
 eval_data                | jsonb             | not null
 eval_input               | jsonb             | not null
 agent_id / team_id / workflow_id  | character varying |
 model_id / model_provider         | character varying |
 created_at | bigint | not null
 updated_at | bigint |

 row_count
-----------
         0
```

pg_stat: n_tup_ins=0, n_tup_upd=0 — table exists, never written.

### Section 3 — AgentOS API response

`GET http://31.97.130.253:7000/eval-runs` → HTTP 200 (`evidence/eval-runs.json`):

```json
{"data":[],"meta":{"page":1,"limit":20,"total_pages":0,"total_count":0,"search_time_ms":0.0}}
```

With `?db_id=…`: identical empty response. Note that the endpoint is **`/eval-runs`**, not the `/evals` path the original plan/RESEARCH assumed.

### Section 4 — UI state

**Operator-confirmed 2026-05-22:** the os.agno.com Evals tab **renders no data** — consistent with the empty `GET /eval-runs` response (Section 3) and the zero rows in `ai.agno_eval_runs` (Section 2). UI is faithfully reflecting backend state.

### Section 5 — Root-cause hypothesis

**Primary tag: `RC-no-eval-harness`.** Zero rows because nothing in the project invokes the Agno eval write path. The only `Eval` instance ever constructed (`citation_judge` in `agentos/agents/chat.py:25-37`) is explicitly held back (`_ = citation_judge`) because the installed Agno version does not accept `evals=` on `Agent`. Phase 13 (eval activation) must either (a) upgrade Agno to a version exposing the `evals=` kwarg, or (b) build an out-of-band eval runner that calls `db.create_eval_run` directly from a CLI harness or scheduled job. The empty table is **expected**, not a regression.

---

## 3. Knowledge surface

### Section 1 — Expected write path

- Agno write: `PostgresDb.upsert_knowledge_content()` at `agno/db/postgres/postgres.py:2108` (sync) / `async_postgres.py:1912` (async). Default table: `"agno_knowledge"` per `agno/db/base.py:62`.
- Project-side wiring: `agentos/app.py:53-56` creates a `VaultKnowledge()` and calls `.load()` once at startup; `kb = vault.knowledge` is passed to every agent factory; `agent_os = AgentOS(…, knowledge=[kb], …)` at `agentos/app.py:69-74`.
- `VaultKnowledge` guards `make_knowledge()` — *"only creates PgVector when `POSTGRES_DSN_KNOWLEDGE` is set; falls back to an empty Knowledge otherwise"* (comment at `agentos/app.py:53-54`).

### Section 2 — DB schema + row evidence

Two distinct stores are involved here, and **both are empty**:

**(a) `ai.agno_knowledge` table** (in agno_sessions DB — the Agno content registry):

```
                  Table "ai.agno_knowledge"
        Column        |   Type            | Nullable
----------------------+-------------------+----------
 id, name, description, type, size, …    |   …
 created_at | bigint | not null
 updated_at | bigint |
row_count: 0
```

**(b) `agno_knowledge` PostgreSQL database** (the separate DSN target — intended for PgVector embeddings):

```
\dt   → "Did not find any relations."
\dn   →   ai     | uab
          public | pg_database_owner
```

The database exists and the `ai` schema exists, but **no tables have been created**. PgVector / Knowledge migrations have never been run against this DSN.

### Section 3 — AgentOS API response

```
GET /knowledge/content         → HTTP 400  {"detail":"db_id or knowledge_id query parameter is required when using multiple knowledge bases. Available IDs: []"}
GET /knowledge/content?db_id=e9a76996-…  → HTTP 404 {"detail":"Knowledge instance with db_id 'e9a76996-…' not found"}
GET /knowledge/config          → HTTP 400 (identical "Available IDs: []" body)
POST /knowledge/search {"query":"test"}  → HTTP 400 (identical "Available IDs: []" body)
```

Files: `evidence/knowledge-content.json`, `evidence/knowledge-content-with-id.json`, `evidence/knowledge-config.json`, `evidence/knowledge-search.json`.

The smoking gun is `Available IDs: []`. AgentOS is iterating the registered knowledge instances and reporting zero — even though `app.py` calls `AgentOS(knowledge=[kb], …)`. *(inference)* This means `VaultKnowledge().knowledge` resolved to the **empty stub fallback** at startup, not a real `Knowledge(vector_db=PgVector(...))`, despite `POSTGRES_DSN_KNOWLEDGE` being set in `/opt/ultra-agents-brain/.env`. The likely concrete cause is a deferred initialization or migration step that `VaultKnowledge.load()` does not perform — phase 12 (knowledge activation) needs to confirm by reading `agentos/knowledge.py` and running the migration explicitly.

### Section 4 — UI state

**Operator-confirmed 2026-05-22:** the os.agno.com Knowledge tab **renders no data**. The backend returns HTTP 400 with `Available IDs: []` from `/knowledge/content` and `/knowledge/config` regardless of whether a `db_id` is supplied (Section 3) — the UI surfaces this as an empty/error state. Faithful reflection of backend state.

### Section 5 — Root-cause hypothesis

**Primary tag: `RC-knowledge-not-registered`.** Two findings stack:
1. `/knowledge/config` reports zero registered knowledge IDs even though `AgentOS(knowledge=[kb], …)` is called with a non-empty list (Section 1 + `evidence/config.json`).
2. The dedicated `agno_knowledge` Postgres database contains **zero tables** in either `public` or `ai` schema, confirming PgVector / Agno knowledge migrations were never executed against the DSN.

Phase 12 must (a) determine why `VaultKnowledge` resolves to the empty stub (look at `agentos/knowledge.py` import-time DSN check, and at the agno `Knowledge` constructor for the failure mode it tolerates silently), (b) run the PgVector / agno_knowledge migrations against the `agno_knowledge` database, and (c) re-register the resulting `Knowledge` instance with AgentOS so `/knowledge/config` returns a non-empty `Available IDs` list. *(inference labelled because the exact silent-fallback line in `VaultKnowledge` was not opened during this audit — see "next phase" note in plan 10-02.)*

---

## 4. Approval surface

### Section 1 — Expected write path

- Agno write: `PostgresDb.create_approval()` at `agno/db/postgres/postgres.py:4813`. Default table: `"agno_approvals"` per `agno/db/base.py:72`.
- Router: `agno/os/routers/approvals/router.py:19` — `get_approval_router(os_db, settings)`. **The router only reads from `os_db`**, the AgentOS-level DB adapter; it does **not** take a `db_id` query param and does not iterate the multi-DB `dbs` dict. Confirmed by reading the router docstring (lines 19-41). Phases 11–14 must treat approvals as singleton-DB scoped.
- Project-side trigger: `@tool(requires_confirmation=True)` decorations create approval records. Per `evidence/write-gate-grep.txt`:
  - `agentos/tools/vault.py:35` — `@tool(requires_confirmation=True)` (write-vault-file)
  - `agentos/tools/vault.py:56` — `@tool(requires_confirmation=True)` (likely append-to-vault or similar)
  - `agentos/agents/ingest.py:3` references *"ingest_to_vault is decorated with `@tool(requires_confirmation=True)`"* — so `ingest_to_vault` is the third confirmation-gated tool.

### Section 2 — DB schema + row evidence

```
                  Table "ai.agno_approvals"
       Column        |       Type        | Nullable
---------------------+-------------------+----------
 approval_id         | character varying | not null
 user_id             | character varying |
 status              | character varying | not null
 tool_call_id        | character varying |
 tool_name           | character varying |
 tool_args           | jsonb             |
 …                   |   …
 created_at          | bigint            | not null
 updated_at          | bigint            |
row_count: 0
```

pg_stat: n_tup_ins=0 — never written.

### Section 3 — AgentOS API response

`GET http://31.97.130.253:7000/approvals` → HTTP 200 (`evidence/approvals.json`):

```json
{"data":[],"meta":{"page":1,"limit":100,"total_pages":0,"total_count":0,"search_time_ms":0.0}}
```

`GET /approvals?db_id=…` returns an identical body — but per Section 1 the `db_id` param is **ignored by this router** (the router uses `os_db` only). Phases 11–14 should not pass `db_id` for the approval surface.

### Section 4 — UI state

**Operator-confirmed 2026-05-22:** the os.agno.com Approvals tab **renders no data** — consistent with the empty `GET /approvals` response (Section 3) and the zero rows in `ai.agno_approvals` (Section 2). UI is faithfully reflecting backend state.

### Section 5 — Root-cause hypothesis

**Primary tag: `RC-no-hitl-trigger-yet`.** Three vault tools + the `ingest_to_vault` tool are decorated `requires_confirmation=True` (Section 1), so the gating code path **exists**. The empty `ai.agno_approvals` table means: *(inference)* no agent has invoked a confirmation-gated tool in production since the deployment started — i.e. no chat or research session has tried to write to the vault yet. This is consistent with the thin memory usage finding (only `user_id=workshop` has interacted).

Phase 14 (approval activation) should: (a) trigger one of the gated tools via a real run to confirm the row is materialized in `ai.agno_approvals`, (b) verify the `/approvals` API surfaces it, (c) cross-check the UI updates. If after a confirmed trigger the table stays empty, escalate to a secondary tag `RC-hitl-write-broken` and re-open the audit.

---

## Appendix A — Read-only guardrail attestation

`pg_stat_user_tables` snapshot before any audit probes (file: `evidence/pg_stat_before.txt`):

```
agno_approvals|0|0|0
agno_component_configs|0|0|0
agno_component_links|0|0|0
agno_components|0|0|0
agno_eval_runs|0|0|0
agno_knowledge|0|0|0
agno_learnings|0|0|0
agno_memories|1|1|0
agno_metrics|2|2|0
agno_schedule_runs|0|0|0
agno_schedules|0|0|0
agno_schema_versions|14|0|0
agno_sessions|39|3|0
agno_spans|114|0|0
agno_traces|42|72|0
```

Snapshot after all probes (`evidence/pg_stat_after.txt`): **byte-identical**. `diff pg_stat_before.txt pg_stat_after.txt` returned with exit code 0 and zero output. **No INSERT / UPDATE / DELETE / DDL occurred during the audit.**

Counter movement on `agno_sessions`, `agno_spans`, `agno_traces` between the deployment start and the audit window reflects normal user / telemetry traffic, not audit writes.

## Appendix B — Companion documents

- **DB-ID-DECISION.md** — Chosen model: **Option A — Pin one shared `BaseDb.id` across all five agents + AgentOS.** Concretely: in `agentos/app.py`, change `db = PostgresDb(db_url=DSN, ...)` to `db = PostgresDb(id="ultra-brain-main", db_url=DSN, ...)` and keep wiring that single instance to every agent factory, the `MemoryManager`, and `AgentOS(db=db, ...)`. Six citations (4 Agno-source + 2 project-source). Downstream consequences specified for phases 11, 12, 13, 14. See `DB-ID-DECISION.md`.
- **BACKLOG.md** — Six pre-populated items (`MON-01`, `MON-02`, `DIAG-BL-01..04`) plus six audit-surfaced items (`DIAG-BL-05..10`). Operator review owns promotion to REQUIREMENTS.md. See `BACKLOG.md`.
