<!-- generated-by: gsd-doc-writer -->
# Getting Started

## Prerequisites

- **Python 3.11+** — the project uses features not available in earlier versions
- **Docker and Docker Compose** — required to run the LiteLLM proxy service
- **Git** — to clone the repository
- At least one LLM provider API key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`, or `OPENROUTER_API_KEY`), or a local LM Studio instance

## Installation Steps

1. Clone the repository:

```bash
git clone <repo-url>
cd ultra-agents-brain
```

2. Create and activate a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

4. Copy the environment template and fill in required values:

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

- `LITELLM_MASTER_KEY` — a secret key you choose for the proxy
- `ANTHROPIC_API_KEY` (or another provider key)
- `SECOND_BRAIN_DIR` — absolute path to your local Markdown vault
- `COST_LEDGER` — absolute path to the cost ledger Markdown file
- `DAILY_COST_CAP_USD` — spending cap in USD (default: `20`)

See [CONFIGURATION.md](CONFIGURATION.md) for the full variable reference.

## First Run

Start the LiteLLM proxy (required before running any agent or CLI command):

```bash
docker compose -f deploy/docker-compose.yml up -d
```

Then verify the setup with a simple vault query:

```bash
python -m ultra_brain query "Hello, what is in my vault?"
```

If the vault is empty, ingest a file first:

```bash
python -m ultra_brain ingest path/to/note.md
```

To run the AgentOS HTTP API (FastAPI on port 7001):

```bash
uvicorn agentos.app:app --host 0.0.0.0 --port 7001
```

## Common Setup Issues

**LiteLLM proxy not reachable (`LITELLM_BASE_URL` connection refused)**
The proxy must be running before any CLI command or API call. Confirm it is up:
```bash
docker compose -f deploy/docker-compose.yml ps
```
If the container is not running, check `docker compose -f deploy/docker-compose.yml logs litellm` for errors.

**Port 7001 already in use**
macOS Control Center previously used port 7000; 7001 is the configured AgentOS port. If 7001 is taken by another process, find it with `lsof -i :7001` and stop it, or pass `--port <other>` to uvicorn and update `AGENTOS_BASE_URL` in `.env`.

**Missing `SECOND_BRAIN_DIR`**
The vault path must exist on disk before running any command. Create it or point the variable at an existing Markdown directory:
```bash
mkdir -p ~/Documents/second-brain
```

**`LITELLM_MASTER_KEY` not set**
The proxy will reject all requests without this key. Set it in `.env` to any non-empty string (treat it as a secret).

## Next Steps

- [CONFIGURATION.md](CONFIGURATION.md) — full environment variable reference
- [ARCHITECTURE.md](ARCHITECTURE.md) — system layers, component diagram, and data flow
