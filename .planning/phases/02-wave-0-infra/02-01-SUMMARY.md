---
phase: "02-wave-0-infra"
plan: "02-01"
subsystem: "infra"
tags: [postgres, pgvector, systemd, dependencies]
dependency_graph:
  requires: []
  provides: [postgres-service-unit, pgvector-deps]
  affects: [requirements.txt, .env.example]
tech_stack:
  added: [psycopg3, pgvector, sentence-transformers, a2a-sdk]
  patterns: [systemd service unit]
key_files:
  created:
    - ops/systemd/uab-postgres.service
  modified:
    - requirements.txt
    - .env.example
decisions:
  - Used psycopg[binary] for zero-build dependency on VPS
  - DSN format uses postgresql+psycopg:// for SQLAlchemy 2.x async compatibility
metrics:
  duration: "~5 minutes"
  completed: "2026-05-20"
  tasks_completed: 3
  files_changed: 3
---

# Phase 02 Plan 01: Postgres 16 + pgvector Infrastructure Summary

**One-liner:** Postgres 16 + pgvector systemd service unit with psycopg3/pgvector/sentence-transformers/a2a-sdk deps added to requirements.txt.

## What Was Done (Local File Changes)

1. **`ops/systemd/uab-postgres.service`** — Created systemd unit for Postgres 16 on Debian/Ubuntu VPS. Uses `pg_ctl` with standard `/var/lib/postgresql/16/main` data dir and logs to `/var/log/postgresql/uab-postgres.log`.

2. **`requirements.txt`** — Added four dependencies:
   - `psycopg[binary]>=3.2` — async Postgres driver (binary wheel, no build tools needed on VPS)
   - `pgvector>=0.3` — Python client for pgvector extension
   - `sentence-transformers>=3.0` — embedding model library for vault RAG
   - `a2a-sdk>=0.2` — Agent-to-Agent SDK for Wave 1+ multi-agent coordination

3. **`.env.example`** — Added two DSN env vars at end of file:
   - `POSTGRES_DSN_SESSIONS` — points to `agno_sessions` DB
   - `POSTGRES_DSN_KNOWLEDGE` — points to `agno_knowledge` DB

## Manual VPS Steps (Operator Must Run)

These steps cannot be automated by the executor — they require SSH access to the VPS.

### 1. Install Postgres 16 + pgvector

```bash
sudo apt update
sudo apt install -y postgresql-16 postgresql-16-pgvector
sudo systemctl enable --now postgresql
```

### 2. Create databases and install vector extension

```bash
sudo -u postgres psql <<'SQL'
CREATE DATABASE agno_sessions;
CREATE DATABASE agno_knowledge;
\c agno_sessions
CREATE EXTENSION IF NOT EXISTS vector;
\c agno_knowledge
CREATE EXTENSION IF NOT EXISTS vector;
SQL
```

### 3. Create app user with grants

```bash
sudo -u postgres psql <<'SQL'
CREATE USER uab WITH PASSWORD '<strong-password>';
GRANT ALL PRIVILEGES ON DATABASE agno_sessions TO uab;
GRANT ALL PRIVILEGES ON DATABASE agno_knowledge TO uab;
SQL
```

### 4. Deploy the systemd service unit

```bash
sudo cp ops/systemd/uab-postgres.service /etc/systemd/system/uab-postgres.service
sudo systemctl daemon-reload
sudo systemctl enable --now uab-postgres
sudo systemctl status uab-postgres
```

> Note: On a standard Debian/Ubuntu install, the system Postgres service (`postgresql`) and this custom unit both point to the same data dir. You may prefer to just use `postgresql.service` directly and skip copying the unit. The unit is provided for explicitness.

### 5. Set env vars on VPS

Copy `.env.example` lines and replace `<password>` with the real password in the VPS `.env` file.

## Verification Commands (After VPS Steps)

```bash
# Test connections from app user
psql postgresql://uab:<password>@127.0.0.1:5432/agno_sessions -c "SELECT extname FROM pg_extension WHERE extname='vector';"
psql postgresql://uab:<password>@127.0.0.1:5432/agno_knowledge -c "SELECT extname FROM pg_extension WHERE extname='vector';"

# Confirm service is running
sudo systemctl status uab-postgres

# Smoke-test from Python (after pip install)
python -c "import psycopg; print('psycopg ok')"
python -c "import pgvector; print('pgvector ok')"
```

## Deviations from Plan

None — plan executed exactly as written. Pre-existing test failures noted (unrelated to this plan's changes).

## Self-Check: PASSED

- `ops/systemd/uab-postgres.service` — FOUND
- `requirements.txt` updated with 4 new deps — FOUND
- `.env.example` updated with POSTGRES_DSN_* vars — FOUND
- Commit `a7e3570` — FOUND

---

## VERIFICATION (2026-05-20)

**Overall: PASS**

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | `ops/systemd/uab-postgres.service` exists with valid systemd syntax | PASS | All four required sections present (`[Unit]`, `[Service]`, `[Install]`); `ExecStart`/`ExecStop`/`Restart` all set |
| 2 | `requirements.txt` contains psycopg[binary]>=3.2, pgvector>=0.3, sentence-transformers>=3.0, a2a-sdk>=0.2 | PASS | All four lines confirmed present verbatim |
| 3 | `.env.example` contains POSTGRES_DSN_SESSIONS and POSTGRES_DSN_KNOWLEDGE | PASS | Both entries present with correct DSN format (`postgresql+psycopg://`) |
| 4 | SUMMARY.md exists at `.planning/phases/02-wave-0-infra/02-01-SUMMARY.md` | PASS | File present and complete |
| 5 | Commit `a7e3570` exists with `feat(infra)` message | PASS | `feat(infra): add Postgres 16 + pgvector service for v1.5 reconfiguration` |
| 6 | Existing tests pass (`pytest tests/`) | PASS | 47 passed (plan expected 38; suite grew in intervening commits). Must run via `.venv/bin/python` — system Python lacks project deps |
| VPS: install postgres, create DBs/users, deploy unit | pending-operator | Cannot be verified programmatically; SSH access required |

**Notes:**
- Test runner must be invoked as `.venv/bin/python -m pytest tests/` — the system Python lacks `httpx`, `agno`, `psycopg` etc. Using bare `pytest` or `python` produces import errors unrelated to this phase's changes.
- 47 tests pass (not 38 as the plan anticipated) because the test suite grew across other commits in the same milestone.
