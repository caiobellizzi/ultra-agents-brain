# Plan 10-01 SUMMARY — diagnostic audit (READ-ONLY)

**Phase:** 10-diagnostic-audit  
**Plan:** 01  
**Status:** Complete (operator-driven interactive execution)  
**Date:** 2026-05-22

## What this plan produced

- `.planning/phases/10-diagnostic-audit/AUDIT.md` — full surface audit with top-matrix + 5-section block per surface + Appendix A read-only attestation.
- `.planning/phases/10-diagnostic-audit/evidence/` — 16 files:
  - `wiring.md` — topology, env shape (redacted), DB backend, `db_id`, read-only guardrail.
  - `config.json`, `info.json`, `agents.json` — AgentOS introspection (HTTP 200).
  - `memories.json`, `memories-with-id.json`, `eval-runs.json`, `eval-runs-with-id.json`, `approvals.json`, `approvals-with-id.json` — raw surface API responses (HTTP 200 / 400 / 404 as recorded).
  - `knowledge-content.json`, `knowledge-content-with-id.json`, `knowledge-config.json`, `knowledge-search.json` — knowledge surface (HTTP 400/404 — root-cause evidence).
  - `psql.txt` — `\dt`, `\d <table>`, `SELECT count(*)`, redacted-column `SELECT … LIMIT 1` per surface table, plus `\dn` schema discovery.
  - `pg_stat_before.txt` / `pg_stat_after.txt` — byte-identical (read-only attestation).
  - `pg_knowledge_before.txt` — confirms the `agno_knowledge` Postgres DB has zero tables.
  - `write-gate-grep.txt` — `requires_confirmation=True` + `enable_agentic_memory=True` matches across `agentos/`.
  - `databases.json.note` — explains why `GET /databases` returns 404 in agno 2.6.7.

## 1. Active DB backend

**PostgresDb.** Both `POSTGRES_DSN_SESSIONS` and `POSTGRES_DSN_KNOWLEDGE` are set in `/opt/ultra-agents-brain/.env`. Postgres runs **natively on the VPS** (not in docker), at `127.0.0.1:5432`. Two databases: `agno_sessions` (15 agno tables, schema `ai`) and `agno_knowledge` (empty — 0 tables).

AgentOS itself runs as `systemd:uab-brain.service` (`/opt/ultra-agents-brain/.venv/bin/python -m agentos`), listening on `0.0.0.0:7000`. Only LiteLLM is in docker-compose.

## 2. Captured `db_id`

`e9a76996-9f0a-535a-bd92-c215f571af96` — captured from `GET /config` (the plan's `GET /databases` path returns 404 in agno 2.6.7; only `/databases/{db_id}/migrate` exists in this version's OpenAPI).

This is the **single** registered DB — used as `os_database`, `session.dbs[0]`, `metrics.dbs[0]`, and `memory.dbs[0]`. The `POSTGRES_DSN_KNOWLEDGE` DSN is **not surfaced** as a separate registered DB.

## 3. Row counts per surface (from `evidence/psql.txt`)

| Surface | Table (in schema `ai`) | Row count | pg_stat n_tup_ins |
|---|---|---|---|
| memory | `agno_memories` | **1** | 1 |
| evals  | `agno_eval_runs` | **0** | 0 |
| knowledge | `agno_knowledge` (Agno content registry) | **0** | 0 |
| knowledge (vector store) | tables in `agno_knowledge` DB | **0 tables exist** | — |
| approval | `agno_approvals` | **0** | 0 |

## 4. Root-cause tags (stable identifiers for phases 11–14)

- `RC-memory-thin-usage` — memory surface **working**, single row reflects production traffic (only `user_id=workshop`). No wiring change needed; this is a usage signal.
- `RC-no-eval-harness` — `agno_eval_runs` empty because nothing invokes `db.create_eval_run`. The installed Agno version does not accept `evals=` on `Agent` (see `agentos/agents/chat.py:75-77`), so the `citation_judge` is constructed but unused (`_ = citation_judge`). Phase 13 needs an out-of-band runner or an Agno upgrade.
- `RC-knowledge-not-registered` — `/knowledge/config` returns `Available IDs: []` despite `AgentOS(knowledge=[kb], …)`; the `agno_knowledge` Postgres DB has zero tables. Phase 12 needs to (a) diagnose why `VaultKnowledge` silently falls back to the empty stub and (b) run the PgVector/Agno knowledge migrations against `POSTGRES_DSN_KNOWLEDGE`.
- `RC-no-hitl-trigger-yet` — `agno_approvals` empty even though 4 tools are `requires_confirmation=True`. No agent has invoked a confirmation-gated tool in production yet. Phase 14 must trigger one and verify the row materializes; if it doesn't, escalate to `RC-hitl-write-broken`.

## 5. Surprises encountered

- `GET /databases` returns **HTTP 404** in agno 2.6.7. The plan/RESEARCH assumed it existed; only `/databases/{db_id}/migrate` is exposed. Workaround: read `databases` array from `GET /config`. *(documented in `evidence/databases.json.note` and inline in `wiring.md` section 5)*
- AgentOS does **not** run in docker on this VPS — it runs as `systemd:uab-brain.service` with the agentos venv. The plan assumed `docker compose exec agentos`. All commands were adapted to use `sudo -u uabrain` / direct curl / direct ssh. *(no rewrite of the plan was needed — Task 1's `wiring.md` records the deviation explicitly.)*
- Agno tables live in the **`ai` schema**, not `public`. Initial `\d agno_memories` ran from `public` and reported "relation does not exist". Re-queried with `\dn` and `pg_stat_user_tables.schemaname` to discover the schema. *(captured in `psql.txt` under SCHEMA DISCOVERY.)*
- The `POSTGRES_DSN_KNOWLEDGE` database exists but is **completely unmigrated** (zero tables in both `public` and `ai` schemas). This is the strongest single piece of evidence for `RC-knowledge-not-registered`.
- Operator deferred 4 UI screenshots, then manually confirmed dashboard state: memory **shows data**, evals/knowledge/approvals **show no data** — matches the API evidence exactly. UI is faithfully reflecting backend state, not a stale-cache or db_id-mismatch UI bug.
- The `JWT` authentication path was not exercised: AgentOS is open on this deployment (`GET /memories` etc. return 200 without an `Authorization` header). Phase 10 did not investigate whether that is intentional; flagged for phase 15 (security/backlog) consideration.

## Read-only attestation

`pg_stat_user_tables` snapshots before/after are byte-identical — see Appendix A of `AUDIT.md` and the raw `pg_stat_before.txt` / `pg_stat_after.txt` files. **Zero INSERT / UPDATE / DELETE / DDL executed during the audit window.**

A secrets check across the entire `evidence/` directory:

```
$ rtk grep -E "password|secret|Bearer eyJ|postgresql://[^*]+:[^*]+@" .planning/phases/10-diagnostic-audit/
(zero matches)
```

→ No secrets leaked into committed files.

## What blocks plan 10-02

Nothing. Plan 10-02 can consume:
- The four root-cause tags above
- The matrix table in `AUDIT.md`
- The observation that only one `db_id` is currently registered (basis for the per-agent vs shared-workspace decision)

to produce `DB-ID-DECISION.md` and `BACKLOG.md`.
