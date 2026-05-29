# DB-ID-DECISION.md — chosen Agno DB registration model for ultra-agents-brain

> Phase 10 / Plan 02 deliverable. Locks the answer to: *"Should ultra-agents-brain register one shared `BaseDb` instance for every agent + AgentOS, or one `BaseDb` per agent?"* Phases 11–14 read this as a committed decision.
>
> Decision date: 2026-05-22. Reviewed against `AUDIT.md` matrix + 4 root-cause tags.

## TL;DR

**Option A — Pin one shared `BaseDb.id` across all five agents + AgentOS.** Concretely: in `agentos/app.py`, change `db = PostgresDb(db_url=DSN, ...)` to `db = PostgresDb(id="ultra-brain-main", db_url=DSN, ...)` and keep wiring that single instance to every agent factory, the `MemoryManager`, and `AgentOS(db=db, ...)`. The shared DB is also the `os_db` (the AgentOS-level DB the approval router uses).

## What `db_id` actually is — debunking the row-partition misconception

A common misreading of the AgentOS API is to treat `db_id` as a **row-partition column** that tags rows in `agno_memories` / `agno_eval_runs` / etc. with which "logical database" they belong to. This is wrong. `db_id` is a **router registry key** — it identifies which registered `BaseDb` *instance* an HTTP request should be routed to. Three Agno-source citations make this concrete:

- `agno/db/base.py:56` — `self.id = id or str(uuid4())`. Every `BaseDb` constructor either accepts a caller-supplied `id` or generates a fresh UUID at construction time. The id lives on the **adapter object**, not on rows.
- `agno/os/app.py:1049-1100` — `_auto_discover_databases()` walks every agent's `db=` arg (plus the AgentOS-level `db=` and any `knowledge=[...]` `vector_db`), collects unique `BaseDb` instances, and builds `self.dbs: Dict[str, List[BaseDb]]` keyed by each instance's `id`. The "list of registered databases" the dashboard sees is just the keys of that dict.
- `agno/os/utils.py:246+` — `get_db(db_id=...)` looks the request's optional `db_id` query param up in that dict. With **one** registered DB and no `db_id` supplied, it returns the singleton. With **multiple** DBs and no `db_id` supplied, it raises HTTP 400 (`"db_id ... query parameter is required when using multiple <surface>"` — exactly the body we observed at `/knowledge/content` and `/knowledge/config` during the audit, see `evidence/knowledge-content.json`).

Implication: if two agents pass the **same** `BaseDb` Python object into their factories, Agno deduplicates by `id` and `self.dbs` ends up with one entry. If two agents pass **different** `PostgresDb(...)` objects pointing at the same DSN, Agno sees two distinct adapters and the `/databases` / `/memories?db_id=...` API requires the caller to disambiguate. The DSN doesn't matter; the **instance identity** + the **id field** do.

## Options considered

### Option A — Pin one shared id

```python
# agentos/app.py
db = PostgresDb(id="ultra-brain-main", db_url=os.environ["POSTGRES_DSN_SESSIONS"])
# ...passed verbatim to every agent factory and to AgentOS(db=db, ...)
```

**Pros**
- 1-line change from the current architecture (`agentos/app.py:25-58` already uses a single shared `db`).
- `db_id` becomes deterministic across redeploys — dashboards / external callers can cache it.
- AgentOS-level routes that take no `db_id` (e.g. `/approvals` → uses `os_db` exclusively per `agno/os/routers/approvals/router.py:19-41`) continue to work without an "which DB is AgentOS-level?" debate.
- No new DSNs, no new migrations, no new env vars.

**Cons**
- All five agents share the same `ai.agno_sessions`, `ai.agno_memories`, `ai.agno_eval_runs`, etc. tables. Per-agent isolation requires `agent_id` filters at query time, not separate tables. (This already matches today's row schemas — see Section 2 of each surface block in `AUDIT.md`.)
- If a future requirement is "one agent must not see another agent's memory rows", we'd implement that with `agent_id`-scoped queries, not with separate DBs.

**Migration cost:** trivial. Existing rows already live in `ai.*`. Pinning the id is a string-literal addition; the rows are unaffected.

### Option B — Per-agent DBs with stable ids

```python
db_chat = PostgresDb(id="agent-chat", db_url=DSN_CHAT)       # or db_schema="chat"
db_curator = PostgresDb(id="agent-curator", db_url=DSN_CURATOR)
# ...one PostgresDb per agent, each with a stable user-supplied id
```

**Pros**
- Strong physical isolation between agents (separate DSNs or `db_schema=` namespaces).
- Per-agent backup/restore granularity.
- The dashboard would render a databases-selector with one entry per agent.

**Cons**
- Introduces 5 DSNs (or 5 schemas) where there is 1 today. Adds operational cost: provisioning, migration, monitoring, backup, secrets management.
- Every read endpoint (`/memories`, `/eval-runs`, etc.) now **requires** a `db_id` query param. The os.agno.com dashboard's existing requests would 400 until updated. The audit confirmed this failure mode is already happening for knowledge (`Available IDs: []`).
- Approvals router still uses `os_db` (`agno/os/routers/approvals/router.py:19`) — the operator must explicitly designate one of the five per-agent DBs as the "AgentOS-level" DB. Picking arbitrarily creates an asymmetry that's hard to justify.
- Migration cost: non-trivial. Existing rows in the single shared DB don't have an agent-attribution column granular enough to split — `agno_sessions.agent_id` exists but isn't a clean partition key for moving rows to per-agent DBs. Operator would inherit a SQL-level migration project.
- None of the four root-cause tags in `AUDIT.md` blames the single-DB architecture. Option B does **not** resolve any RC tag.

**Migration cost:** non-trivial (see above).

### Comparison

| Dimension | Option A (shared, pinned) | Option B (per-agent) |
|---|---|---|
| Code change | 1 line in `agentos/app.py` | New DSN/schema per agent + factory wiring |
| Migration | Zero data moves | Per-agent SQL split (no clean partition column) |
| Dashboard breakage on switch | None | Requests without `db_id` start 400ing |
| Approvals router | Works (os_db = the single DB) | Requires explicit "which one is os_db" pick |
| Resolves RC-memory-thin-usage | No (it's a usage signal) | No |
| Resolves RC-no-eval-harness | No (it's a missing-runner issue) | No |
| Resolves RC-knowledge-not-registered | No (it's a Knowledge-init silent fallback) | No |
| Resolves RC-no-hitl-trigger-yet | No (no agent has invoked a gated tool yet) | No |
| New operational surfaces | None | 5 DSNs/schemas, 5 migration paths |

## Chosen model + rationale

**Option A — Pin one shared `BaseDb.id` across all five agents.** Restated from the TL;DR.

Justification (5 sentences):

1. `AUDIT.md`'s matrix shows that **none of the four root-cause tags blames the single-DB architecture** — they blame thin usage, missing eval runner, unmigrated knowledge PG database, and no HITL trigger yet. Option B does not resolve any of them.
2. The dashboard *already works* for memory (operator-confirmed) and would only stop working if we moved to multi-DB without `db_id` plumbing in every caller (the audit captured this failure live at `/knowledge/content` returning `Available IDs: []`).
3. The approvals router (`agno/os/routers/approvals/router.py:19-41`) only uses `os_db`, so multi-DB introduces an arbitrary "which is the AgentOS-level DB" decision that has no defensible answer.
4. The 1-line code change is trivial and the migration is zero-data-move — operator can ship Option A as a precondition for phase 11 with no rollback risk.
5. If at any future point per-agent isolation is needed, Option A doesn't preclude it: a future plan can introduce per-agent DBs only for the agents that actually need isolation, without re-litigating today's decision.

### What this does NOT fix

Option A is a registration-model decision. It does **not** resolve any of:

- `RC-no-eval-harness` — phase 13 still needs to build an out-of-band eval runner (or upgrade Agno to a version that accepts `evals=` on `Agent`).
- `RC-knowledge-not-registered` — phase 12 still needs to diagnose why `VaultKnowledge` silently falls back to the empty stub and run the `agno_knowledge` migrations.
- `RC-no-hitl-trigger-yet` — phase 14 still needs to trigger a confirmation-gated tool in production and verify the approval row materializes.
- `RC-memory-thin-usage` — this is a usage signal, not a code change. No phase work required.

## Downstream consequences per phase

### Phase 11 (Memory activation)

**Amended 2026-05-22** — supersedes the earlier note that claimed phase 11's flag-flip was already done.

- All 6 agents pass `enable_agentic_memory=True` + `update_memory_on_run=True` (see `evidence/write-gate-grep.txt`). That is a **different** Agno mechanism from auto-extraction — it gives the agent a tool, but the agent has to *choose* to call it.
- The auto-extraction path (`enable_user_memories=True`, with an attached `MemoryManager` and a stable `user_id` per run) is **not** enabled — `grep -rn "enable_user_memories" agentos/` returns zero matches. The 1 row that exists in `ai.agno_memories` has `agent_id=null`, strongly indicating it was created via the UI "+ CREATE MEMORY" button or an explicit `db.upsert_user_memory()` call, not via an agent run.
- Phase 11's primary work is therefore to **enable `enable_user_memories=True`** on the agents whose conversations should leave a memory trace — most likely the Telegram-facing brief/chat agents (the ones with a stable per-user identity). The supervisor/curator/ingest agents may not need it.
- Phase 11's secondary work (precondition `DIAG-BL-01`): add `id="ultra-brain-main"` to the `PostgresDb` constructor in `agentos/app.py`. No agent factory signature change.
- Verify phase 11 success by:
  (a) running a real chat-agent conversation with memory-worthy content under a stable `user_id`, then querying `/memories` within 5 s (per ROADMAP success criterion 1) and confirming a new row appears with `agent_id` populated (proving the auto-extraction path fired, not just a manual UI add);
  (b) confirming `/config` reports `os_database="ultra-brain-main"` after redeploy.

### Phase 12 (Evals activation)

- The eval runner stays on the **same** shared DB (rows live in `ai.agno_eval_runs`).
- Phase 12's real work is independent of this decision: build a CLI / cron runner that calls `db.create_eval_run(...)` from `evals/conftest.py` or a new `scripts/run_evals.py`, or upgrade Agno to expose `evals=` on `Agent`.
- No new `id=` kwarg needed beyond the one Option A pins.

### Phase 13 (Knowledge activation)

- Knowledge stays on the shared PgVector instance (or `Knowledge` adapter); Option A does not split it.
- Phase 13's real work: (a) figure out why `VaultKnowledge` resolves to the empty stub at startup; (b) run the agno_knowledge migrations against `POSTGRES_DSN_KNOWLEDGE` (currently zero tables exist in that DB); (c) ensure the registered `Knowledge` instance shows up in `/knowledge/config` `Available IDs`. The `Knowledge` instance gets its own `id` (e.g. `id="ultra-brain-vault-kb"`) **distinct** from the `BaseDb.id`, but that's a separate registry (knowledge IDs, not db IDs).

### Phase 14 (Approvals activation)

- `agno/os/routers/approvals/router.py:19` uses `os_db` only. Under Option A, `os_db = db` (the single shared DB), which is the cleanest possible answer. No `db_id` query param applies to the `/approvals` endpoint.
- Phase 14's real work: trigger one of the four `requires_confirmation=True` tools (`agentos/tools/vault.py:35`, `vault.py:56`, `ingest.py:3`) in production via a real run, verify the row lands in `ai.agno_approvals`, and confirm `/approvals` surfaces it.

## Migration implications

- **Existing rows stay where they are.** Under Option A, the schema, table names, and row content are unchanged. Only the in-memory `BaseDb.id` field changes from a fresh UUID-per-process to the literal string `"ultra-brain-main"`.
- **External callers that cached the old UUID-shaped `db_id`** (e.g. an os.agno.com workspace that previously connected and remembered `e9a76996-9f0a-535a-bd92-c215f571af96`) will need to re-discover the new id once. This is a one-time, non-blocking effect — `/config` always returns the current id authoritatively.
- **Knowledge migration is orthogonal.** The `agno_knowledge` PG database (currently zero tables) needs its own migration regardless of Option A vs B; see phase 13 work above.

## Citations

| # | File | Lines | What it proves |
|---|---|---|---|
| 1 | `agno/db/base.py` | 56-72 | `self.id = id or str(uuid4())` plus default table-name fields. Establishes that `db_id` is a per-instance identifier and `agno_*` are the default table names — same names observed in `evidence/psql.txt`. |
| 2 | `agno/os/app.py` | 1049-1100 | `_auto_discover_databases()` builds the `self.dbs: Dict[str, List[BaseDb]]` registry keyed by `BaseDb.id` from every agent's `db=` arg. Proves the "shared object → one registry entry" semantics that make Option A trivial. |
| 3 | `agno/os/utils.py` | 246+ | `get_db()` resolution + the HTTP 400 raised when multiple DBs are registered and no `db_id` is supplied. Proves the dashboard breakage risk of Option B. |
| 4 | `agno/os/routers/approvals/router.py` | 19-41 | `get_approval_router(os_db, settings)` — the approval router uses `os_db` only. Proves Option B forces an arbitrary "which DB is AgentOS-level" pick. |
| 5 | `agentos/app.py` | 25-74 | Current single-shared-`db` wiring + `AgentOS(db=db, …)`. Proves the Option A change is 1 line. |
| 6 | `agentos/agents/chat.py` | 43-44 | `enable_agentic_memory=True`, `update_memory_on_run=True` (not `enable_user_memories`). Proves phase 11's flag-flip story is already done; what remains is the `id=` pin. |
