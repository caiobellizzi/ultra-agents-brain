# Phase 10 — Research

**Authored:** 2026-05-22
**Agno version installed:** 2.6.7 (`.venv/lib/python3.13/site-packages/agno/`)
**Source mode:** main-thread Opus (Sonnet quota exhausted; sub-agents skipped)

---

## Headline finding: `db_id` is a router registry key, not a DB column

**Critical correction to the audit framing.** `db_id` in Agno 2.6.7 is NOT a partition key
on table rows. It is the **AgentOS HTTP router query parameter** used to select which
registered `BaseDb` instance handles a request.

- `BaseDb.__init__` sets `self.id = id or str(uuid4())` — `agno/db/base.py:56`
- AgentOS holds `self.dbs: Dict[str, List[BaseDb]]` keyed by that id (auto-discovered from every
  Agent / Team / Workflow / Knowledge in `_auto_discover_databases()` — `agno/os/app.py:1049-1100`)
- Every router endpoint accepts `db_id: Optional[str] = Query(...)`, then calls
  `get_db(self.dbs, db_id, table)` to resolve. With **one** registered DB and no `db_id`,
  it returns that DB. With **multiple** registered DBs and no `db_id`, it raises HTTP 400
  (`agno/os/utils.py:246` and following).
- **No** `db_id` column exists on `agno_memories`, `agno_eval_runs`, `agno_knowledge`, or
  `agno_approvals`. Rows are physically isolated only when the **DB instance itself** is
  separate (different file / different schema / different DSN).

**Implication for DIAG-02:** The "per-agent vs shared workspace" decision is really
"register one `PostgresDb` shared by all five agents (current) vs register five `PostgresDb`
instances (one per agent) with stable user-supplied ids." Per-agent isolation under one DB
still requires shared rows since there is no row-level partition column.

---

## Project wiring (from `agentos/app.py` + `agentos/db.py`)

- Single DB selected at startup. When `POSTGRES_DSN_SESSIONS` is set → `PostgresDb(db_url=...,
  create_schema=True)`; otherwise `SqliteDb(db_file=~/Documents/uab-state/agno.db)`
  (`agentos/app.py:25-39`).
- Same `db` instance is passed to all 5 agents (`chat_agent`, `curator_agent`, `ingest_agent`,
  `query_agent`, `research_agent`) and the `supervisor_team`, AND to `AgentOS(db=db, ...)`.
- `MemoryManager(db=db, model=chat_model("cheap-worker"))` — a single MM shared by all agents.
- `kb = VaultKnowledge().knowledge` — single Knowledge instance with PgVector when
  `POSTGRES_DSN_KNOWLEDGE` is set, else empty stub.
- `agentos.cost` registers a `litellm.success_callback` for the cost ledger.
- VPS runs the `agentos` module, not `ultra_brain` (S21798).
- `db.id` is **not** explicitly set anywhere → each process boot generates a new UUID.
  **This alone is enough to break os.agno.com** if the dashboard caches a `db_id` across
  restarts (the cached id no longer exists after a redeploy → router returns 404).

---

## Default table names (`agno/db/base.py:57-72`)

| Surface       | Default table          | Source ref       |
|---------------|------------------------|------------------|
| Sessions      | `agno_sessions`        | base.py:57       |
| Memories      | `agno_memories`        | base.py:59       |
| Eval runs     | `agno_eval_runs`       | base.py:61       |
| Knowledge     | `agno_knowledge`       | base.py:62       |
| Traces        | `agno_traces`          | base.py:63       |
| Metrics       | `agno_metrics`         | base.py:60       |
| Approvals     | `agno_approvals`       | base.py:72       |
| Schedules     | `agno_schedules`       | base.py:70       |

Project does not override any of these — defaults apply.

---

## Per-surface write paths

### 1. Memory (`agno_memories`)

- **Write trigger:** `Agent.arun()` / `Agent.run()` when `enable_user_memories=True`
  (or `agent_memory=True` on team). Flow → `MemoryManager.create_user_memories()`
  (`agno/memory/manager.py`) → `db.upsert_user_memory(UserMemory)` (PostgresDb has
  `upsert_user_memory`, `get_user_memories`, `delete_user_memories` — see
  `agno/db/postgres/postgres.py:1362`).
- **Read endpoint:** `GET /memories` → `get_memory_router()` → `db.get_user_memories(...)`
  (`agno/os/routers/memory/memory.py`).
- **Dashboard:** os.agno.com "Memory" tab.
- **Likely current state:** EMPTY. None of the 5 agents in `agentos/agents/*.py` are
  expected to set `enable_user_memories=True` (verify by grep — MEM-03 in REQUIREMENTS).
  No `enable_user_memories=True` → MM never invoked → no rows.

### 2. Evals (`agno_eval_runs`)

- **Write trigger:** EXPLICIT — `AccuracyEval(...).run()`, `PerformanceEval`, `ReliabilityEval`,
  or `AgentAsJudgeEval` (`agno/eval/{accuracy,performance,reliability,agent_as_judge}.py`).
  Each calls `db.create_eval_run(EvalRunRecord)` (`agno/db/postgres/postgres.py:2196`).
- **`Agent.arun()` does NOT auto-eval.** Eval rows only exist if eval code is run explicitly
  (CI, batch job, manual invocation).
- **Read endpoint:** `GET /evals` → `get_eval_run` (`agno/os/routers/evals/evals.py:227`).
- **Dashboard:** os.agno.com "Evals" tab.
- **Likely current state:** EMPTY because no eval harness runs against the deployed
  AgentOS — `evals/conftest.py` exists but is for `pytest` runs, not for writing to prod DB.
  Cross-check S605 noted "eval failures" — that may be local eval pytest, not AgentOS row writes.
- **Landmine:** LiteLLM judge errors (S605, S21769) — `agent_as_judge` calls LiteLLM via
  the configured `model=`. If the judge call fails, the eval may raise before
  `create_eval_run()` is called. Verify by checking whether `accuracy.py` writes a partial
  row on failure or aborts the run.

### 3. Knowledge (`agno_knowledge`)

- **Write trigger:** `Knowledge.add_content()` / `Knowledge.add_contents()` (`agno/knowledge/knowledge.py`),
  invoked at startup by `VaultKnowledge().load()` (`agentos/app.py`) and incrementally by the
  curator agent. Storage layer: `db.upsert_knowledge_content()` for the metadata row +
  PgVector for embeddings.
- **Read endpoint:** `GET /knowledge/content`, `POST /knowledge/search`
  (`agno/os/routers/knowledge/knowledge.py:115, 267, 422, 529`).
- **Dashboard:** os.agno.com "Knowledge" tab.
- **Likely current state:** Possibly POPULATED IF `POSTGRES_DSN_KNOWLEDGE` is set on VPS and
  the vault load completed; otherwise EMPTY (the dev fallback is an empty stub —
  `VaultKnowledge.knowledge` returns empty when DSN missing). Check VPS env.
- **`vector_db_ids` is a separate concept** from `db_id` — Knowledge router accepts both
  (`agno/os/routers/knowledge/schemas.py:166-168`). PgVector instance also has its own id.

### 4. Approvals (`agno_approvals`)

- **Write trigger:** `@tool(requires_confirmation=True)` decorator (`agno/approval/decorator.py`)
  on tools. When the agent calls the tool, Agno creates an approval row and pauses the run
  until resolved. Pause/resume protocol uses `agno/run/approval.py`.
- **Read endpoint:** `GET /approvals` (`agno/os/routers/approvals/router.py:82`), resolve
  via `POST /approvals/{id}/resolve` (router.py:164).
- **Note:** Approval router uses `os_db` (the single AgentOS-level DB), not the multi-DB
  `dbs` dict. So `db_id` does NOT apply to approvals — they always go to the AgentOS DB.
  The router raises HTTP 503 if the DB does not implement `get_approval`
  (`agno/os/routers/approvals/router.py:62`).
- **Dashboard:** os.agno.com "Approvals" tab.
- **Likely current state:** EMPTY unless an HITL-confirmed tool was invoked. Grep
  `requires_confirmation=True` across `ultra_brain/` and `agentos/tools/` — if zero matches,
  approvals are structurally impossible to populate. SqliteDb fallback may not implement
  approvals (verify against `agno/db/sqlite/sqlite.py`).

---

## Why os.agno.com surfaces show empty (working hypotheses to confirm in audit)

In priority order:

1. **Stale db_id cache (highest probability).** Each VPS restart regenerates `BaseDb.id`
   because `agentos/app.py` does not pin `id=`. Dashboard caches the previously-seen id and
   queries return HTTP 404. Confirmable via `curl` to AgentOS with and without `db_id=`.
2. **Memory disabled.** `enable_user_memories=True` not set on any agent → `agno_memories` is empty.
3. **No eval harness in prod.** Evals are pytest-only; `agno_eval_runs` is empty by design.
4. **PgVector knowledge DSN missing or vault load failed at boot.** Knowledge router returns
   empty.
5. **No HITL tools.** Zero tools with `requires_confirmation=True` → `agno_approvals` is empty.
6. **AgentOS auth.** os.agno.com requires JWT for the deployment — `get_authentication_dependency`
   wraps all routers (router.py:53). If JWT is misconfigured, all queries 401 → surface looks empty.

Each hypothesis maps cleanly to one of phases 11–14.

---

## Evidence-collection recipes (read-only — D-03)

All commands prefixed with `rtk` per project CLAUDE.md.

### Find DSN + container shape
```
rtk docker compose -f deploy/docker-compose.yml ps
rtk docker compose -f deploy/docker-compose.yml exec agentos env | rtk grep -i 'POSTGRES_DSN\|UAB_'
```
**Do not echo full DSN with password** into AUDIT.md. Redact to `postgresql://<user>:****@<host>/<db>`.

### Psql snapshots (production DB, READ-ONLY)
```
# Connect through agentos container or directly using DSN (host machine)
rtk docker compose -f deploy/docker-compose.yml exec postgres psql -U <user> -d <db> -c "\dt"
rtk docker compose -f deploy/docker-compose.yml exec postgres psql -U <user> -d <db> -c "SELECT count(*) FROM agno_memories;"
rtk docker compose -f deploy/docker-compose.yml exec postgres psql -U <user> -d <db> -c "SELECT count(*) FROM agno_eval_runs;"
rtk docker compose -f deploy/docker-compose.yml exec postgres psql -U <user> -d <db> -c "SELECT count(*) FROM agno_knowledge;"
rtk docker compose -f deploy/docker-compose.yml exec postgres psql -U <user> -d <db> -c "SELECT count(*) FROM agno_approvals;"
rtk docker compose -f deploy/docker-compose.yml exec postgres psql -U <user> -d <db> -c "SELECT count(*) FROM agno_sessions;"
# Sample row (or zero) per surface
rtk docker compose -f deploy/docker-compose.yml exec postgres psql -U <user> -d <db> -c "SELECT * FROM agno_memories ORDER BY updated_at DESC LIMIT 1;"
```
Absence-of-evidence: record both the query and the empty result verbatim (D-02).

### AgentOS HTTP probes (against VPS, read-only endpoints)
```
# Identify db_id Agno auto-generated:
rtk curl -s -H "Authorization: Bearer $AGENTOS_JWT" https://<vps-host>/databases | jq .
# Per-surface (with and without db_id to confirm caching hypothesis):
rtk curl -s -H "Authorization: Bearer $AGENTOS_JWT" "https://<vps-host>/memories" | jq '.items | length'
rtk curl -s -H "Authorization: Bearer $AGENTOS_JWT" "https://<vps-host>/memories?db_id=<id>" | jq '.items | length'
rtk curl -s -H "Authorization: Bearer $AGENTOS_JWT" "https://<vps-host>/evals" | jq '.items | length'
rtk curl -s -H "Authorization: Bearer $AGENTOS_JWT" "https://<vps-host>/knowledge/content" | jq '.items | length'
rtk curl -s -H "Authorization: Bearer $AGENTOS_JWT" "https://<vps-host>/approvals" | jq '.items | length'
```
If 401: auth misconfigured (hypothesis 6). If 404 with id, 200 without: stale-cache (hypothesis 1).

### os.agno.com UI observation
- Login to https://os.agno.com, connect the ultra-brain deployment.
- For each of Memory / Evals / Knowledge / Approvals tabs:
  - Open browser devtools → Network tab
  - Capture the exact API request URL (with `db_id` query string)
  - Compare against the `db_id` returned by `GET /databases` above
  - Record empty state vs. populated, exact URL, response status
  - Save screenshot to `phases/10-diagnostic-audit/evidence/<surface>.png`

---

## DB-ID-DECISION.md inputs (already sufficient — no spike needed)

The audit can render the decision from source alone. No D-06 spike is required because the
ambiguity is resolved: `db_id` is a registry key (`agno/db/base.py:56`,
`agno/os/app.py:1049-1100`, `agno/os/utils.py:246+`) — three citations.

The decision the operator must make:
- **A. Pin one shared id** (`SqliteDb(id="ultra-brain-main", ...)` / `PostgresDb(id="ultra-brain-main", ...)`)
  → stable across restarts, all 5 agents share storage. Simplest fix for the stale-cache
  hypothesis. Recommended unless the operator has a reason to isolate per agent.
- **B. Per-agent ids** (`PostgresDb(id="chat", ...)`, `PostgresDb(id="curator", ...)`, …)
  → os.agno.com must pass the right `db_id` per request. Useful only if surfaces should be
  visually segregated per agent. Increases DB connection count 5×.
- Migration: option A requires no row migration (single DB stays the same — just pins the id).
  Option B requires either (a) creating 5 separate DBs/DSNs and re-loading, or (b) 5 schemas
  on the same DSN (`agno/db/postgres/postgres.py` accepts `db_schema=...`). Existing rows
  cannot be re-attributed across schemas without manual SQL.

**Downstream consequences (for phases 11–14):**
- Phase 11 (Memory): independent of A/B — must set `enable_user_memories=True` on agents.
- Phase 12 (Evals): independent of A/B — must register an eval harness that actually writes rows.
- Phase 13 (Knowledge): independent of A/B — must verify PgVector DSN + vault load succeeds.
- Phase 14 (Approvals): independent of A/B — must introduce at least one `requires_confirmation=True` tool.
- Phase 15 (Worker hygiene): orthogonal — date-mismatch + sync-delete bugs (S21808, S21815).

---

## BACKLOG candidates surfaced during research (per D-11)

To pre-populate `BACKLOG.md` after the audit:

- **DIAG-BL-01 (high):** `agentos/app.py` does not pin `db.id` — every redeploy regenerates the
  UUID. Suggest phase 11–14 work also pins `id="ultra-brain-main"` (or whichever the
  DB-ID-DECISION lands on). Repro: restart agentos container → `BaseDb.id` is new uuid.
- **DIAG-BL-02 (medium):** SqliteDb fallback in `agentos/app.py:35-39` may not implement
  approval methods. If VPS ever drops to fallback (DSN unset), `/approvals` returns 503.
  Verify against `agno/db/sqlite/sqlite.py`.
- **DIAG-BL-03 (medium):** No CI/cron eval harness — `evals/conftest.py` runs only under
  pytest. `agno_eval_runs` will remain empty in prod until an explicit eval driver lands.
  Phase 12 scope.
- **DIAG-BL-04 (low):** `agentos/agents/*.py` — none likely set `enable_user_memories`.
  Confirmed in audit task → BACKLOG promoted to phase 11.
- **MON-01 (carried over, S21808):** daily-brief missed monitor-filed items due to date
  mismatch — already tagged for phase 15.
- **MON-02 (carried over, S21815):** vault sync `--delete` deleting VPS-generated inbox items
  — already tagged for phase 15.

---

## AUDIT.md 5-section template — viable for all 4 surfaces

The CONTEXT.md D-08 template (expected write path / DB schema + row evidence / API response /
UI state / root-cause hypothesis) works uniformly. One deviation worth noting:

- For **Approvals**, "AgentOS API response" must capture both the read endpoint
  (`GET /approvals`) and confirm the DB backend implements approval methods (HTTP 503 if not).
- For **Knowledge**, capture both `GET /knowledge/content` and `POST /knowledge/search`
  because the dashboard uses search, not list, for the main view.

The summary matrix at the head of AUDIT.md (D-09):
`surface | write-fn (Agno src) | db-table | db-row-count | api-status | ui-shows? | root-cause-tag`

---

## Open questions to resolve during the audit (not blocking planning)

1. What is the actual `db.id` UUID currently in the VPS process? (Captured by
   `GET /databases` probe.)
2. Does the VPS have `POSTGRES_DSN_SESSIONS` and `POSTGRES_DSN_KNOWLEDGE` both set?
   (Captured by `docker exec ... env` probe.)
3. Does os.agno.com pass `db_id` on its outgoing requests, and if so, where does the id
   come from? (Browser devtools observation.)
4. Are there any `requires_confirmation=True` decorators anywhere in `ultra_brain/` or
   `agentos/tools/`? (Repo-wide grep.)
5. Does `agno/db/sqlite/sqlite.py` implement `get_approval`, `create_eval_run`,
   `upsert_user_memory`, `upsert_knowledge_content`? (Source inspection — gates which
   fallback states are possible.)

These are captured as audit tasks in PLAN.md, not as research follow-ups.

## RESEARCH COMPLETE
