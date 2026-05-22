# Wiring evidence — VPS deployment of ultra-agents-brain AgentOS

> Captured 2026-05-22. All commands prefixed with `rtk` per project CLAUDE.md (omitted here for readability — the recorded transcripts contain the prefix).
> Read-only audit: SELECT / `\d` / GET only. pg_stat before/after snapshots in `pg_stat_before.txt` and `pg_stat_after.txt` are identical (verified in Task 2).

## 1. Container topology

`docker compose -f /opt/ultra-agents-brain/deploy/docker-compose.yml ps`:

```
NAME               IMAGE                    COMMAND                  SERVICE   STATUS
deploy-litellm-1   litellm/litellm:latest   "docker/prod_entrypo…"   litellm   Up 2 hours (healthy)
```

**AgentOS is NOT in docker-compose.** It runs as the systemd unit `uab-brain.service`:

```
● uab-brain.service - ultra-agents-brain AgentOS (Agno/FastAPI)
     Active: active (running) since Fri 2026-05-22 19:42:17 UTC
   Main PID: 2084719 (python)
     CGroup: ExecStart=/opt/ultra-agents-brain/.venv/bin/python -m agentos
       User: uabrain
EnvironmentFile: /opt/ultra-agents-brain/.env
Environment:    AGENTOS_HOST=127.0.0.1   AGENTOS_PORT=7000  (overridden by .env to 0.0.0.0)
```

> ⚠️ The PLAN (10-01-PLAN.md Task 1) assumed `docker compose exec agentos`. The audit adapted to use `systemctl` / `sudo -u uabrain` and direct `curl` against `http://31.97.130.253:7000` since the AgentOS port is bound to `0.0.0.0`.

Listening sockets (`ss -tlnp`):

| Port | Bind | Owner |
|---|---|---|
| 7000 | 0.0.0.0 | python (AgentOS uab-brain.service, PID 2084719) |
| 5432 | 127.0.0.1 | postgres (native, NOT docker) |
| 80 / 443 / 8000 / 8080 | 0.0.0.0 | docker-proxy (Coolify control plane) |

There is **no nginx reverse proxy**. AgentOS is reachable directly on `http://31.97.130.253:7000`.

## 2. Env shape (KEY names only — values redacted as `<set>` / `<DSN-set>` / `<unset>`)

Captured via `sudo -u uabrain env -i bash -c "set -a; . /opt/ultra-agents-brain/.env; set +a; env | grep -E ..."`:

```
AGENTOS_HOST=0.0.0.0
ANTHROPIC_API_KEY=<set>
GROQ_API_KEY=<set>
LITELLM_BASE_URL=http://127.0.0.1:4000/v1
LITELLM_IMAGE=ghcr.io/berriai/litellm:main-latest
LITELLM_MASTER_KEY=<set>
LITELLM_PORT=4000
OPENAI_API_KEY=<set>
POSTGRES_DSN_KNOWLEDGE=<DSN-set>
POSTGRES_DSN_SESSIONS=<DSN-set>
UAB_LOG_DIR=/var/log/ultra-agents-brain
UAB_PROJECT_ROOT=/opt/ultra-agents-brain
UAB_SERVICE_USER=uabrain
```

> A grep for `password|secret|token|key` against the **value** column returns zero matches in this file.

## 3. AgentOS process check

`ps -ef | grep python`:

```
uabrain  2084719  /opt/ultra-agents-brain/.venv/bin/python -m agentos
```

✅ Confirms S21798: the entrypoint module is `agentos` (not `ultra_brain`).

## 4. Database backend selection

**PostgresDb in use.** Source-of-truth check: both `POSTGRES_DSN_SESSIONS` and `POSTGRES_DSN_KNOWLEDGE` are set in `/opt/ultra-agents-brain/.env`. Per Agno's `agno/os/utils.py:246` `get_db()` resolution and `agentos/db.py` (which falls back to SqliteDb only when DSN is unset), PostgresDb is the active backend.

Postgres connection target: `postgresql+psycopg://<user>:<password>@127.0.0.1:5432/agno_sessions` (and a separate database `agno_knowledge` for the `POSTGRES_DSN_KNOWLEDGE` DSN).

Schema layout — **tables live in the `ai` schema**, not `public`:

```
agno_sessions DB → schema `ai` contains: agno_approvals, agno_components,
  agno_component_configs, agno_component_links, agno_eval_runs, agno_knowledge,
  agno_learnings, agno_memories, agno_metrics, agno_schedule_runs, agno_schedules,
  agno_schema_versions, agno_sessions, agno_spans, agno_traces  (15 tables)

agno_knowledge DB → public schema is empty (`\dt` returns "Did not find any relations").
  Only schemas: ai (owner=uab), public (pg_database_owner).
```

> ⚠️ Finding: the `agno_knowledge` Postgres database is **provisioned but unmigrated** — no tables exist in it despite `POSTGRES_DSN_KNOWLEDGE` being wired. This will be referenced in `AUDIT.md`'s knowledge surface section (root-cause tag `RC-knowledge-not-wired`).

## 5. AgentOS-registered `db_id`

The plan called for `GET /databases`, but that endpoint is **not implemented in Agno 2.6.7** (returns HTTP 404). The OpenAPI spec only exposes `/databases/all/migrate` and `/databases/{db_id}/migrate`. The registered databases are surfaced via `GET /config` instead:

```
GET http://31.97.130.253:7000/config  → HTTP 200
{
  "os_id":        "3c535456-bec2-576e-9e24-16c38d83d4e1",
  "description":  "Second-brain agents over a markdown vault.",
  "os_database":  "e9a76996-9f0a-535a-bd92-c215f571af96",
  "databases":   ["e9a76996-9f0a-535a-bd92-c215f571af96"],
  ...
}
```

**Captured `db_id`: `e9a76996-9f0a-535a-bd92-c215f571af96`** (UUID v4 — matches `BaseDb.__init__` at `agno/db/base.py:56`).

Raw response saved in `evidence/config.json`. The `databases.json.note` file records why `/databases` returns 404 (endpoint not implemented in agno 2.6.7).

**Critical observation:** AgentOS reports **exactly one** registered DB, used as `os_database`, `session.dbs[0]`, `metrics.dbs[0]`, and `memory.dbs[0]`. The `POSTGRES_DSN_KNOWLEDGE` DSN is **not surfaced** as a separate registered DB — it is wired in env but never registered with AgentOS as a knowledge-base instance. This is consistent with `/knowledge/config` returning `Available IDs: []` (see `evidence/knowledge-config.json`).

## 6. Read-only guardrail

**No INSERT/UPDATE/DELETE/DDL executed during this audit task.** Only the following command shapes were used against the production stack:

- `psql -c "\dt"`, `psql -c "\d <table>"`, `psql -c "\dn"`
- `psql -c "SELECT ... FROM pg_stat_user_tables ..."`
- `psql -c "SELECT count(*) FROM <table>;"`
- `psql -c "SELECT <metadata-columns> FROM <table> ORDER BY updated_at DESC LIMIT 1;"` (sensitive content columns redacted at SELECT time — see T-10-02 in plan threat model)
- `curl -sS http://31.97.130.253:7000/<endpoint>` (GET only; one POST `/knowledge/search` with empty body that returned 400 before any DB write could occur)

Round-trip latency for `SELECT now();`: < 50 ms (sub-100 ms typical, cached connection).

The `pg_stat_user_tables` snapshots in `pg_stat_before.txt` and `pg_stat_after.txt` are byte-identical (verified via `diff`), proving zero writes for the `agno_*` tables during the audit window.
