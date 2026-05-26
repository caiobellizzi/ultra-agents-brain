<!-- generated-by: gsd-doc-writer -->
# ultra-agents-brain

A second-brain agent system that runs AI agents over a local Markdown vault, exposed via an AgentOS HTTP API and a Telegram bot interface.

## Installation

Requires Python 3.11+.

```bash
git clone <repo-url>
cd ultra-agents-brain
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Copy the environment template and fill in secrets:

```bash
cp .env.example .env
```

## Quick Start

1. Start the LiteLLM proxy and AgentOS services:

```bash
docker compose -f deploy/docker-compose.yml up -d
```

2. Run the AgentOS host (FastAPI):

```bash
uvicorn agentos.app:app --host 0.0.0.0 --port 7001
```

3. Run a CLI command against the vault:

```bash
python -m ultra_brain query "What did I write about X?"
```

## Usage Examples

**Ingest a file into the knowledge base:**

```bash
python -m ultra_brain ingest path/to/note.md
```

**Query the vault with a natural-language question:**

```bash
python -m ultra_brain query "Summarize my notes on project planning"
```

**Check LLM spending against the daily cap:**

```bash
python -m ultra_brain cost-summary
```

**Run a telos alignment check:**

```bash
python -m ultra_brain telos-check
```

## CLI Commands

| Command | Description |
|---|---|
| `ensure-vault` | Verify vault directory is present and accessible |
| `ingest` | Ingest a URL or Markdown file into the vault |
| `query` | Query the vault with a natural-language question |
| `lint` | Lint vault Markdown files (writes `vault/_system/lint-report.md`) |
| `digest` | Generate a daily digest from vault contents |
| `daily-brief` | Synthesize the day's brief and deliver it to Telegram (`--no-telegram` to skip) |
| `cost-summary` | Print LLM spending summary from the cost ledger |
| `research-plan` | Plan a multi-worker research run for a topic |
| `research-aggregate` | Aggregate worker outputs into a Research project under `vault/Projects/Research/` |
| `telos-check` | Score an action against the stored telos doc |
| `telos-interview` | Interactive telos capture interview |
| `monitor` | Poll configured RSS feeds and file new items to `vault/_inbox/` |
| `bluesky` | Poll configured Bluesky handles and file new posts to `vault/_inbox/` |
| `review` | Write a weekly strategic review to `vault/_system/weekly-review.md` |

For operator-side flows (cadence, recovery, adding sources) see [docs/MAINTENANCE.md](docs/MAINTENANCE.md).
For the source-to-vault map see [docs/SOURCES.md](docs/SOURCES.md).

## Architecture

The system has three runtime layers:

- **AgentOS** (`agentos/`) — FastAPI app hosting six Agno surfaces: agents `chat`, `ingest`, `query`, `research`, `curator`, plus a `supervisor` team (`agentos/agents/supervisor.py`) that delegates across them. Exposes the standard Agno HTTP surface compatible with the hosted dashboard at `https://os.agno.com`. Default bind port `7001` (macOS Control Center occupies 7000).
- **LiteLLM proxy** — Docker service that routes model calls across a 5-tier matrix (Agno dashboard reports `provider: LiteLLM` for every agent; the real upstream depends on the tier): `orchestrator` (NVIDIA NIM DeepSeek V4 Pro → GLM-5.1 → cloud-sonnet), `research-worker` (NIM DeepSeek V4 Flash → Llama 3.1 405B → cloud-sonnet), `default-worker` (local LM Studio Gemma → NIM Llama 3.3 70B → Mistral 2 Large → cloud-groq), `cheap-worker` and `private-worker` (local-only). NIM is treated as cloud-allowed (equivalent privacy posture to Anthropic/Groq); `private-worker` stays strictly local by contract.
- **Telegram bot / channels** — Calls `POST /agents/{agent_id}/runs` on the AgentOS host. Configured via `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_CHAT_IDS`.

The `ultra_brain/` package provides standalone CLI wrappers and reusable helpers (cost tracking, vault sync, trust checks, Markdown utilities) that the agents and scripts share.

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and fill in values.

Key variables:

| Variable | Required | Description |
|---|---|---|
| `LITELLM_BASE_URL` | Yes | LiteLLM proxy endpoint (default: `http://127.0.0.1:4000/v1`) |
| `LITELLM_MASTER_KEY` | Yes | Auth key for LiteLLM proxy |
| `ANTHROPIC_API_KEY` | — | Anthropic API key (at least one provider key required) |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `GROQ_API_KEY` | — | Groq API key |
| `OPENROUTER_API_KEY` | — | OpenRouter API key |
| `NVIDIA_NIM_API_KEY` | — | NVIDIA NIM (build.nvidia.com) API key — free 40 RPM/model; required for `orchestrator`, `research-worker`, and `default-worker` NIM fallback aliases |
| `XAI_API_KEY` | — | xAI Grok (api.x.ai) API key — placeholder; requires paid credits before any `xai/grok-*` alias can be added to LiteLLM config |
| `LITELLM_ORCHESTRATOR_MODEL` / `LITELLM_RESEARCH_MODEL` / `LITELLM_DEFAULT_MODEL` / `LITELLM_CHEAP_MODEL` / `LITELLM_PRIVATE_MODEL` | — | Per-tier LiteLLM alias overrides (default to the tier name itself) |
| `LM_STUDIO_API_BASE` | — | LM Studio local endpoint |
| `TELEGRAM_BOT_TOKEN` | — | Telegram bot token for the channel adapter |
| `TELEGRAM_ALLOWED_CHAT_IDS` | — | Comma-separated list of allowed Telegram chat IDs |
| `SECOND_BRAIN_DIR` | Yes | Path to the local Markdown vault |
| `WORKSHOP_REPO_REGISTRY` | — | Path to the Workshop repo registry JSON persisted via the localhost `PUT /workshop/repos` route (default: `/srv/second-brain/_system/workshop-repos.json`) |
| `COST_LEDGER` | Yes | Path to the cost ledger Markdown file |
| `DAILY_COST_CAP_USD` | Yes | Hard daily spending cap in USD (default: `20`) |

See `.env.example` for the full list including vault sync and deployment settings.

## License

Private — all rights reserved.
