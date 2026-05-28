# Plan: Full Agno + AgentOS Reconfiguration Sweep

**Status:** Draft v1 — awaiting approval
**Date:** 2026-05-20
**Owner:** Caio Bellizzi
**Working directory:** `/Users/caiobellizzi/Documents/Projects/ultra-agents-brain`
**Authority:** `/grill-me` session 2026-05-20 + Explore + docs-researcher passes against installed `agno==2.6.7`

---

## Context

The ultra-agents-brain v1.0 shipped with Agno configured at a minimal surface: 5 agents (chat, curator, ingest, query, research) plus a supervisor Team, all running on `OpenAILike` through a LiteLLM proxy with SQLite session storage and a markdown vault. Only the chat agent and supervisor team currently use any memory/session features. Knowledge is wired into AgentOS but has **no vector store backing it** — `VaultKnowledge.load()` just enumerates `.md` files. There is no MCP exposure, no A2A protocol, no structured outputs, no agentic RAG, and reasoning is enabled only on the supervisor.

This plan brings every agent up to Agno 2.6.7's production-grade feature set so the system can actually use the knobs Agno provides: per-user semantic memory, agentic RAG over the vault, ReasoningTools on planning-heavy agents, Pydantic-typed outputs, MCP exposure (callable from Claude Code / Cursor), and A2A (callable from ultra-workshop). The intended outcome is a Brain that remembers users across sessions, searches the vault semantically, reasons before acting on complex tasks, returns typed contracts to channel adapters, and is discoverable to external agents through standard protocols.

---

## Decisions locked (from grill-me session)

| Axis | Decision |
|---|---|
| Outcome | Full reconfiguration sweep (every agent) |
| Infra | Add Postgres + pgvector — single new VPS service |
| Agent features | Tier 2: MemoryManager + Knowledge/RAG + ReasoningTools + `output_schema` |
| AgentOS surface | MCP server + A2A protocol (no custom FastAPI routes) |
| Model routing | Reassign per feature need (capable models for reasoning/structured outputs) |
| Evals | All 4 Agno eval classes — Accuracy, Reliability, Performance, AgentAsJudge — per agent + team |
| Sequencing | No conflict — Hermes already replaced in v1.0 |

---

## Current state (validated against codebase)

- **Agents** (`agentos/agents/*.py`):
  - `chat` — has `enable_agentic_memory`, session summaries, history, `query_vault` tool
  - `curator` — bare: model + tools (`run_digest`, `run_review`, `lint_vault`, `poll_feeds`)
  - `ingest` — bare: model + tools (`ingest_to_vault` with HITL)
  - `query` — bare: model + tools (`query_vault`)
  - `research` — history only + `research_topic` tool (HITL)
  - `supervisor` (Team, untracked) — has `reasoning=True`, agentic memory, session summaries
- **AgentOS** (`agentos/app.py`): `agents=[5]`, `teams=[supervisor]`, `knowledge=[kb.knowledge]`, `tracing=True`. **No MCP, no A2A.** Cost callback wired.
- **DB**: SQLite (`aiosqlite`) at `db` shared by all agents
- **Knowledge** (`agentos/knowledge.py`): `Knowledge(name=...)` with **no vector store**; `load()` enumerates files only
- **Models** (`agentos/model.py`): `OpenAIChat` against LiteLLM proxy `:4000`
- **Tools** (`agentos/tools/vault.py`): 7 plain callables, 2 with `@tool(requires_confirmation=True)`
- **Telegram adapter** (`channels/telegram_adapter.py`): native async, POSTs to `/agents/{id}/runs`, handles HITL via `/continue`
- **Pinned deps**: `agno==2.6.7`. **Missing**: `pgvector`, `psycopg[binary]`, `sentence-transformers`, `a2a-sdk`

---

## Target state

### Infra (Wave 0)
- New systemd unit `uab-postgres.service` running Postgres 16 + pgvector extension on the VPS, bound `127.0.0.1:5432` only
- Two databases: `agno_sessions` (replaces SQLite — sessions/memory) and `agno_knowledge` (PgVector tables for vault RAG)
- `pgvector` extension installed: `CREATE EXTENSION IF NOT EXISTS vector;`
- New env vars in `.env`: `POSTGRES_DSN_SESSIONS`, `POSTGRES_DSN_KNOWLEDGE`
- `requirements.txt` additions: `psycopg[binary]>=3.2`, `pgvector>=0.3`, `sentence-transformers>=3.0`, `a2a-sdk>=0.2`

### Model routing reassignment (Wave 1)
Update `agentos/model.py` to expose a richer factory and reassign per agent:

| Agent | Current tier | New tier | Reason |
|---|---|---|---|
| chat | `default-worker` | `default-worker` | Conversational, no change |
| query | `cheap-worker` | `default-worker` | Needs structured outputs + RAG |
| curator | `cheap-worker` | `cheap-worker` | Bulk ops, no change |
| ingest | `cheap-worker` | `default-worker` | Structured outputs need capable model |
| research | `default-worker` | `orchestrator` | Reasoning + multi-step planning |
| supervisor | `orchestrator` | `orchestrator` | Already correct |

### Agent reconfigurations (Wave 2)

All 5 agents gain (explicit kwarg list — no implicit "memory" bundle):
- `memory_manager=memory` (shared `MemoryManager` instance with `PostgresDb` backend)
- `enable_agentic_memory=True` (agent decides when to write memories)
- `update_memory_on_run=True` (replaces deprecated `enable_user_memories`)
- `add_history_to_context=True`
- `output_schema=<AgentSpecificResult>` (new Pydantic models in `agentos/schemas.py`)

Session-summary trio added to **conversational** agents (chat, query, research — not curator/ingest which are one-shot bulk):
- `enable_session_summaries=True`
- `add_session_summary_to_context=True`
- `search_past_sessions=True`
- `num_past_sessions_to_search=3`

Knowledge / agentic RAG:
- `knowledge=knowledge` + `search_knowledge=True` for chat/query/research (agentic RAG over vault)

Per-agent reasoning:
- `research`, `ingest`, `query` — add `ReasoningTools(add_instructions=True)` to `tools=[...]`
- `chat`, `curator` — no reasoning (latency-sensitive / bulk)

Supervisor team (`supervisor.py`) already carries the session-summary trio, `add_team_history_to_members=True`, `share_member_interactions=True`, and `reasoning=True`. Only changes needed: swap inline kwargs to use the shared `memory_manager`, add `output_schema=SupervisorRouting`, no other touches.

### Knowledge layer (Wave 2)
Rewrite `agentos/knowledge.py`:
- Replace empty `Knowledge(name=...)` with `Knowledge(vector_db=PgVector(...))`
- `PgVector(table_name="vault", db_url=POSTGRES_DSN_KNOWLEDGE, embedder=SentenceTransformerEmbedder(), search_type=SearchType.hybrid, reranker=SentenceTransformerReranker())`
- `VaultKnowledge.load()` iterates vault `.md` files calling `knowledge.insert(path=md_path, upsert=True, skip_if_exists=True)` — sync at startup, incremental from curator
- Add async variant `aload()` for systemd-triggered refresh

### AgentOS reconfiguration (Wave 3)
Update `agentos/app.py`:
- Replace SQLite `db` with `PostgresDb(db_url=POSTGRES_DSN_SESSIONS, create_schema=True)`
- Instantiate shared `MemoryManager(db=db, model=chat_model("cheap-worker"))`
- Pass `enable_mcp_server=True` to `AgentOS(...)`
- Pass `a2a_interface=True` to `AgentOS(...)`
- `app = agent_os.get_app(enable_mcp_server=True)` — **both** flags required (gotcha from docs research)
- Knowledge stays mounted; teams stay mounted

### Evals (Wave 5)

Agno 2.6.7 ships 4 eval classes — source-verified in `.venv/lib/python3.13/site-packages/agno/eval/`. No CLI, no dataset format, no built-in RAG/memory/reasoning eval. We build the orchestration as plain pytest.

| Class | Module | Use here |
|---|---|---|
| `AccuracyEval` | `agno.eval.accuracy` | Judge-scored quality — **only for chat's free-text reply** (everything else is structured) |
| `ReliabilityEval` | `agno.eval.reliability` | Tool-call correctness (HITL `ingest_to_vault`, `research_topic`, supervisor routing) |
| `PerformanceEval` | `agno.eval.performance` | p95 latency baseline per agent — catches LiteLLM tier-swap regressions |
| `AgentAsJudgeEval` | `agno.eval.agent_as_judge` | Inline per-run judges attached to `agent.evals=[...]` — fires `run_in_background=True` on every real user request for continuous quality telemetry |

#### Eval strategy by output type (locked in grill session)

| Output kind | Tool | Why |
|---|---|---|
| Pydantic fields (path, tags, citations, action lists) | **Plain pytest assertions** | Deterministic, fast, no judge LLM. `assert result.note_path.startswith("vault/02-Resources/")` |
| Free-text fields (chat reply body) | `AccuracyEval` with hand-authored expected | Only place natural-language scoring is needed |
| RAG citation correctness | **Tag-based pytest assertions** | `assert "#vector-db" in {tag for c in result.citations for tag in c.tags}` — survives vault renames/moves |
| Always-on quality rules | Inline `AgentAsJudgeEval` (production) | Continuous signal from real traffic, persisted to `agno_eval_runs` |
| Tool selection / delegation | `ReliabilityEval` | Native Agno class, deterministic check |
| Latency drift | `PerformanceEval` | Native Agno class, baseline diff |

#### Per-agent coverage (3 hand-authored cases per agent)

| Agent | Pytest field asserts | AccuracyEval (free text) | ReliabilityEval | PerformanceEval | Inline AgentAsJudge |
|---|---|---|---|---|---|
| chat | citation tags present | 3 cases on `ChatReply.text` | — | ✓ p95 | ✓ "cite vault if vault-relevant" |
| curator | actions_taken non-empty, no errors | — | ✓ correct tool per intent | ✓ batch time | — |
| ingest | `note_path` prefix, tags ≥2, `needs_review` flag | — | ✓ `ingest_to_vault` called with right `category` | — | — |
| query | citation tag overlap with expected topic tags | — | — | ✓ p95 | ✓ "answer must cite ≥1 source" |
| research | `next_questions` ≥3, `findings` non-empty | — | ✓ `research_topic` + reasoning `think`/`analyze` called | ✓ token cost | ✓ "must include ≥3 next_questions" |
| supervisor (team) | `chosen_member` matches expected | — | ✓ delegated to expected member | ✓ p95 e2e | — |

Total: **18 hand-authored cases** (3 × 6 targets). Real authoring cost ≈3 hours.

#### Module layout

```
evals/
  __init__.py
  conftest.py                  # fixtures: postgres_db, judge_model (env-var driven), agents
  fixtures/
    eval_vault_seed.md         # optional: stable notes referenced by tag in datasets
  datasets/
    chat_cases.py              # 3 cases: input, expected_text, expected_citation_tags
    curator_cases.py           # 3 cases: input, expected_actions, expected_no_errors
    ingest_cases.py            # 3 cases: source, expected_path_prefix, expected_tags
    query_cases.py             # 3 cases: question, expected_topic_tags
    research_cases.py          # 3 cases: topic, expected_reasoning_tools, min_next_questions
    supervisor_routing.py      # 3 cases: input, expected_member
  test_chat.py                 # pytest assertions + AccuracyEval
  test_curator.py
  test_ingest.py
  test_query.py
  test_research.py
  test_supervisor.py
  baselines/
    accuracy_baseline.json     # frozen avg_scores — regression gate
    performance_baseline.json  # frozen p95 latencies
```

#### Judge model wiring — env-var configurable (locked)

```python
# evals/conftest.py
import os
from agentos.model import chat_model

EVAL_JUDGE_TIER = os.getenv("EVAL_JUDGE_TIER", "private-worker")

@pytest.fixture(scope="session")
def judge_model():
    return chat_model(EVAL_JUDGE_TIER)
```

Default `private-worker` = LM Studio (free, offline). Override per-run: `EVAL_JUDGE_TIER=orchestrator pytest evals/` when investigating regressions or before a release. Document the tradeoff in `evals/README.md`: LM Studio judge is good enough for binary criteria and regression sniff-tests; switch to `orchestrator` for nuanced AccuracyEval scoring before merging significant agent changes.

#### Inline AgentAsJudge attachment (locked — in production agent code)

```python
# agentos/agents/chat.py
from agno.eval.agent_as_judge import AgentAsJudgeEval
from agentos.model import chat_model
import os

EVAL_JUDGE_TIER = os.getenv("EVAL_JUDGE_TIER", "private-worker")

citation_judge = AgentAsJudgeEval(
    name="chat-must-cite",
    criteria="If the user's message references something likely in their vault (notes, articles, ideas), the response MUST include at least one vault citation. If purely conversational or unrelated to vault content, pass.",
    scoring_strategy="binary",
    model=chat_model(EVAL_JUDGE_TIER),
    db=db,
    run_in_background=True,   # never blocks user response
)

chat_agent = Agent(
    ...,
    evals=[citation_judge],
)
```

Same pattern on `query` (`"answer must cite ≥1 source"`) and `research` (`"must include ≥3 next_questions"`). Runs on every real user request via Telegram → continuous quality telemetry in `agno_eval_runs`, separate from synthetic pytest cases.

#### Per-file pre-commit gating (locked)

`.pre-commit-config.yaml` maps file → eval scope:

| Files staged | Evals run | Why |
|---|---|---|
| `agentos/agents/chat.py` | `pytest evals/test_chat.py` | Isolated to that agent |
| `agentos/agents/curator.py` | `pytest evals/test_curator.py` | " |
| `agentos/agents/ingest.py` | `pytest evals/test_ingest.py` | " |
| `agentos/agents/query.py` | `pytest evals/test_query.py` | " |
| `agentos/agents/research.py` | `pytest evals/test_research.py` | " |
| `agentos/agents/supervisor.py` | `pytest evals/test_supervisor.py` | " |
| `agentos/knowledge.py` | `pytest evals/test_query.py evals/test_research.py` | RAG-dependent agents |
| `agentos/model.py`, `agentos/app.py`, `agentos/schemas.py` | `pytest evals/` (full) | Config-wide changes |
| Any other file | (skip evals) | Unrelated edits don't block |

Hook implementation: a small shell script `tools/precommit_eval_router.sh` reads staged files via `git diff --cached --name-only` and runs only the mapped subset. Latency budget: ≤15s for single-agent edit, ≤90s for full suite.

#### Regression baselines

1. After Wave 5b coverage is in, run `EVAL_JUDGE_TIER=orchestrator pytest evals/` once
2. Write results to `evals/baselines/accuracy_baseline.json` and `performance_baseline.json` via a `--write-baseline` flag in `conftest.py`
3. Subsequent runs `assert result.avg_score >= baseline[case_id] - 0.5` and `assert result.p95_run_time <= baseline[case_id] * 1.25`
4. Intentional baseline updates: `pytest evals/ --update-baseline` regenerates and commits

#### Storage + dashboard

All eval runs persist to `PostgresDb` via `agno_eval_runs` (auto-created). Surfaces on os.agno.com dashboard via default `telemetry=True`. No `enable_eval=True` flag exists.

#### Critical gotchas (from docs-researcher pass)

- **`AccuracyEval.run()` raises `ValueError` if `db` is `AsyncBaseDb`** — use `.arun()` consistently if we ever go async (currently sync, fine)
- **`PerformanceEval.func` must be sync** for `.run()` — wrap any async agent call in `asyncio.run(agent.arun(...))` inside the lambda
- **Pydantic stringification in AccuracyEval** — moot here since we use pytest assertions for Pydantic; AccuracyEval is reserved for chat's `ChatReply.text` only
- **Default judge is `o4-mini`** — every `AccuracyEval`/`AgentAsJudgeEval` instantiation MUST pass explicit `model=` (the `judge_model` fixture / inline `chat_model(EVAL_JUDGE_TIER)`)

### New module: schemas (Wave 2)
Create `agentos/schemas.py` with one Pydantic model per agent:
- `ChatReply` — `text: str`, `citations: list[VaultCitation]`, `suggested_actions: list[str]`
- `QueryAnswer` — `answer: str`, `citations: list[VaultCitation]`, `confidence: float`
- `IngestResult` — `note_path: str`, `frontmatter: dict`, `tags: list[str]`, `needs_review: bool`
- `ResearchReport` — `topic: str`, `findings: list[Finding]`, `next_questions: list[str]`
- `CuratorResult` — `actions_taken: list[str]`, `notes_touched: list[str]`, `errors: list[str]`

Channel adapter (`telegram_adapter.py`) updates to consume typed responses — minimal change since AgentOS already returns JSON; just narrow the JSONPath extraction to typed fields.

---

## Critical files to modify

| File | Change |
|---|---|
| `agentos/app.py` | Replace `db`, add `memory`, enable MCP + A2A |
| `agentos/agents/chat.py` | + `memory_manager`, `knowledge`, `output_schema`, switch to `update_memory_on_run` |
| `agentos/agents/curator.py` | + `memory_manager`, `output_schema` |
| `agentos/agents/ingest.py` | + `memory_manager`, `output_schema`, `ReasoningTools`, bump model |
| `agentos/agents/query.py` | + `memory_manager`, `knowledge`, `output_schema`, `ReasoningTools`, bump model |
| `agentos/agents/research.py` | + `memory_manager`, `knowledge`, `output_schema`, `ReasoningTools`, bump model to orchestrator |
| `agentos/agents/supervisor.py` | + `memory_manager` (replace inline kwargs), `output_schema` |
| `agentos/knowledge.py` | Add `PgVector` + `SentenceTransformerEmbedder` + reranker; rewrite `load()` |
| `agentos/model.py` | Add helper exporting tier→model mapping |
| `agentos/schemas.py` | **NEW** — 5 Pydantic result models + shared `VaultCitation` |
| `requirements.txt` | + `psycopg[binary]`, `pgvector`, `sentence-transformers`, `a2a-sdk` |
| `channels/telegram_adapter.py` | Narrow response extraction to typed fields |
| `ops/systemd/uab-postgres.service` | **NEW** — systemd unit for Postgres |
| `.env.example` | + `POSTGRES_DSN_SESSIONS`, `POSTGRES_DSN_KNOWLEDGE` |
| `evals/` (new tree) | **NEW** — datasets, pytest tests, baselines, inline judges |
| `evals/conftest.py` | **NEW** — shared db + judge_model fixtures |
| `evals/datasets/*.py` | **NEW** — 6 dataset files (one per agent + supervisor) |
| `evals/test_accuracy.py` | **NEW** — parametrized AccuracyEval runner |
| `evals/test_reliability.py` | **NEW** — parametrized ReliabilityEval runner |
| `evals/test_performance.py` | **NEW** — PerformanceEval runner with baseline diff |
| `evals/baselines/*.json` | **NEW** — frozen baselines committed to repo |
| `tools/precommit_eval_router.sh` | **NEW** — maps staged files to scoped eval runs |
| `.pre-commit-config.yaml` | **NEW** or modify — wires the router script in |

Reusable existing utilities (do **not** rewrite):
- `agentos/tools/vault.py` — keep all 7 tool functions as-is
- `agentos/cost.py` — already wired, no change
- `channels/telegram_adapter.py` HITL flow — already correct

---

## Implementation waves

**Wave 0 — Infra (1 commit)**
1. Add systemd unit, install Postgres + pgvector on VPS
2. Add `psycopg`, `pgvector`, `sentence-transformers`, `a2a-sdk` to `requirements.txt`
3. Add env vars + smoke-test `psql` connection

**Wave 1 — Schemas + model factory (1 commit)**
1. Create `agentos/schemas.py` with all 5 Pydantic models
2. Extend `agentos/model.py` with tier mapping helper

**Wave 2 — Per-agent reconfig (5 commits, one per agent)**
For each of chat/curator/ingest/query/research:
1. Add `memory_manager`, `output_schema`, knowledge/reasoning per the table above
2. Run that agent's smoke test (`tests/test_agentos.py`) — extend tests to cover new fields

**Wave 3 — AgentOS surface (1 commit)**
1. Swap `db` to `PostgresDb`, instantiate shared `MemoryManager`
2. Wire `enable_mcp_server=True` + `a2a_interface=True` on both `AgentOS()` and `get_app()`
3. Update `agentos/knowledge.py` to use `PgVector` + load vault on startup

**Wave 4 — Adapter + verification (1 commit)**
1. Update `channels/telegram_adapter.py` to consume typed responses
2. Bootstrap vault into `agno_knowledge` via one-shot `python -m agentos.knowledge --reindex`
3. End-to-end smoke: Telegram → chat (memory persists across sessions) → query (RAG cites vault notes) → research (reasoning steps visible in trace)

**Wave 5 — Evals (3 commits)**
1. **Commit 5a — scaffolding**: create `evals/` tree, `conftest.py` with `judge_model` fixture (env-var `EVAL_JUDGE_TIER`, default `private-worker`), dataset stubs, one smoke test per agent (pytest assertion only, no LLM judge yet), wire `pytest evals/` into local `make test`
2. **Commit 5b — coverage + inline judges**: fill all 6 datasets (3 cases each, hand-authored), implement pytest field assertions per coverage table, add `AccuracyEval` only to `test_chat.py`, add `ReliabilityEval` to ingest/research/curator/supervisor, add `PerformanceEval` to chat/query/research/curator/supervisor, attach inline `AgentAsJudgeEval` to chat/query/research **in production agent files**
3. **Commit 5c — baselines + pre-commit hook**: run `EVAL_JUDGE_TIER=orchestrator pytest evals/` once with a `--write-baseline` flag, freeze `evals/baselines/*.json`, add `tools/precommit_eval_router.sh` + `.pre-commit-config.yaml` entry mapping staged files to scoped eval runs per the per-file table above

---

## Verification

| Check | How |
|---|---|
| Postgres reachable | `psql "$POSTGRES_DSN_SESSIONS" -c 'SELECT 1'` |
| pgvector installed | `psql "$POSTGRES_DSN_KNOWLEDGE" -c "SELECT extname FROM pg_extension WHERE extname='vector'"` |
| Memory persists across sessions | Send Telegram msg A → restart agentos → send msg B → chat agent recalls A |
| RAG cites vault | Query agent answer includes `citations: [VaultCitation(path=...)]` |
| Reasoning fires | Research agent run trace contains `think`/`analyze` tool calls |
| Structured outputs | `curl localhost:7000/agents/chat/runs` returns JSON matching `ChatReply` schema |
| MCP exposure | `curl -H 'Authorization: Bearer $KEY' http://localhost:7000/mcp` returns MCP capabilities |
| A2A discovery | `curl localhost:7000/a2a/agents/chat/.well-known/agent-card.json` returns agent card |
| Existing tests pass | `rtk pytest tests/` |
| Hermes-era smoke | `channels/SMOKE.md` flow still green |
| Evals scaffolded | `rtk pytest evals/ -k smoke` returns green |
| Eval coverage complete | `rtk pytest evals/` runs all Accuracy + Reliability + Performance suites |
| Baselines frozen | `evals/baselines/accuracy_baseline.json` + `performance_baseline.json` exist and are tracked in git |
| Eval runs persist | `psql "$POSTGRES_DSN_SESSIONS" -c "SELECT count(*) FROM ai.agno_eval_runs"` returns >0 |
| Dashboard sees evals | os.agno.com → Evals tab shows runs (telemetry=True default) |
| Pre-commit per-file routing | `git commit -m "test" agentos/agents/chat.py` runs ONLY `test_chat.py` (under 15s); unrelated edit skips evals |
| Judge tier switch works | `EVAL_JUDGE_TIER=orchestrator pytest evals/test_chat.py` produces different (cloud-tier) judge scores than default `private-worker` |
| Inline judges fire on real traffic | Send Telegram msg to chat → check `agno_eval_runs` table for new row with `eval_type=AGENT_AS_JUDGE` |
| Regression gate works | Force a fail (lower a dataset's expected score) → `git commit` is blocked; restore → succeeds |

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| pgvector embedding cost on first vault load | Use local `SentenceTransformerEmbedder` (no API), one-shot reindex outside hot path |
| `output_schema` + tool calls break on some models | Anthropic falls back to `parser_model` — safe per docs-researcher findings. Test ingest agent first (smallest blast radius). |
| SQLite → Postgres migration loses session history | Acceptable: v1.0 retrospective notes "no session backup expected". Document in commit. |
| Local embedder differs across machines | Pin `sentence-transformers/all-MiniLM-L6-v2` (384 dims), document in `agentos/knowledge.py` |
| Concurrent vault writes during reindex | Use `upsert=True, skip_if_exists=True` — safe |
| MCP/A2A auth not configured | Bind `127.0.0.1:7000` only (REQ-104 already enforces); add JWT in a follow-up |

---

## Out of scope (deferred)

- Agno Workflows v2 (Tier 4) — revisit if curator/ingest pipelines grow non-linear branches
- Async conversion of agents (Tier 3) — current sync flow is fine for Telegram long-poll latency
- Custom FastAPI routes / Hermes-replacement work — already shipped
- ultra-workshop integration via A2A — Brain just exposes the endpoint; Workshop adoption is a separate plan

---

## References

- Agno 2.6.7 source: `/.venv/lib/python3.13/site-packages/agno/` (read directly during research)
- Docs: https://docs.agno.com (A2A endpoint shapes, security model)
- Past decisions: `.planning/REQUIREMENTS.md` (REQ-104 loopback binding), `.planning/RETROSPECTIVE.md` (v1.0 patterns)
- Grill session date: 2026-05-20
