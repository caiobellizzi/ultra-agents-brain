<!-- generated-by: gsd-doc-writer -->
# Architecture

## System Overview

ultra-agents-brain is a personal second-brain system that hosts a fleet of AI agents over a local markdown vault. External input arrives from a Telegram channel or systemd cron timers; each message is routed to one of five Agno agents exposed via an AgentOS FastAPI server running on port 7000. Agents read and write markdown notes in a local vault directory, use a LiteLLM proxy as a model-routing layer (supporting local LM Studio models alongside cloud providers), and persist session memory in a shared SQLite database. The system follows a layered architecture: a thin HTTP host (`agentos`) delegates to domain logic (`ultra_brain`) for vault I/O, extraction, research, and cost tracking.

## Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      External Channels                       │
│   Telegram Bot  ─────────────────────  systemd Timers       │
└────────────┬────────────────────────────────────┬───────────┘
             │ POST /agents/{id}/runs              │ curl POST
             ▼                                     ▼
┌────────────────────────────────────────────────────────────┐
│              AgentOS FastAPI Host  (:7000)                  │
│  agentos/app.py — Agno AgentOS wrapping five agents        │
│                                                            │
│  ┌──────────┐ ┌────────┐ ┌───────┐ ┌──────────┐ ┌──────┐ │
│  │  chat    │ │ ingest │ │ query │ │ research │ │curate│ │
│  └────┬─────┘ └───┬────┘ └───┬───┘ └────┬─────┘ └──┬───┘ │
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

┌──────────────────────────────┐
│  SQLite DB  (uab-state/)     │
│  Shared session memory for   │
│  all Agno agents             │
└──────────────────────────────┘
```

## Data Flow

A typical user message follows this path:

1. **Telegram adapter** sends `POST /agents/{agent_id}/runs` with JSON body to the AgentOS server at `:7000`.
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
| `Agent` (×5) | `agentos/agents/` | Individual Agno agents: `chat`, `ingest`, `query`, `research`, `curator` |
| `chat_model()` | `agentos/model.py` | Factory returning an `OpenAIChat` pointed at the LiteLLM proxy; accepts a model-tier string |
| `VaultKnowledge` | `agentos/knowledge.py` | Thin Agno `Knowledge` wrapper that enumerates vault markdown files |
| `SqliteDb` | `agentos/db.py` | Shared Agno session database; one instance used by all agents |
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
