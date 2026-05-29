<!-- generated-by: gsd-doc-writer -->
# Getting Started — ultra-agents-brain

This guide gets the AgentOS server running locally and walks through common
interactions with each agent. A separate section covers VPS deployment via
systemd for production use.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | >= 3.13 | Project runs on 3.13.x |
| pip / venv | bundled with Python | Used to create `.venv` |
| LiteLLM proxy | running on port 4000 | Provides model tier aliases |
| NVIDIA NIM API key | — | Required by `orchestrator`, `research-worker`, and `default-worker` NIM fallback tiers. Free tier: 40 RPM per model, no expiry. Get one at [build.nvidia.com](https://build.nvidia.com) |
| PostgreSQL + pgvector | >= 15 (prod only) | Sessions and knowledge databases. Not required for local dev — SQLite fallback activates automatically when `POSTGRES_DSN_SESSIONS` is unset |

> **Local dev shortcut:** If you only have LiteLLM + an API key configured,
> the server starts with SQLite storage and a stub knowledge base. Full RAG
> requires PostgreSQL with pgvector.

---

## Local Setup

### 1. Clone and create a virtual environment

```bash
git clone <your-fork-url> ultra-agents-brain
cd ultra-agents-brain
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in the minimum required values:

```dotenv
# LiteLLM proxy (must be running on this address)
LITELLM_BASE_URL=http://127.0.0.1:4000/v1
LITELLM_MASTER_KEY=<your-litellm-master-key>

# At least one LLM provider key (NVIDIA NIM is needed for default/research tiers)
NVIDIA_NIM_API_KEY=<key-from-build.nvidia.com>

# Optional but recommended for full functionality
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

Everything else in `.env.example` is optional for a first local run.

### 4. Start the server

```bash
AGENTOS_PORT=7001 python -m agentos
```

> **Why 7001?** Port 7000 conflicts with macOS Control Center. The systemd
> service unit uses 7000 (no conflict on Linux); locally override to 7001.

The server starts a FastAPI/uvicorn process. You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:7001 (Press CTRL+C to quit)
```

---

## Agent Roster

The server exposes six agents/teams at `POST /agents/{id}/runs`.

| Agent ID | Role | Model tier |
|---|---|---|
| `chat` | Conversational front-end. Answers from vault, falls back to general knowledge with a `(general knowledge)` prefix. | `default-worker` |
| `curator` | Vault maintenance: daily digest, weekly review, lint, RSS feed polling. Invoked by systemd timers in production. | `cheap-worker` |
| `ingest` | Extracts content from URLs or files and writes notes to the vault. Uses HITL confirmation before writing. | `default-worker` |
| `query` | Strict vault retrieval — answers only from vault evidence with citations. Never invents. | `default-worker` |
| `research` | Multi-angle research using external sources + vault RAG. Aggregates findings into a vault note. | `research-worker` |
| `supervisor` | Orchestrator team. Decomposes requests and delegates to `query`, `ingest`, `research`, or `curator`. | `orchestrator` |

---

## Calling Agents

### curl

```bash
# Ask the chat agent a question
curl -s -X POST http://127.0.0.1:7001/agents/chat/runs \
  -F "message=What do my notes say about Agno?" \
  -F "stream=false" | python3 -m json.tool

# Query the vault strictly
curl -s -X POST http://127.0.0.1:7001/agents/query/runs \
  -F "message=Summarise my notes on RAG architectures" \
  -F "stream=false" | python3 -m json.tool

# Ingest a URL into the vault
curl -s -X POST http://127.0.0.1:7001/agents/ingest/runs \
  -F "message=https://example.com/interesting-article" \
  -F "stream=false" | python3 -m json.tool

# Research a topic
curl -s -X POST http://127.0.0.1:7001/agents/research/runs \
  -F "message=Research the current state of vector databases" \
  -F "stream=false" | python3 -m json.tool

# Run vault maintenance (digest / review / lint / poll_feeds)
curl -s -X POST http://127.0.0.1:7001/agents/curator/runs \
  -F "message=digest" \
  -F "stream=false" | python3 -m json.tool

# Delegate to the supervisor team
curl -s -X POST http://127.0.0.1:7001/agents/supervisor/runs \
  -F "message=Research agents in AI and add anything new to my vault" \
  -F "stream=false" | python3 -m json.tool
```

### httpie

```bash
http POST http://127.0.0.1:7001/agents/chat/runs \
  message="What do my notes say about Agno?" stream=false
```

### Agno hosted dashboard

The server registers with the Agno hosted dashboard at
`https://os.agno.com`. Open that URL, point it at
`http://127.0.0.1:7001`, and use the web UI to browse sessions, runs,
and memory.

---

## Eval System

Every agent run is recorded by the eval recorder. A background judge
worker scores pending rows against per-agent rubrics.

### Run the smoke eval suite (no Postgres required)

```bash
make eval-smoke
# or explicitly:
PYTHONPATH=. .venv/bin/pytest evals/ -k smoke -q
```

### Run the full eval suite

```bash
make eval-full
# Uses the orchestrator tier as judge — requires a working LiteLLM proxy.
```

### Check eval results

Eval rows are stored in the database alongside session data. To see a
summary of agent surface health:

```bash
make check-surfaces
```

### Write or update baselines

```bash
# First run: establish baselines
PYTHONPATH=. .venv/bin/pytest evals/ --write-baseline -q

# After intentional behaviour changes: update specific baselines
PYTHONPATH=. .venv/bin/pytest evals/ --update-baseline -q
```

### Live auto-scoring (local)

The live judge worker scores eval rows automatically. Run it once
manually:

```bash
python -m agentos live-judge --once --limit 20
```

Or keep it running in the background:

```bash
python -m agentos live-judge --loop --interval 60
```

On the VPS the `uab-live-judge.timer` systemd unit runs this every
2 minutes automatically (see VPS Deployment below).

---

## VPS Deployment

### Overview

Production runs on a Linux VPS under systemd. Key services:

| Unit | Purpose |
|---|---|
| `uab-brain.service` | AgentOS FastAPI server (port 7000, host 127.0.0.1) |
| `uab-telegram.service` | Telegram adapter channel (depends on `uab-brain`) |
| `uab-digest.timer` | Runs `curator/runs digest` daily at 20:00 |
| `uab-review.timer` | Weekly vault review |
| `uab-monitor.timer` | Periodic health monitoring |
| `uab-live-judge.timer` | Auto-scores eval rows every 2 minutes |

Unit files live in `deploy/systemd/`.

### Initial VPS setup

```bash
# On the VPS as root — create service user and project directory
useradd -r -s /usr/sbin/nologin uabrain
mkdir -p /opt/ultra-agents-brain
chown uabrain:uabrain /opt/ultra-agents-brain

# Clone the repo
git clone <repo-url> /opt/ultra-agents-brain
cd /opt/ultra-agents-brain

# Create virtualenv and install
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Copy and fill in the env file
cp .env.example .env
# Edit .env — set real keys and PostgreSQL DSNs
nano .env

# Install systemd units
cp deploy/systemd/*.service deploy/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
```

### Required env vars for production

These must be set in `/opt/ultra-agents-brain/.env` on the VPS:

```dotenv
LITELLM_BASE_URL=http://127.0.0.1:4000/v1
LITELLM_MASTER_KEY=<secret>
NVIDIA_NIM_API_KEY=<key>

POSTGRES_DSN_SESSIONS=postgresql+psycopg://uab:<password>@127.0.0.1:5432/agno_sessions
POSTGRES_DSN_KNOWLEDGE=postgresql+psycopg://uab:<password>@127.0.0.1:5432/agno_knowledge

TELEGRAM_BOT_TOKEN=<token>
TELEGRAM_ALLOWED_CHAT_IDS=<comma-separated-chat-ids>

SECOND_BRAIN_DIR=/srv/second-brain

# Enable auto-scoring
EVAL_LIVE_JUDGE_ENABLED=true
EVAL_LIVE_SAMPLE_RATE=1.0
```

### Enable and start services

```bash
systemctl enable --now uab-brain.service
systemctl enable --now uab-telegram.service
systemctl enable --now uab-digest.timer
systemctl enable --now uab-review.timer
systemctl enable --now uab-monitor.timer
systemctl enable --now uab-live-judge.timer
```

### Check service status

```bash
systemctl status uab-brain
journalctl -u uab-brain -f
```

### Deploy an update

```bash
cd /opt/ultra-agents-brain
git pull
.venv/bin/pip install -r requirements.txt
systemctl restart uab-brain uab-telegram
```

---

## Common Setup Issues

**`LITELLM_MASTER_KEY` not set — `litellm.exceptions.AuthenticationError`**
Set `LITELLM_MASTER_KEY` in `.env`. For local smoke tests a dummy value
works: `LITELLM_MASTER_KEY=test-key-for-evals`.

**Port 7000 already in use on macOS**
macOS Control Center binds port 7000. Use `AGENTOS_PORT=7001` when
starting locally.

**`POSTGRES_DSN_SESSIONS` not set — SQLite fallback warning in logs**
Expected for local dev. The server starts normally with SQLite at
`~/Documents/uab-state/agno.db`. Set the DSN only when you need full
session persistence or pgvector RAG.

**`sentence-transformers` install is slow**
It downloads model weights on first import. This is a one-time cost per
environment.

**Eval smoke tests fail with import errors**
Ensure `PYTHONPATH=.` is set and you are running from the project root
with the virtualenv activated.

---

## Next Steps

- See `docs/ARCHITECTURE.md` for the component diagram and data flow.
- See `docs/DEVELOPMENT.md` for the full build/lint/test workflow.
- Browse `evals/` to understand the per-agent evaluation rubrics.
- Browse `deploy/litellm/config.yaml` to configure or add model tier aliases.
