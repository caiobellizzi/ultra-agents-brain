<!-- generated-by: gsd-doc-writer -->
# Architecture

## System Overview

ultra-agents-brain is a personal second-brain system that hosts a fleet of AI agents over a local markdown vault. External input arrives from a Telegram channel or VPS cron jobs; each message is routed to one of five Agno agents (or the `supervisor` team that orchestrates them) exposed via an AgentOS FastAPI server (`:7000` on prod VPS, `:7001` on macOS dev). Agents read and write markdown notes in a local vault directory, use a LiteLLM proxy as a model-routing layer (local LM Studio + cloud providers + NVIDIA NIM), and persist session memory in **SqliteDb** locally or **PostgresDb** (with pgvector knowledge schema) on the VPS — `agentos/db.py` picks based on `POSTGRES_DSN_SESSIONS`.

The Memory and Knowledge surfaces are wrapped by `agentos/instrumented_memory.py` and `agentos/instrumented_knowledge.py` for structured observability. Per-turn eval rows are recorded by `agentos/eval_recorder.py` (OBS-01), and a separate `live_judge` worker scores those rows asynchronously using an agent-as-judge model, writing experience notes back to the vault. The system follows a layered architecture: a thin HTTP host (`agentos`) delegates to domain logic (`ultra_brain`) for vault I/O, extraction, research, and cost tracking.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Channels                         │
│    Telegram Bot  ─────────────────────────  systemd Timers      │
└────────────┬────────────────────────────────────────┬───────────┘
             │ POST /agents/{id}/runs                  │ curl POST
             ▼                                         ▼
┌─────────────────────────────────────────────────────────────────┐
│          AgentOS FastAPI Host  (:7001 dev / :7000 prod)          │
│   agentos/app.py — Agno AgentOS: 5 agents + supervisor team     │
│                                                                  │
│  ┌──────┐ ┌──────┐ ┌────────┐ ┌──────────┐ ┌──────┐ ┌────────┐│
│  │ chat │ │ingest│ │ query  │ │ research │ │curate│ │ super- ││
│  │      │ │      │ │        │ │          │ │      │ │ visor  ││
│  └──┬───┘ └──┬───┘ └───┬────┘ └────┬─────┘ └──┬───┘ └──┬─────┘│
└────────┼──────────┼──────────┼──────────┼──────────┼─────────┘
         │          │          │          │          │
         │   OBS-01 class-level patch (eval_recorder + approval_recorder)
         │   every run() / arun() wrapped at Agent/Team class level
         │          │          │          │          │
         ▼          ▼          ▼          ▼          ▼
┌────────────────────────────────────────────────────────────────┐
│                    agentos/tools/vault.py                       │
│         Plain-Python callables — bridge to ultra_brain          │
└───────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                    ▼
┌──────────────┐  ┌──────────────┐  ┌────────────────────┐
│ ultra_brain/ │  │ ultra_brain/ │  │  ultra_brain/      │
│  query.py    │  │  ingest.py   │  │  research.py       │
│  vault.py    │  │  express.py  │  │  cost.py           │
│  lint.py     │  │  markdown.py │  │  trust.py          │
│  review.py   │  │  telos.py    │  │  monitor.py        │
└──────┬───────┘  └──────┬───────┘  └─────────┬──────────┘
       │                 │                     │
       ▼                 ▼                     ▼
┌───────────────────────────────────────────────────────┐
│              Markdown Vault (filesystem)               │
│   ~/Documents/second-brain  or  /srv/second-brain      │
│   vault/_system/experiences/{agent_id}/  ← exp notes  │
│   vault/_system/.workshop-queue.jsonl    ← workshop Q  │
│   vault/_system/workshop-repos.json      ← repo reg.   │
└───────────────────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│         LiteLLM Proxy  (:4000)           │
│   Routes to LM Studio / cloud / NIM      │
│   Tiers: cheap-worker, default-worker,   │
│   orchestrator, research-worker,         │
│   private-worker                         │
└──────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│  Session + Knowledge persistence (agentos/db.py)      │
│  • SqliteDb at $UAB_DB_PATH (local/dev default)       │
│  • PostgresDb id="ultra-brain-main" when              │
│    POSTGRES_DSN_SESSIONS is set (VPS prod)            │
│  • pgvector schema: table=vault, BAAI/bge-small-en    │
│    hybrid search, SentenceTransformerReranker         │
│  • ai.agno_eval_runs — eval rows (PERFORMANCE rows    │
│    written by eval_recorder; AGENT_AS_JUDGE child rows│
│    written by live_judge)                             │
│  • ai.agno_memory — extracted user memories          │
│  • ai.agno_knowledge — vault RAG content rows        │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│            Eval Feedback Loop (async)                 │
│                                                       │
│  eval_recorder.py                                     │
│    class-level patch of Agent/Team run()/arun()       │
│    writes PERFORMANCE row to ai.agno_eval_runs        │
│    marks eligible rows judge_status="pending"         │
│          │                                            │
│          ▼  (systemd timer: uab-live-judge.timer)     │
│  live_judge.py  (python -m agentos live-judge --once) │
│    reads pending rows from ai.agno_eval_runs          │
│    routes each row through eval_live_policy.py        │
│    (privacy gate + sample-rate filter)                │
│    selects rubric via eval_rubrics.py                 │
│    calls DefaultLiveJudge (private-worker tier)       │
│    writes AGENT_AS_JUDGE child row                    │
│    writes experience note to vault/_system/           │
│      experiences/{agent_id}/{date}-{run_id}.md        │
│    attempts reindex via agentos.knowledge.reindex()   │
└──────────────────────────────────────────────────────┘
```

## Data Flow

### Request path (live traffic)

1. **Telegram adapter** sends `POST /agents/{agent_id}/runs` with JSON body to the AgentOS server.
2. **AgentOS** (`agentos/app.py`) routes the run to the matching Agno `Agent` or `Team` instance. Because `eval_recorder.patch_classes_for_recording()` runs at module import time, the class-level patch intercepts the call before Agno's route handler sees it.
3. The agent calls its LLM via **`agentos/model.py`**, which resolves to an OpenAI-compatible endpoint on the **LiteLLM proxy** at `:4000`. LiteLLM selects the actual model based on the requested model-tier string (`cheap-worker`, `orchestrator`, etc.). Each successful LLM call also fires the `agentos.cost` success callback, which appends a row to `vault/_system/cost-ledger.md`.
4. The agent invokes one or more **tool callables** from `agentos/tools/vault.py` (e.g. `query_vault`, `ingest_to_vault`, `research_topic`).
5. Tool callables delegate to **`ultra_brain`** domain modules which perform actual vault I/O, web extraction, or markdown synthesis.
6. Results are written to the **markdown vault** on disk. Session state and extracted memories are persisted to the shared `db` (SQLite locally, Postgres in prod).
7. For tools marked `requires_confirmation=True` (e.g. `ingest_to_vault`), Agno pauses the run and returns `status=paused`. The Telegram adapter presents approve/deny buttons; on approval it sends `POST /runs/{run_id}/continue` to resume. The `approval_recorder` patch logs every approval lifecycle event.
8. After the run completes, the class-level eval wrapper records one `EvalRunRecord(eval_type=PERFORMANCE)` row to `ai.agno_eval_runs`. If `eval_live_policy` decides the row is eligible for judging, it sets `judge_status="pending"` and `judge_rubric_ids=[...]` inside `eval_data`.
9. Curator runs (digest, review, lint, RSS poll) are triggered by **systemd timers** via direct curl POSTs — no Telegram involved.

### Eval / judgment path (async, out-of-band)

1. **`uab-live-judge.timer`** fires the oneshot `uab-live-judge.service`, which runs `python -m agentos live-judge --once --limit 20`.
2. `live_judge_cli()` delegates to `run_live_judge_once()`, which queries `ai.agno_eval_runs` for rows with `judge_status="pending"`.
3. For each pending row, `eval_live_policy.py` re-applies the privacy gate and sample-rate filter. Rows that pass are routed to `DefaultLiveJudge` (which instantiates `AgentAsJudgeEval` backed by the `private-worker` model tier).
4. The judge produces a `JudgeDecision(score, passed, reason)`. A child `EvalRunRecord(eval_type=AGENT_AS_JUDGE)` row is written, and the parent row's `judge_status` is updated to `"judged"`.
5. `_write_experience_note()` writes a structured markdown file to `vault/_system/experiences/{agent_id}/{date}-{run_id}.md` with YAML frontmatter `(agent, run_id, score, rubric, status, date)`.
6. `agentos.knowledge.reindex()` is attempted so the new experience note becomes searchable in the next agent run (requires `POSTGRES_DSN_KNOWLEDGE`).

## Key Abstractions

| Abstraction | File | Description |
|---|---|---|
| `AgentOS` | `agentos/app.py` | Agno's built-in multi-agent FastAPI host; exposes the standard Agno HTTP surface (agents, sessions, runs, memory, knowledge, approvals) |
| `Agent` (×5) | `agentos/agents/` | Individual Agno agents: `chat`, `ingest`, `query`, `research`, `curator` — each with `enable_agentic_culture=True` |
| `make_supervisor_team()` | `agentos/agents/supervisor.py` | Agno `Team` that orchestrates the 5 leaf agents for multi-step tasks; routes at `orchestrator` model tier |
| `chat_model()` | `agentos/model.py` | Factory returning `LiteLLMChat` (OpenAI-compatible) pointed at LiteLLM proxy; 5 tier strings map to env-var model IDs |
| `make_knowledge()` | `agentos/knowledge.py` | Knowledge factory; returns `InstrumentedKnowledge` wrapping PgVector with hybrid search and MiniLM reranker; stub-fallback when `POSTGRES_DSN_KNOWLEDGE` unset |
| `reindex()` | `agentos/knowledge.py` | Walk vault `*.md`, sha256-delta index to pgvector, called by `python -m agentos.knowledge --reindex` or post-judgment |
| `InstrumentedKnowledge` | `agentos/instrumented_knowledge.py` | Subclass of `Knowledge`; emits OBS-01 log lines on search and bumps `access_count` per hit |
| `InstrumentedMemoryManager` | `agentos/instrumented_memory.py` | Subclass of `MemoryManager`; wraps `create_user_memories` / `acreate_user_memories` with structured logging |
| `patch_classes_for_recording()` | `agentos/eval_recorder.py` | Class-level monkey-patch of `Agent.run/arun` and `Team.run/arun`; survives Agno's `deep_copy()` per HTTP request |
| `EvalLivePolicy` | `agentos/eval_live_policy.py` | Privacy gate + sample-rate filter; reads `EVAL_LIVE_JUDGE_ENABLED`, `EVAL_LIVE_SAMPLE_RATE`, per-agent overrides from env |
| `EvalRubric` / `LIVE_RUBRICS` | `agentos/eval_rubrics.py` | 5 rubrics mapping agent ID → quality criteria, scoring strategy, and threshold |
| `DefaultLiveJudge` | `agentos/live_judge.py` | Instantiates `AgentAsJudgeEval` at `private-worker` tier; called by the CLI worker |
| `patch_db_for_approval_recording()` | `agentos/approval_recorder.py` | Instance-level patch of db approval methods; logs every approval create/resolve/run_status event |
| `db` / `POSTGRES_DB` | `agentos/db.py` | `SqliteDb` always-on fallback; `PostgresDb(id="ultra-brain-main")` when `POSTGRES_DSN_SESSIONS` set |
| `register_workshop_routes()` | `agentos/workshop_registry.py` | Mounts `PUT /workshop/repos` for the Workshop process to persist its computed repo registry to the vault |
| `register_queue_routes()` | `agentos/workshop_queue.py` | Mounts `PUT /workshop/queue/{entry_id}/dispatched` so the Workshop can mark queue entries consumed |
| Tool callables | `agentos/tools/vault.py` | Plain-Python bridge between Agno agents and `ultra_brain` modules |
| `ultra_brain.ingest` | `ultra_brain/ingest.py` | URL/file extraction pipeline and vault filing |
| `ultra_brain.query` | `ultra_brain/query.py` | Vault retrieval with citation tokens |
| `ultra_brain.research` | `ultra_brain/research.py` | Multi-angle web research aggregated into a vault note |
| `ultra_brain.cost` | `ultra_brain/cost.py` | Per-call LiteLLM cost ledger appended to `vault/_system/cost-ledger.md` |

## Eval Feedback Loop

The eval feedback loop is a self-contained subsystem that observes every agent run, judges a sampled fraction, and writes the resulting experience notes back into the vault so future agents can learn from them.

```
Agent run completes
        │
        ▼
eval_recorder (class-level patch)
  • writes EvalRunRecord(eval_type=PERFORMANCE) to ai.agno_eval_runs
  • calls EvalLivePolicy.judge_decision() inline (fast — no LLM)
  • if eligible: sets eval_data["judge_status"] = "pending"
               eval_data["judge_rubric_ids"] = [...]
        │
        │  (async — uab-live-judge.timer fires every N minutes)
        ▼
live_judge --once
  • reads rows WHERE judge_status="pending" (limit 20)
  • EvalLivePolicy re-checks privacy + sample rate
  • DefaultLiveJudge (private-worker) runs AgentAsJudgeEval
  • writes child EvalRunRecord(eval_type=AGENT_AS_JUDGE)
  • updates parent: judge_status="judged"
  • _write_experience_note() → vault/_system/experiences/{agent_id}/
  • reindex() → experience note added to pgvector
```

**Privacy controls** (from `eval_live_policy.py`):
- `EVAL_LIVE_JUDGE_ENABLED` must be `1` (disabled by default)
- Per-agent sample rate: `EVAL_LIVE_SAMPLE_RATE` (global) + `EVAL_LIVE_SAMPLE_RATE_{AGENT}` overrides
- Payloads with secret-key markers or token-like values are blocked
- `ingest` agent: full output only sent when `EVAL_LIVE_ALLOW_CONTENT_READ=1`

**Rubrics** (`eval_rubrics.py`): `chat-helpfulness-v1`, `query-groundedness-v1`, `ingest-fidelity-v1`, `curator-quality-v1`, `research-grounding-v1`.

## Agentic Culture

All 5 leaf agents (`chat`, `ingest`, `query`, `research`, `curator`) and the `supervisor` team are created with `enable_agentic_culture=True`. This causes Agno to inject a shared Culture KB into the agent's context before each response. The Culture KB is a separate knowledge base that agents inherit, distinct from the vault RAG knowledge base. Combined with the Experience KB (vault notes written by `live_judge`), this forms the self-improvement loop: each judged run generates a note that is reindexed into the vault, making patterns from past performance available to future agent runs via RAG.

## Workshop System

The Workshop pipeline (`ultra-workshop`, a separate process running as user `uws`) performs autonomous repository work. Because `uws` cannot write to the vault's `_system/` directory (owned by `uabrain`), it communicates back to the Brain over localhost via two custom routes added to the AgentOS app:

- `PUT /workshop/repos` — receives the complete computed repo registry document; the Brain validates and atomically writes it to `vault/_system/workshop-repos.json`. New repos trigger automatic vault project mirrors under `vault/00-Projects/{slug}/`.
- `PUT /workshop/queue/{entry_id}/dispatched` — marks a work-queue entry in `vault/_system/.workshop-queue.jsonl` as dispatched after the Workshop has acted on it.

Both routes are inserted at the front of the FastAPI router to avoid being shadowed by AgentOS's catch-all sub-app.

## Directory Structure

```
ultra-agents-brain/
├── agentos/                  # HTTP host layer — Agno AgentOS wiring, agents, tools
│   ├── agents/               # One file per Agno Agent / Team definition
│   │   ├── chat.py           # Conversational agent (chat knowledge + vault RAG)
│   │   ├── curator.py        # Vault maintenance: digest, review, lint, feed poll
│   │   ├── ingest.py         # URL/file ingest with HITL confirmation gate
│   │   ├── query.py          # Pure vault retrieval, no web fallback
│   │   ├── research.py       # Multi-source web research with ReasoningTools
│   │   └── supervisor.py     # Team orchestrator for multi-step tasks
│   ├── tools/                # Plain-Python tool callables passed to agents
│   ├── app.py                # AgentOS host: wires agents, memory, KB, patches
│   ├── __main__.py           # CLI: `python -m agentos` (server) or `live-judge`
│   ├── db.py                 # Shared DB handles (SqliteDb / PostgresDb)
│   ├── model.py              # chat_model() factory, 5-tier LiteLLM routing
│   ├── knowledge.py          # make_knowledge(), reindex() write path
│   ├── schemas.py            # Pydantic response models for all agents
│   ├── instrumented_knowledge.py  # OBS-01 search wrapper + access_count bump
│   ├── instrumented_memory.py     # OBS-01 memory extraction wrapper
│   ├── eval_recorder.py      # Class-level Agent/Team run() patch → eval rows
│   ├── eval_rubrics.py       # 5 per-agent quality rubrics
│   ├── eval_live_policy.py   # Privacy gate + sample-rate filter
│   ├── live_judge.py         # CLI worker: reads pending rows, runs LLM judge
│   ├── cost.py               # LiteLLM success_callback → cost-ledger.md
│   ├── approval_recorder.py  # OBS-01 approval lifecycle wrapper
│   ├── workshop_registry.py  # PUT /workshop/repos route
│   └── workshop_queue.py     # PUT /workshop/queue/{id}/dispatched route
├── ultra_brain/              # Domain logic layer — vault I/O, extraction, research
├── deploy/                   # Docker Compose: LiteLLM proxy and supporting services
├── scripts/                  # Operational helpers: health check, smoke tests
├── ops/                      # Vault rsync launchd plist and VPS bootstrap
├── tests/                    # Pytest test suite
├── plans/                    # Markdown planning artifacts
└── docs/                     # Architecture (this file), runbooks
```

**`agentos/`** is the thin integration layer: it imports Agno primitives, wires agents to the shared db and model factory, and exposes the resulting FastAPI app. It contains no business logic.

**`ultra_brain/`** is the domain library: it can be imported and tested independently of Agno. All vault reads/writes, web extraction, markdown synthesis, cost tracking, and trust decisions live here.

**`deploy/`** holds Docker Compose configuration for the LiteLLM proxy (host-network mode so it can reach a locally-running LM Studio on `127.0.0.1:1234`) and any supporting containers.

**`ops/`** handles the vault sync side-channel: a launchd plist schedules rsync from the local vault to a VPS copy.

## Systemd Services

The VPS deployment is managed by a set of systemd units under `deploy/systemd/`:

| Unit | Type | Description |
|---|---|---|
| `uab-brain.service` | `simple` | Main AgentOS server; `python -m agentos` on `:7000`; user `uabrain` |
| `uab-telegram.service` | `simple` | Telegram adapter; `python -m channels.telegram_adapter`; depends on brain |
| `uab-live-judge.service` | `oneshot` | Live eval judge worker; `python -m agentos live-judge --once --limit 20` |
| `uab-live-judge.timer` | timer | Fires `uab-live-judge.service` on a schedule |
| `uab-digest.service` | `oneshot` | Daily digest; `curl POST /agents/curator/runs -F message=digest` |
| `uab-digest.timer` | timer | Fires `uab-digest.service` daily |
| `uab-monitor.service` | `oneshot` | Feed poll; `curl POST /agents/curator/runs -F message=poll_feeds` |
| `uab-monitor.timer` | timer | Fires `uab-monitor.service` on schedule |
| `uab-review.service` | `oneshot` | Weekly review; `curl POST /agents/curator/runs -F message=review` |
| `uab-review.timer` | timer | Fires `uab-review.service` weekly |

## Database Schema

The system uses Agno's standard schema across two databases:

**Sessions DB** (`POSTGRES_DSN_SESSIONS` / SQLite fallback — `id="ultra-brain-main"`):
- `ai.agno_sessions` — per-agent session records
- `ai.agno_memory` — extracted user memories (written by `InstrumentedMemoryManager`)
- `ai.agno_eval_runs` — eval rows (PERFORMANCE by `eval_recorder`; AGENT_AS_JUDGE by `live_judge`)
- `ai.agno_approvals` — HITL approval records (logged by `approval_recorder`)

**Knowledge DB** (`POSTGRES_DSN_KNOWLEDGE` — separate DSN):
- `vault` table in pgvector — vault note embeddings (`BAAI/bge-small-en-v1.5`, hybrid search)
- `ai.agno_knowledge` — knowledge content rows with sha256, `access_count`, metadata
- Populated by `python -m agentos.knowledge --reindex` and incrementally by `live_judge` after experience-note writes
