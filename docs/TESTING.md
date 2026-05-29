<!-- generated-by: gsd-doc-writer -->
# Testing

This document covers two audiences:

- **Contributors** — how to run unit tests and eval smoke suites locally.
- **Operators** — how the live eval judge scores production traffic and how to inspect results.

---

## Test framework and setup

The project uses **pytest** (Python). Two separate test roots exist:

| Root | Purpose |
|------|---------|
| `tests/` | Unit and integration tests for `agentos.*` internals |
| `evals/` | Agent schema smoke tests + parametrized integration evals |

**Markers** (defined in `pytest.ini`):

| Marker | Meaning |
|--------|---------|
| `smoke` | Fast schema-level assertions; zero LLM API calls. Safe for CI. |
| `integration` | Full agent runs; requires live services and `POSTGRES_DSN_SESSIONS`. |
| `live` | Requires a deployed VPS. Skip in unit-CI runs. |

**Prerequisites** before any test run:

```bash
# Install dependencies
.venv/bin/pip install -e ".[dev]"

# Required env var (set automatically by conftest if unset — but explicit is safer)
export LITELLM_MASTER_KEY=test-key-for-evals
```

`POSTGRES_DSN_SESSIONS` is optional for smoke runs. Set it when you need eval rows
written to Postgres or when running integration tests.

---

## Running tests

### Unit tests (`tests/`)

```bash
# All unit tests (excludes the slow test_core.py)
make test

# Equivalent manual command
PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_core.py -q
```

### Eval smoke suite (`evals/`)

```bash
# Smoke only — no LLM calls, runs in seconds
make eval-smoke

# Equivalent manual command
PYTHONPATH=. .venv/bin/pytest evals/ -k smoke -q
```

### Full eval suite with LLM judge

```bash
# Full evals — uses orchestrator-tier model as judge, writes rows to Postgres
make eval-full

# Equivalent manual command
EVAL_JUDGE_TIER=orchestrator PYTHONPATH=. .venv/bin/pytest evals/ -q
```

### Single test file

```bash
PYTHONPATH=. .venv/bin/pytest evals/test_supervisor.py -q
PYTHONPATH=. .venv/bin/pytest tests/unit/test_live_judge.py -v
```

### Baseline management

The eval suite supports writing and updating score baselines stored in `evals/baselines/`:

```bash
# Write new baselines (first run on a new agent)
PYTHONPATH=. .venv/bin/pytest evals/ --write-baseline -q

# Update existing baselines with new scores
PYTHONPATH=. .venv/bin/pytest evals/ --update-baseline -q
```

Baseline JSON files live at `evals/baselines/{name}.json`. When
`--write-baseline` or `--update-baseline` is active, the EVAL-02 suite write
path (Postgres row write) is skipped to avoid double-writing.

---

## Test file inventory

### `evals/` — agent eval suite

| File | Coverage area | Key fixtures |
|------|--------------|--------------|
| `evals/test_chat.py` | `ChatReply` schema; `text`, `citations`, `suggested_actions` fields | `eval_recorder` |
| `evals/test_curator.py` | `CuratorResult` schema; `actions_taken`, `notes_touched`, `errors` fields | `eval_recorder`, `eval_db`, `judge_model` |
| `evals/test_ingest.py` | `IngestResult` schema; `note_path`, `frontmatter`, `tags`, `needs_review` fields | `eval_recorder` |
| `evals/test_query.py` | `QueryAnswer` schema; `answer`, `citations`, `confidence` fields | `eval_recorder` |
| `evals/test_research.py` | `ResearchReport` schema; `topic`, `findings`, `next_questions`, `Finding` object | `eval_recorder` |
| `evals/test_supervisor.py` | `SupervisorRouting` schema; `chosen_member`, `reason`, `response` fields; valid agent set | `eval_recorder` |

Each file has the same two-layer structure:
1. **Smoke tests** (`@pytest.mark.smoke`) — import the schema, assert field names exist, instantiate with minimal data. No network, no LLM.
2. **Integration tests** (`@pytest.mark.integration`) — parametrized from `evals/datasets/{agent}_cases.py`, call `eval_recorder()` to emit a scored row.

### `tests/` — agentos internals

| File | Coverage area |
|------|--------------|
| `tests/test_agentos.py` | Full AgentOS app bootstrap and agent wiring |
| `tests/test_approval_recorder.py` | HITL approval flow recording |
| `tests/test_telegram_adapter.py` | Telegram adapter surface |
| `tests/unit/test_eval_recorder.py` | `InstrumentedEvalRecorder` sync/async wrap, OBS-01 log schema, error swallow |
| `tests/unit/test_live_judge.py` | `run_live_judge_once` child row write, privacy skip logic |
| `tests/unit/test_eval_suite_hook.py` | `pytest_runtest_makereport` hook, EVAL-02 suite write path |
| `tests/unit/test_eval_live_policy.py` | Sample-rate gate, privacy filter, `EvalLivePolicy.from_env()` |
| `tests/unit/test_agent_factories.py` | Agent factory construction |
| `tests/unit/test_brief.py` | Brief generation logic |
| `tests/unit/test_knowledge_reindex.py` | Knowledge base reindex |
| `tests/unit/test_live_judge.py` | Judge child row construction, privacy gate |
| `tests/unit/test_sync_vault.py` | Vault sync surface |
| `tests/unit/test_vault_trash.py` | Vault trash operations |
| `tests/integration/test_eval_suite_surface.py` | End-to-end eval surface with live Postgres |
| `tests/integration/test_memory_surface.py` | Memory surface with live Postgres |

---

## Conftest fixtures

### `evals/conftest.py`

| Fixture | Scope | Description |
|---------|-------|-------------|
| `judge_model` | session | `chat_model(EVAL_JUDGE_TIER)` — LM Studio by default, override with `EVAL_JUDGE_TIER=orchestrator` |
| `eval_db` | session | `PostgresDb(POSTGRES_DSN_SESSIONS)` if env set; `None` otherwise (smoke-safe) |
| `eval_test_run_id` | session | Git identity string (`<short-sha>` or `<sha>+dirty:<hash>`) — stable across a run |
| `eval_recorder` | function | Per-test recorder callable; captures `score`, `output`, `eval_input`, `agent_id`, `case_id`. The `pytest_runtest_makereport` hook reads this after each test call and writes one `EvalRunRecord` (type `ACCURACY`) to Postgres when `eval_db` is set. |
| `write_baseline` | session | `True` when `--write-baseline` CLI flag is passed |
| `update_baseline` | session | `True` when `--update-baseline` CLI flag is passed |

**`eval_test_run_id` construction:** SHA of HEAD (`--short=12`). If any file under
`agentos/`, `evals/`, `tests/`, `ultra_brain/`, or `skills/` is dirty or untracked,
a `+dirty:<sha256[:12]>` suffix is appended so dirty runs are never confused with
clean commits in the database.

### `tests/conftest.py`

| Fixture | Scope | Description |
|---------|-------|-------------|
| `tmp_vault` | function | Creates a temporary vault dir and sets `VAULT_PATH` env var to it |
| `live_postgres_dsn_knowledge` | function | Skips the test if `POSTGRES_DSN_KNOWLEDGE` is not set |
| `live_postgres_dsn_sessions` | function | Skips the test if `POSTGRES_DSN_SESSIONS` is not set |

---

## Live eval judge system

The live eval system runs in production alongside the agents. It has three components:

### 1. Eval recorder (`agentos/eval_recorder.py`)

`InstrumentedEvalRecorder` wraps every agent's `run()` / `arun()` and `continue_run()` / `acontinue_run()` methods. After each successful (non-streaming, non-background, non-paused) call it writes one `EvalRunRecord` with `eval_type=PERFORMANCE` to `ai.agno_eval_runs`.

The record contains:
- `run_id` — taken from the Agno response, or a fresh UUID if absent
- `eval_input` — `{"user_message": "<first positional arg or 'message' kwarg>"}`
- `eval_data.output` — `response.content.model_dump()` (or raw content)
- `eval_data.latency_ms` — wall-clock ms
- `eval_data.model_id` / `model_provider` — from `response.model`
- `eval_data.score` — always `None` at write time (scoring is deferred to the judge)
- `eval_data.status` — `"ok"` or `"error"`

If `EVAL_LIVE_JUDGE_ENABLED=true` and the sample-rate gate passes, the recorder also stamps:
- `eval_data.judge_status = "pending"`
- `eval_data.judge_attempts = 0`
- `eval_data.judge_rubric_ids = [<rubric_id>, ...]`

These three fields act as the work queue consumed by the live judge worker.

`patch_classes_for_recording(db)` patches `Agent` and `Team` at the class level so
Agno's `deep_copy()` (which creates a fresh instance per HTTP request) inherits
the instrumentation automatically.

**Streaming and background paths are not recorded.** Only `stream=False` calls — the
AgentOS standard for `/agents/{id}/runs` — go through the instrumented path.

### 2. Live judge worker (`agentos/live_judge.py`)

`run_live_judge_once(db, limit=10)` is called by the CLI worker or a cron job. It:

1. Fetches up to `limit` rows with `eval_type=PERFORMANCE` from Postgres.
2. Filters to rows where `eval_data.judge_status == "pending"`.
3. Applies privacy and max-attempts gates (from `EvalLivePolicy.from_env()`).
4. For each eligible row, resolves rubrics (from `eval_data.judge_rubric_ids` or
   `rubrics_for_agent(agent_id)`).
5. Calls `judge.evaluate(rubric=rubric, judge_input=...)` via `AgentAsJudgeEval`.
6. Writes a child `EvalRunRecord` with `eval_type=AGENT_AS_JUDGE` and the score.
7. Updates the parent row's `judge_status` to `"judged"` (or `"retry_pending"` / `"failed"` on error).
8. Writes an experience note to the vault (see below).

Run it manually:

```bash
# Single pass — judges up to 10 pending rows
PYTHONPATH=. .venv/bin/python -m agentos.live_judge --limit 10

# Continuous loop (poll every 60 s)
PYTHONPATH=. .venv/bin/python -m agentos.live_judge --loop --interval 60
```

### 3. Eval rubrics (`agentos/eval_rubrics.py`)

Each agent has one or more rubrics that define what the judge evaluates:

| Rubric ID | Agent | Scoring | Threshold | Criteria summary |
|-----------|-------|---------|-----------|-----------------|
| `chat-helpfulness-v1` | `chat` | binary | 1.0 | Response is helpful, directly answers the user, avoids fabricated vault facts |
| `query-groundedness-v1` | `query` | numeric | 0.7 | Answer is grounded in citation data structures, not just markdown citation tokens |
| `ingest-fidelity-v1` | `ingest` | numeric | 0.7 | Preserves source meaning, chooses sensible note path, avoids leaking private content |
| `curator-quality-v1` | `curator` | numeric | 0.7 | Note adds value, has correct tags, links to existing notes, properly formatted |
| `research-grounding-v1` | `research` | numeric | 0.7 | Report cites sources, conclusions traceable to evidence, no fabricated claims |

`supervisor` has no live rubric (routing decisions are validated by the eval suite only).

Numeric thresholds are on a 0–1 scale. Binary rubrics pass only at 1.0.

---

## Checking eval results

### Query the database directly

```sql
-- All eval rows, newest first
SELECT run_id, agent_id, eval_type, created_at,
       eval_data->>'score' AS score,
       eval_data->>'status' AS status,
       eval_data->>'judge_status' AS judge_status
FROM ai.agno_eval_runs
ORDER BY created_at DESC
LIMIT 50;

-- Live performance rows waiting to be judged
SELECT run_id, agent_id, eval_data->>'judge_status' AS judge_status
FROM ai.agno_eval_runs
WHERE eval_data->>'eval_type' = 'performance'
  AND eval_data->>'judge_status' = 'pending'
ORDER BY created_at DESC;

-- Judge child rows with scores
SELECT run_id, agent_id, eval_data->>'rubric_id', eval_data->>'score', eval_data->>'passed'
FROM ai.agno_eval_runs
WHERE eval_type = 'agent_as_judge'
ORDER BY created_at DESC
LIMIT 20;

-- Suite accuracy rows (written by pytest eval_recorder)
SELECT run_id, agent_id, eval_data->>'case_id', eval_data->>'score'
FROM ai.agno_eval_runs
WHERE eval_type = 'accuracy'
ORDER BY created_at DESC;
```

### OBS-01 log lines

Every eval write emits a structured JSON line to the `agentos.eval` logger:

```
# Successful write
INFO agentos.eval OBS-01 eval write: {"path":"eval","status":"ok","eval_type":"performance","row_id":"<run_id>","agent_id":"chat","score":null,...}

# Failed write (db error — agent response still returned)
ERROR agentos.eval OBS-01 eval write failed: {"path":"eval","status":"error","error_type":"IntegrityError","error_msg":"..."}
```

Fields present in every OBS-01 record: `path`, `status`, `eval_type`, `row_id`,
`case_id`, `score`, `model_id`, `model_provider`, `agent_id`, `db_id`, `latency_ms`.

---

## Experience notes

After the live judge successfully scores a row it writes a structured experience note
to `vault/_system/experiences/{agent_id}/{date}-{run_id}.md`.

Example path:
```
vault/_system/experiences/chat/2026-05-29-live-chat-abc123.md
```

Example frontmatter:
```yaml
---
agent: chat
run_id: live-chat-abc123
score: 0.85
rubric: chat-helpfulness-v1
status: success
date: 2026-05-29
tags: [experience, chat]
---
```

The body includes the input summary, score verdict, and the judge's reason text.
After writing, `reindex()` is called immediately so the experience is searchable
by the agents on the next run. Experience notes feed the agent's self-improvement loop.

Experience notes are written only when `judge_status` transitions to `"judged"`.
Failures (`failed`, `failed_max_attempts`, `skipped_privacy`) do not produce notes.

---

## Coverage requirements

No coverage threshold is configured in `pytest.ini` or any coverage config file.
Coverage enforcement is left to CI policy.

---

## CI integration

No `.github/workflows/` CI configuration was found in this repository.
<!-- VERIFY: CI test configuration — no workflow files detected in .github/workflows/ -->

The test commands are driven locally via `make`:

| Make target | Command | Use case |
|-------------|---------|---------|
| `make test` | `pytest tests/ --ignore=tests/test_core.py -q` | Unit tests, no LLM |
| `make eval-smoke` | `pytest evals/ -k smoke -q` | Schema smoke, no LLM |
| `make eval-full` | `EVAL_JUDGE_TIER=orchestrator pytest evals/ -q` | Full evals with orchestrator-tier judge |
| `make check-surfaces` | `python scripts/check_surfaces.py` | Surface coverage check |
