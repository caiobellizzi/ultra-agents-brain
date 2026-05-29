<!-- generated-by: gsd-doc-writer -->
# ultra-agents-brain

A self-hosted, multi-agent second brain built on [Agno](https://github.com/agno-agi/agno) and LiteLLM. Six specialized agents — coordinated by a supervisor team — read and write an Obsidian vault, answer questions, ingest new content, run research, and score themselves with a timer-fired LLM eval judge.

## Install

```bash
git clone <repo-url> ultra-agents-brain
cd ultra-agents-brain
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill secrets
```

**Runtime requirements:** Python 3.11+, PostgreSQL (prod) or SQLite (local), LiteLLM proxy.

## Configuration

Copy `.env.example` to `.env` and populate the required variables:

| Variable | Required | Default | Description |
|---|---|---|---|
| `LITELLM_MASTER_KEY` | Yes | — | LiteLLM proxy master key |
| `LITELLM_BASE_URL` | No | `http://127.0.0.1:4000/v1` | LiteLLM proxy base URL |
| `ANTHROPIC_API_KEY` | Yes* | — | Anthropic provider key |
| `OPENAI_API_KEY` | Yes* | — | OpenAI provider key |
| `NVIDIA_NIM_API_KEY` | Yes* | — | NVIDIA NIM key (orchestrator/research tiers) |
| `GROQ_API_KEY` | No | — | Groq provider key |
| `OPENROUTER_API_KEY` | No | — | OpenRouter provider key |
| `TELEGRAM_BOT_TOKEN` | No | — | Telegram bot token |
| `TELEGRAM_ALLOWED_CHAT_IDS` | No | — | Comma-separated allowed chat IDs |
| `SECOND_BRAIN_DIR` | No | `./vault` | Path to the Obsidian vault |
| `POSTGRES_DSN_SESSIONS` | No | SQLite fallback | PostgreSQL DSN for agent sessions |
| `POSTGRES_DSN_KNOWLEDGE` | No | — | PostgreSQL DSN for vector knowledge base |
| `EVAL_LIVE_JUDGE_ENABLED` | No | `false` | Enable timer-fired LLM eval scoring |
| `EVAL_LIVE_SAMPLE_RATE` | No | `0.0` | Fraction of runs to score (0.0–1.0) |
| `AGENTOS_HOST` | No | `127.0.0.1` | FastAPI bind host |
| `AGENTOS_PORT` | No | `7000` | FastAPI bind port |

\* At least one LLM provider key is required; which ones depend on your LiteLLM `config.yaml`.

## Running

### Local dev

```bash
# Start LiteLLM proxy first (separate terminal)
python -m agentos                 # FastAPI on http://127.0.0.1:7000

# One-shot eval judge pass
python -m agentos live-judge --once

# Continuous eval judge loop
python -m agentos live-judge --loop --interval 60
```

### Tests

```bash
make test          # unit tests (excludes test_core.py)
make eval-smoke    # fast smoke evals
make eval-full     # full eval suite with orchestrator judge tier
make check-surfaces  # surface smoke-check script
```

### VPS (systemd)

```bash
# Deploy and enable all units
systemctl enable --now uab-brain.service
systemctl enable --now uab-telegram.service
systemctl enable --now uab-live-judge.timer   # fires every 2 min
systemctl enable --now uab-digest.timer
systemctl enable --now uab-monitor.timer
systemctl enable --now uab-review.timer
```

All services run as user `uabrain`, read from `/opt/ultra-agents-brain/.env`, and write to `/srv/second-brain` and `/var/lib/uab`.

## Agent Roster

| Agent | Type | Model tier | Role |
|---|---|---|---|
| **supervisor** | `Team` | `orchestrator` | Routes requests to leaf agents; central entry point |
| **chat** | `Agent` | `default-worker` | Answers from the vault; falls back to general chat |
| **query** | `Agent` | `default-worker` | Strict vault RAG with citations |
| **research** | `Agent` | `research-worker` | Multi-angle research with ReasoningTools + vault RAG |
| **ingest** | `Agent` | `default-worker` | Ingests URLs and files into the vault |
| **curator** | `Agent` | `cheap-worker` | Daily digest, weekly review, RSS polling, vault lint |

All five leaf agents have `enable_agentic_culture=True`, allowing them to read shared experience notes and adapt behaviour over time.

## Architecture

```
Telegram / HTTP client
        │
        ▼
  channels/telegram_adapter  ──►  AgentOS FastAPI (port 7000)
                                         │
                              ┌──────────┴──────────┐
                              │     supervisor Team  │  (orchestrator tier)
                              └──┬──┬──┬──┬──┬──────┘
                                 │  │  │  │  │
                   chat ─────────┘  │  │  │  └─── curator
                   query ───────────┘  │  └─────── ingest
                   research ───────────┘

        All agents ──► LiteLLM proxy ──► provider APIs
        All agents ──► Postgres (sessions) + Postgres/SQLite (knowledge)
        All agents ──► /srv/second-brain  (Obsidian vault)

  eval_recorder (monkey-patch on Agent/Team.run / .arun)
        │ writes eval rows
        ▼
  DB (eval_runs table)
        │ polled every 2 min
        ▼
  live_judge (uab-live-judge.timer)
        │ LLM judge scores each row
        ▼
  vault/_system/experience/  (experience notes)
```

## Eval System

The eval pipeline runs continuously in the background:

1. **`eval_recorder`** — monkey-patches `Agent.run` / `arun` at class level; writes a row to the eval DB for every agent invocation.
2. **`eval_rubrics`** — defines per-agent rubrics (`chat-helpfulness-v1`, `query-groundedness-v1`, `ingest-fidelity-v1`, `curator-quality-v1`, `research-grounding-v1`).
3. **`eval_live_policy`** — controls sampling rate and enabled state via env vars (`EVAL_LIVE_JUDGE_ENABLED`, `EVAL_LIVE_SAMPLE_RATE`).
4. **`live_judge`** — timer-fired worker (`uab-live-judge.timer`, every 2 min) that runs an LLM judge against pending rows and writes scores back to the DB and experience notes to the vault.

Enable auto-scoring on the VPS:

```bash
# In /opt/ultra-agents-brain/.env
EVAL_LIVE_JUDGE_ENABLED=true
EVAL_LIVE_SAMPLE_RATE=1.0   # safe for low-traffic; use 0.1–0.3 for high-traffic
```

## Systemd Units

| Unit | Type | Description |
|---|---|---|
| `uab-brain.service` | service | AgentOS FastAPI server |
| `uab-telegram.service` | service | Telegram adapter |
| `uab-live-judge.service` + `.timer` | oneshot + timer | Eval judge, every 2 min |
| `uab-digest.service` + `.timer` | oneshot + timer | Daily digest via curator |
| `uab-monitor.service` + `.timer` | oneshot + timer | Feed monitor via curator |
| `uab-review.service` + `.timer` | oneshot + timer | Weekly review via curator |

## Contributing

```bash
# Lint / format
pre-commit run --all-files

# Run tests before pushing
make test && make eval-smoke
```

See `docs/` for architecture deep-dives and phase retrospectives.
