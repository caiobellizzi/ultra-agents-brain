<!-- generated-by: gsd-doc-writer -->
# Configuration

This document covers all environment variables, config files, and per-environment overrides for ultra-agents-brain.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the required secrets before running any component.

```bash
cp .env.example .env
```

### LiteLLM Proxy

| Variable | Required | Default | Description |
|---|---|---|---|
| `LITELLM_MASTER_KEY` | **Required** | — | Auth key for all requests to the LiteLLM proxy. Startup fails if absent. |
| `LITELLM_BASE_URL` | Optional | `http://127.0.0.1:4000/v1` | Base URL of the LiteLLM proxy (OpenAI-compatible). |
| `LITELLM_IMAGE` | Optional | `ghcr.io/berriai/litellm:main-latest` | Docker image used for the proxy container. |
| `LITELLM_PORT` | Optional | `4000` | Host port the LiteLLM container exposes. |

### LM Studio (local model server)

| Variable | Required | Default | Description |
|---|---|---|---|
| `LM_STUDIO_API_BASE` | Optional | `http://localhost:1234/v1` | LM Studio OpenAI-compatible endpoint. Use the LM Link URL when accessing from a VPS. |
| `LM_STUDIO_API_KEY` | Optional | `lm-studio` | API key sent to LM Studio (any non-empty string is accepted). |
| `LM_STUDIO_MODEL` | Optional | `lm-studio-primary` | Model identifier as shown in LM Studio (e.g. `qwen3-32b-mlx`). Maps to the `orchestrator` / `default-worker` tiers. |
| `LM_STUDIO_FAST_MODEL` | Optional | `lm-studio-fast` | Lighter model for the `cheap-worker` tier. Falls back to `LM_STUDIO_MODEL` if not set. |

### Cloud LLM fallbacks

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Optional | — | Used by the `cloud-sonnet` fallback tier. Required in production if LM Studio is unreachable. |
| `OPENAI_API_KEY` | Optional | — | Available for future OpenAI-routed tiers. Not wired to a tier in v1. |
| `GROQ_API_KEY` | Optional | — | Used by the `cloud-groq` fallback tier (`llama-3.3-70b-versatile`). |
| `OPENROUTER_API_KEY` | Optional | — | Available for OpenRouter-backed tiers. Not wired in v1. |

### AgentOS server

| Variable | Required | Default | Description |
|---|---|---|---|
| `AGENTOS_HOST` | Optional | `127.0.0.1` | Bind address for the AgentOS FastAPI server. |
| `AGENTOS_PORT` | Optional | `7000` | Port for the AgentOS FastAPI server. <!-- VERIFY: production port may differ — was remapped to 7001 on macOS dev to avoid ControlCenter conflict --> |

### Persistence paths

| Variable | Required | Default | Description |
|---|---|---|---|
| `UAB_DB_PATH` | Optional | `~/Documents/uab-state/agno.db` | SQLite database path for Agno agent session memory. |
| `UAB_VAULT_PATH` | Optional | `./vault` | Path to the Obsidian vault used by vault tools. Overrides `SECOND_BRAIN_DIR` if both are set. |
| `SECOND_BRAIN_DIR` | Optional | `/srv/second-brain` | Fallback vault path and cost ledger root (production convention). |
| `COST_LEDGER` | Optional | `/srv/second-brain/_system/cost-ledger.md` | Markdown file where cost accounting is appended. |
| `UAB_LOG_DIR` | Optional | `/var/log/ultra-agents-brain` | Log directory used by systemd service units. |
| `UAB_PROJECT_ROOT` | Optional | `/opt/ultra-agents-brain` | Root directory used in deploy scripts and systemd units. |
| `UAB_SERVICE_USER` | Optional | `uabrain` | System user that owns the deployed service processes. |

### Cost controls

| Variable | Required | Default | Description |
|---|---|---|---|
| `DAILY_COST_CAP_USD` | Optional | `20` | Maximum daily spend in USD before requests are blocked. |
| `ALLOW_DIRTY_VAULT` | Optional | `0` | Set to `1` to skip vault git-clean checks. Default `0` enforces clean state. |
| `VAULT_COST_WARNING_USD` | Optional | `16` | Cost threshold (USD) that triggers a warning before the hard cap. |
| `HEALTH_NOTIFY_ON_SUCCESS` | Optional | `0` | Set to `1` to send Telegram health notifications even on successful runs. |

### Telegram integration

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Optional | — | Bot token from BotFather. Required for Telegram HITL approval/deny flow. |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Optional | — | Comma-separated list of chat IDs that may interact with the bot. |
| `TELEGRAM_ALERT_CHAT_ID` | Optional | — | Chat ID that receives proactive alerts and cost notifications. |
| `TELEGRAM_WEBHOOK_SECRET` | Optional | — | Secret used to validate incoming Telegram webhook requests. |

### Hermes agent container

| Variable | Required | Default | Description |
|---|---|---|---|
| `HERMES_IMAGE` | Optional | `ghcr.io/nousresearch/hermes-agent:v2026.5.16` | Docker image for the Hermes agent. |
| `HERMES_HTTP_PORT` | Optional | `8787` | Host port exposed by the Hermes container. |
| `HERMES_CONFIG_DIR` | Optional | `/opt/ultra-agents-brain/hermes` | Config directory mounted into the Hermes container. |
| `HERMES_SKILLS_DIR` | Optional | `/opt/ultra-agents-brain/hermes/skills` | Skills directory mounted into the Hermes container. |
| `HERMES_STATE_DIR` | Optional | `/var/lib/ultra-agents-brain/hermes` | Persistent state directory for the Hermes container. |
| `HERMES_TELEGRAM_WEBHOOK_URL` | Optional | — | Public URL Telegram POSTs to for Hermes webhook delivery. <!-- VERIFY: must be an HTTPS URL reachable by Telegram servers --> |
| `HERMES_RELEASE_TAG` | Optional | `v2026.5.16` | Hermes image tag used by vault sync scripts. |

### Vault sync

| Variable | Required | Default | Description |
|---|---|---|---|
| `VAULT_REMOTE_URL` | Optional | — | Git remote URL for the vault repository. |
| `VAULT_VPS_PATH` | Optional | — | Absolute path to the vault checkout on the VPS. |
| `VAULT_MAC_PATH` | Optional | — | Absolute path to the vault checkout on the development Mac. |
| `VAULT_DEFAULT_BRANCH` | Optional | `main` | Default branch used by vault sync scripts. |

### Crawl4AI

| Variable | Required | Default | Description |
|---|---|---|---|
| `CRAWL4AI_MCP_URL` | Optional | `http://127.0.0.1:11235/mcp` | MCP endpoint for the local Crawl4AI Docker container. |

---

## Config File: `deploy/litellm/config.yaml`

The LiteLLM proxy is configured via `deploy/litellm/config.yaml`. This file defines the model tiers, timeouts, and fallback chains. All secrets are read from environment variables at runtime — no secrets are hardcoded.

### Model tiers

| Tier name | Purpose | Timeout |
|---|---|---|
| `orchestrator` | Heavy reasoning tasks | 300 s |
| `default-worker` | Standard agent tasks | 300 s |
| `cheap-worker` | Fast / low-cost tasks | 180 s |
| `private-worker` | Local-only sensitive tasks | 300 s |
| `cloud-sonnet` | Cloud fallback (`claude-sonnet-4-6`) | 120 s |
| `cloud-groq` | Cloud fallback (`llama-3.3-70b-versatile`) | 90 s |

All local tiers route to LM Studio via `LM_STUDIO_API_BASE`. Cloud tiers activate automatically through the fallback chain when LM Studio is unreachable.

### Fallback chain (configured in `litellm_settings.fallbacks`)

```
orchestrator    → cloud-sonnet
default-worker  → cloud-sonnet → cloud-groq
cheap-worker    → default-worker → cloud-groq
private-worker  → cheap-worker
```

### Minimal working example

```yaml
model_list:
  - model_name: default-worker
    litellm_params:
      model: openai/<your-lm-studio-model-id>
      api_base: os.environ/LM_STUDIO_API_BASE
      api_key: os.environ/LM_STUDIO_API_KEY

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
```

---

## Required vs Optional Settings

The following variables cause startup failure if absent:

| Variable | Component | Error |
|---|---|---|
| `LITELLM_MASTER_KEY` | `agentos/model.py` | `KeyError: 'LITELLM_MASTER_KEY'` — hard `os.environ["LITELLM_MASTER_KEY"]` lookup with no default |

All other variables have defaults or are purely optional integrations (Telegram, cloud keys, vault sync).

---

## Per-Environment Overrides

| Environment | Approach |
|---|---|
| **Local development (Mac)** | `LM_STUDIO_API_BASE=http://localhost:1234/v1`. Use `lm-studio` as `LM_STUDIO_API_KEY`. Cloud keys optional. |
| **VPS / production** | `LM_STUDIO_API_BASE` set to the LM Link endpoint from LM Studio. `SECOND_BRAIN_DIR=/srv/second-brain`. Systemd unit reads `.env` from `UAB_PROJECT_ROOT`. |
| **macOS port conflict** | `AGENTOS_PORT=7001` to avoid conflict with macOS ControlCenter which occupies port 7000. |

There are no `.env.development` or `.env.production` files — all overrides are applied by editing the single `.env` file on each host.
