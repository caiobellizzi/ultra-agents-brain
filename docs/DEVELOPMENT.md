<!-- generated-by: gsd-doc-writer -->
# Development Guide

This guide covers the full local development workflow for `ultra-agents-brain`: from first clone through running tests and evals to common day-to-day tasks.

---

## Prerequisites

- Python 3.13 (see `Dockerfile` `FROM` line and `.venv/` layout)
- `pre-commit` (installed into the venv — see below)
- A running LM Studio instance with a loaded model if you want live LLM calls locally (the `private-worker` tier)
- Optional: a PostgreSQL instance for the sessions/knowledge DB surfaces; most smoke tests run without it

---

## Local Setup

```bash
# 1. Clone
git clone <repo-url>
cd ultra-agents-brain

# 2. Create and activate a virtual environment
python3.13 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Copy the example env and fill in secrets
cp .env.example .env
# Edit .env — at minimum set LITELLM_MASTER_KEY and LM_STUDIO_API_BASE

# 5. Install pre-commit hooks
pre-commit install
```

---

## First Run

Start the AgentOS FastAPI server:

```bash
PYTHONPATH=. python -m agentos
```

The server binds to `127.0.0.1:7000` by default. Override with env vars:

```bash
AGENTOS_HOST=0.0.0.0 AGENTOS_PORT=7001 python -m agentos
```

---

## Build Commands

| Command | Description |
|---|---|
| `make test` | Run the unit test suite (excludes `tests/test_core.py`) |
| `make eval-smoke` | Run smoke-tier evals (zero LLM calls) |
| `make eval-full` | Run the full eval suite using the orchestrator judge tier |
| `make check-surfaces` | Check all agent surface registrations via `scripts/check_surfaces.py` |

---

## Code Style

Linting and formatting are enforced by the pre-commit hook defined in `.pre-commit-config.yaml`. Run the full hook set manually with:

```bash
pre-commit run --all-files
```

The project currently uses no standalone ESLint/Prettier/Biome config — style enforcement is handled through the pre-commit setup.

---

## Pre-Commit Hooks

`.pre-commit-config.yaml` registers a single local hook: `scoped-evals`, backed by `tools/precommit_eval_router.sh`.

**What it does:** On each commit, the router inspects staged files and runs the corresponding scoped eval file(s) at the `smoke` tier. Smoke tests make zero LLM calls and complete in under a second.

| Staged file | Eval(s) triggered |
|---|---|
| `agentos/agents/chat.py` | `evals/test_chat.py` |
| `agentos/agents/curator.py` | `evals/test_curator.py` |
| `agentos/agents/ingest.py` | `evals/test_ingest.py` |
| `agentos/agents/query.py` | `evals/test_query.py` |
| `agentos/agents/research.py` | `evals/test_research.py` |
| `agentos/agents/supervisor.py` | `evals/test_supervisor.py` |
| `agentos/knowledge.py` | `evals/test_query.py` + `evals/test_research.py` |
| `agentos/model.py`, `agentos/app.py`, `agentos/schemas.py` | Full `evals/` suite |

If no relevant agent files are staged the hook exits 0 and skips evals entirely.

---

## Running Tests

### Unit tests

```bash
PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_core.py -q
# or via make:
make test
```

### Eval suite — smoke tier (no LLM calls)

```bash
PYTHONPATH=. .venv/bin/pytest evals/ -k smoke -q
# or via make:
make eval-smoke
```

### Eval suite — full (live LLM judge)

```bash
EVAL_JUDGE_TIER=orchestrator PYTHONPATH=. .venv/bin/pytest evals/ -q
# or via make:
make eval-full
```

### Single eval file

```bash
PYTHONPATH=. .venv/bin/pytest evals/test_chat.py -q
```

### Writing eval results to Postgres

Set `POSTGRES_DSN_SESSIONS` in `.env`. When the env var is present, the `eval_db` fixture in `evals/conftest.py` connects to Postgres and the per-test `eval_recorder` fixture writes an `EvalRunRecord` to `ai.agno_eval_runs` after each test completes.

---

## Test Markers

Defined in `pytest.ini`:

| Marker | Meaning |
|---|---|
| `smoke` | Fast schema-level assertions — no LLM calls. Always safe to run. |
| `integration` | Full agent runs — requires live services (LiteLLM, Postgres). |
| `live` | Integration tests that require a deployed VPS — skip in unit-CI runs. |

Select a tier:

```bash
pytest evals/ -k smoke          # smoke only
pytest evals/ -k integration    # integration only
pytest evals/ -k "not live"     # everything except VPS tests
```

---

## Eval System Development Workflow

The eval system has two layers: a **recorder** that captures live traffic and a **live judge** that scores captured rows.

### How eval runs are recorded

`agentos/eval_recorder.py` (`InstrumentedEvalRecorder`) monkey-patches `Agent.run` and `Agent.arun` at class level when the server starts (wired in `agentos/app.py` via `patch_classes_for_recording`). After every completed run it writes one `EvalRunRecord` of type `PERFORMANCE` to the eval DB. Fields written include `agent_id`, `latency_ms`, `model_id`, `output`, and `judge_status=pending`.

Key behaviour:
- Paused HITL responses are **not** recorded (the row is written only after the resumed run completes).
- Error runs get `status=error` and are not queued for judging.
- The `_extract_model` helper resolves `model_id` and `model_provider` from the Agno response object.

### How to run the live judge manually

The live judge reads pending rows from the eval DB, scores them using the configured rubric, and writes a child `AGENT_AS_JUDGE` row:

```bash
# Run one pass (default: scan up to 10 rows)
PYTHONPATH=. python -m agentos live-judge --once

# Run one pass scanning up to 50 rows
PYTHONPATH=. python -m agentos live-judge --once --limit 50

# Run continuously (sleep 60 s between passes)
PYTHONPATH=. python -m agentos live-judge --loop --interval 60
```

The judge is off by default. Enable it for local development:

```bash
EVAL_LIVE_JUDGE_ENABLED=true EVAL_LIVE_SAMPLE_RATE=1.0 python -m agentos live-judge --once
```

In production, the judge runs via the `uab-live-judge.timer` systemd timer (every 2 minutes, `--once --limit 20`). The relevant env vars in `.env.example` are:

```
EVAL_LIVE_JUDGE_ENABLED=false      # set to true on VPS
EVAL_LIVE_SAMPLE_RATE=0.0          # 1.0 = score every row
```

### Live rubrics

Rubrics live in `agentos/eval_rubrics.py`. Current rubrics:

| Rubric ID | Agent | Strategy |
|---|---|---|
| `chat-helpfulness-v1` | chat | binary |
| `query-groundedness-v1` | query | numeric |
| `ingest-fidelity-v1` | ingest | numeric |
| `curator-quality-v1` | curator | numeric |
| `research-grounding-v1` | research | numeric |

### Inspecting eval results in the database

**SQLite (local dev)** — the eval DB defaults to `~/Documents/uab-state/agno.db` (override with `UAB_DB_PATH`):

```bash
sqlite3 ~/Documents/uab-state/agno.db \
  "SELECT run_id, agent_id, name, score FROM agno_eval_runs ORDER BY created_at DESC LIMIT 20;"
```

**Postgres (production)** — eval rows live in schema `ai`, table `agno_eval_runs`:

```sql
-- Recent scored rows
SELECT run_id, agent_id, name, score, created_at
FROM ai.agno_eval_runs
WHERE score IS NOT NULL
ORDER BY created_at DESC
LIMIT 20;

-- Pending rows (not yet judged)
SELECT count(*), agent_id
FROM ai.agno_eval_runs
WHERE eval_data->>'judge_status' = 'pending'
GROUP BY agent_id;
```

---

## Experience Notes

After the live judge scores a row, it writes a structured **experience note** to the vault so agents can learn from past runs.

### Where they are written

```
vault/_system/experiences/{agent_id}/{date}-{run_id}.md
```

Example path:

```
vault/_system/experiences/chat/2026-05-29-dd1844f6.md
```

The `SECOND_BRAIN_DIR` env var controls the vault root (defaults to `"vault"` in local dev; `/srv/second-brain` on VPS).

### Note format

```markdown
---
agent: chat
run_id: <run_id>
score: 1.0
rubric: chat-helpfulness-v1
status: success
date: 2026-05-29
tags: [experience, chat]
---

## Input
<truncated user message or input dict>

## Score
1.0 — passed ✓

## What worked
<judge reasoning>

## Key pattern
<judge reasoning>
```

### How to review experience notes

```bash
# List all experience notes for a specific agent
ls vault/_system/experiences/chat/

# View the most recent experience note
ls -t vault/_system/experiences/chat/ | head -1 | xargs -I{} cat vault/_system/experiences/chat/{}
```

After writing a note the live judge calls `reindex()` immediately, so the experience is searchable in the vault on the next agent run.

---

## Agentic Culture

All five specialist agents (`chat`, `ingest`, `query`, `research`, `curator`) have `enable_agentic_culture=True` in their `Agent(...)` constructor.

**What it does:** Agno's `CultureManager` (from `agno.culture.manager`) accumulates `CulturalKnowledge` rows in the agent's SQLite/Postgres DB across runs. At the start of each run, relevant cultural knowledge is injected into the agent's context window alongside memory summaries.

**Important:** `enable_agentic_culture` is an `Agent`-level feature in Agno 2.x. The `supervisor` `Team` does not have it — only the member agents do.

**The culture KB is automatically updated** — no manual step is needed. Agno extracts and persists culture entries after each agent run when the feature is enabled. The DB used is the shared `db` singleton from `agentos/db.py` (SQLite at `UAB_DB_PATH` locally; Postgres when `POSTGRES_DSN_SESSIONS` is set).

To inspect culture entries for a given agent (Postgres):

```sql
SELECT agent_id, content, created_at
FROM ai.agno_cultural_knowledge
WHERE agent_id = 'chat'
ORDER BY created_at DESC
LIMIT 10;
```

---

## Branch Conventions

No formal convention is documented in this repo. The default branch is `main`.

---

## PR Process

No `.github/PULL_REQUEST_TEMPLATE.md` is present. Follow standard practice:
- Keep PRs to one logical change
- Ensure `make test` and `make eval-smoke` pass before opening a PR
- Reference the relevant plan file in `plans/` in the PR description if the change implements a planned feature
