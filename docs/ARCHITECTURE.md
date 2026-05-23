<!-- generated-by: gsd-doc-writer -->
# Architecture

## System Overview

ultra-agents-brain is a personal second-brain system that hosts a fleet of AI agents over a local markdown vault. External input arrives from a Telegram channel or VPS cron jobs; each message is routed to one of five Agno agents (or the `supervisor` team that orchestrates them) exposed via an AgentOS FastAPI server, default port `7001` on macOS dev (Control Center occupies 7000). Agents read and write markdown notes in a local vault directory, use a LiteLLM proxy as a model-routing layer (local LM Studio + cloud providers + NVIDIA NIM), and persist session memory in **SqliteDb** locally or **PostgresDb** (with pgvector knowledge schema) on the VPS — `agentos/db.py` picks based on `POSTGRES_DSN_SESSIONS`. The Memory and Knowledge surfaces are wrapped by `agentos/instrumented_memory.py` and `agentos/instrumented_knowledge.py` for structured observability, and per-turn evals are recorded by `agentos/eval_recorder.py`. The system follows a layered architecture: a thin HTTP host (`agentos`) delegates to domain logic (`ultra_brain`) for vault I/O, extraction, research, and cost tracking.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      External Channels                       │
│   Telegram Bot  ─────────────────────  systemd Timers       │
└────────────┬────────────────────────────────────┬───────────┘
             │ POST /agents/{id}/runs              │ curl POST
             ▼                                     ▼
┌────────────────────────────────────────────────────────────┐
│           AgentOS FastAPI Host  (:7001 dev / :7000 prod)    │
│  agentos/app.py — Agno AgentOS: 5 agents + supervisor team │
│                                                            │
│  ┌──────┐ ┌──────┐ ┌─────┐ ┌────────┐ ┌──────┐ ┌────────┐│
│  │ chat │ │ingest│ │query│ │research│ │curate│ │supervis││
│  └──┬───┘ └──┬───┘ └──┬──┘ └────┬───┘ └──┬───┘ └────┬───┘│
└───────┼───────────┼──────────┼──────────┼──────────┼──────┘
        │           │          │          │          │
        ▼           ▼          ▼          ▼          ▼
┌───────────────────────────────────────────────────────────┐
│                agentos/tools/vault.py                      │
│      Plain-Python callables — bridge to ultra_brain        │
└───────────────────────┬───────────────────────────────────┘
                        │
        ┌───────────────┼───────────────────┐
        ▼               ▼                   ▼
┌──────────────┐ ┌─────────────┐  ┌────────────────┐
│ ultra_brain/ │ │ultra_brain/ │  │ ultra_brain/   │
│  query.py    │ │  ingest.py  │  │  research.py   │
│  vault.py    │ │  express.py │  │  cost.py       │
│  lint.py     │ │  markdown.py│  │  trust.py      │
│  review.py   │ │  telos.py   │  │  monitor.py    │
└──────┬───────┘ └──────┬──────┘  └────────────────┘
       │                │
       ▼                ▼
┌──────────────────────────────────────────────────┐
│              Markdown Vault (filesystem)          │
│   ~/Documents/second-brain  (git repo)           │
│   Rsync-synced to VPS copy                       │
└──────────────────────────────────────────────────┘

┌─────────────────────────────────────┐
│       LiteLLM Proxy  (:4000)        │
│   Routes to LM Studio / cloud       │
│   model groups: cheap-worker,       │
│   default-worker, smart-worker      │
└─────────────────────────────────────┘

┌────────────────────────────────────────────────┐
│  Session + Knowledge persistence (agentos/db.py)│
│  • SqliteDb at $UAB_DB_PATH (local/dev default) │
│  • PostgresDb id="ultra-brain-main" when        │
│    POSTGRES_DSN_SESSIONS set (VPS prod)         │
│  • pgvector schema agno_knowledge for vault RAG │
│  • Wrapped by InstrumentedMemory / Knowledge    │
│    and eval_recorder (Phase 11+ observability)  │
└────────────────────────────────────────────────┘
```

## Data Flow

A typical user message follows this path:

1. **Telegram adapter** sends `POST /agents/{agent_id}/runs` with JSON body to the AgentOS server (default `:7001` on macOS dev, `:7000` on Linux where Control Center isn't a conflict).
2. **AgentOS** (`agentos/app.py`) routes the run to the matching Agno `Agent` instance.
3. The agent calls its LLM via **`agentos/model.py`**, which resolves to an OpenAI-compatible endpoint on the **LiteLLM proxy** at `:4000`. LiteLLM selects the actual model (local LM Studio or a cloud provider) based on the requested model group (`cheap-worker`, `default-worker`, etc.).
4. The agent invokes one or more **tool callables** from `agentos/tools/vault.py` — for example `query_vault`, `ingest_to_vault`, or `research_topic`.
5. These callables delegate to **`ultra_brain`** domain modules (`query.py`, `ingest.py`, `research.py`, etc.) which perform actual vault I/O, web extraction, or markdown synthesis.
6. Results are written to the **markdown vault** on disk. Session state is persisted to **SQLite** via Agno's built-in session layer.
7. For tools marked `requires_confirmation=True` (e.g. `ingest_to_vault`), Agno pauses the run and returns `status=paused`. The Telegram adapter presents approve/deny buttons; on approval it sends `POST /runs/{run_id}/continue` to resume.
8. Curator runs (digest, review, lint, RSS poll) are triggered by **systemd timers** via direct curl POSTs — no Telegram involved.

## Key Abstractions

| Abstraction | File | Description |
|---|---|---|
| `AgentOS` | `agentos/app.py` | Agno's built-in multi-agent FastAPI host; exposes the standard Agno HTTP surface |
| `Agent` (×5) | `agentos/agents/` | Individual Agno agents: `chat`, `ingest`, `query`, `research`, `curator` — each with an explicit `id=` (Phase 11-01) for stable routing |
| Supervisor team | `agentos/agents/supervisor.py` | `make_supervisor_team()` — coordinates the 5 agents for multi-step tasks |
| `chat_model()` | `agentos/model.py` | Factory returning an `OpenAIChat` pointed at the LiteLLM proxy; accepts a model-tier string |
| `make_knowledge()` | `agentos/knowledge.py` | Knowledge factory; returns an `InstrumentedKnowledge` wrapper over Agno's `Knowledge` |
| `InstrumentedKnowledge` | `agentos/instrumented_knowledge.py` | Read-path observability wrapper for vault RAG (Phase 13-02) |
| `InstrumentedMemoryManager` | `agentos/instrumented_memory.py` | Structured logging of memory extraction decisions |
| `EvalRecorder` | `agentos/eval_recorder.py` | Per-turn evaluation capture into Postgres |
| `db` / `POSTGRES_DB` | `agentos/db.py` | SqliteDb always-on; PostgresDb (id=`ultra-brain-main`) when `POSTGRES_DSN_SESSIONS` set |
| Tool callables | `agentos/tools/vault.py` | Plain-Python bridge functions between Agno agents and `ultra_brain` modules |
| `ultra_brain.ingest` | `ultra_brain/ingest.py` | URL/file extraction pipeline (Jina always-on; crawl4ai via env var) and vault filing |
| `ultra_brain.query` | `ultra_brain/query.py` | Vault retrieval with `[[file.md:NNN]]` citation tokens |
| `ultra_brain.research` | `ultra_brain/research.py` | Multi-angle web research aggregated into a single vault note |
| `ultra_brain.cost` | `ultra_brain/cost.py` | LiteLLM success callback that writes per-call cost to a ledger |
| `ultra_brain.trust` | `ultra_brain/trust.py` | Trust-gate logic controlling autonomous action permissions |

## Directory Structure Rationale

```
ultra-agents-brain/
├── agentos/           # HTTP host layer — Agno AgentOS wiring, agents, tools
│   ├── agents/        # One file per Agno Agent definition
│   └── tools/         # Plain-Python tool callables passed to agents
├── ultra_brain/       # Domain logic layer — vault I/O, extraction, research, cost
├── deploy/            # Docker Compose files for LiteLLM and supporting services
├── scripts/           # Operational helpers: health check, cost check, smoke tests
├── ops/               # Vault rsync launchd plist and VPS bootstrap
├── tests/             # Pytest test suite (test_core.py, test_agentos.py, test_telegram_adapter.py)
├── plans/             # Markdown planning artifacts from development sessions
└── docs/runbooks/     # Operational runbooks
```

**`agentos/`** is the thin integration layer: it imports Agno primitives, wires agents to the shared db and model factory, and exposes the resulting FastAPI app. It contains no business logic.

**`ultra_brain/`** is the domain library: it can be imported and tested independently of Agno. All vault reads/writes, web extraction, markdown synthesis, cost tracking, and trust decisions live here.

**`deploy/`** holds Docker Compose configuration for the LiteLLM proxy (host-network mode so it can reach a locally-running LM Studio on `127.0.0.1:1234`) and any supporting containers.

**`ops/`** handles the vault sync side-channel: a launchd plist (`com.ultraagents.vault-sync.plist`) schedules rsync from the local `~/Documents/second-brain` git repo to a VPS copy.
