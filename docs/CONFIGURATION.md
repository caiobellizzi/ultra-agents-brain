<!-- generated-by: gsd-doc-writer -->
# Configuration

This document covers all environment variables, config files, and per-environment overrides for ultra-agents-brain.

---

## Environment Variables

Copy `.env.example` to `.env` and fill in the required secrets before running any component.

```bash
cp .env.example .env
```

### Core / AgentOS server

| Variable | Required | Default | Description |
|---|---|---|---|
| `AGENTOS_HOST` | Optional | `127.0.0.1` | Bind address for the AgentOS FastAPI server. |
| `AGENTOS_PORT` | Optional | `7001` | Port for the AgentOS FastAPI server. Default `7001` avoids macOS Control Center which occupies 7000; safe to set to `7000` on Linux/VPS (the `uab-brain.service` systemd unit hardcodes `7000` for production). |
| `AGENTOS_BASE_URL` | Optional | `http://127.0.0.1:7000` | Base URL used by the Telegram adapter service to reach AgentOS. Set in `uab-telegram.service`. |

### Database / persistence

| Variable | Required | Default | Description |
|---|---|---|---|
| `UAB_DB_PATH` | Optional | `~/Documents/uab-state/agno.db` | SQLite database path for Agno agent session memory. Always-on; used as fallback when `POSTGRES_DSN_SESSIONS` is not set. |
| `POSTGRES_DSN_SESSIONS` | Optional | — | When set, activates `PostgresDb(id="ultra-brain-main")` for the chat session schema (`agno_sessions`) and the eval runs table (`ai.agno_eval_runs`). Required in production. Format: `postgresql+psycopg://uab:<password>@127.0.0.1:5432/agno_sessions`. |
| `POSTGRES_DSN_KNOWLEDGE` | Optional | — | DSN for the pgvector knowledge schema (`agno_knowledge`). Required for vault RAG on the VPS. Format: `postgresql+psycopg://uab:<password>@127.0.0.1:5432/agno_knowledge`. |
| `SECOND_BRAIN_DIR` | Optional | `/srv/second-brain` | Vault path (production convention). The CLI's `--vault` flag overrides this; on local Mac the `vault/` symlink in the project root handles it. Also used by `live_judge.py` as the base path for writing experience notes to `<SECOND_BRAIN_DIR>/_system/experiences/<agent_id>/`. |
| `COST_LEDGER` | Optional | `/srv/second-brain/_system/cost-ledger.md` | Markdown file where cost accounting is appended. |
| `UAB_LOG_DIR` | Optional | `/var/log/ultra-agents-brain` | Log directory used by systemd service units. |
| `UAB_PROJECT_ROOT` | Optional | `/opt/ultra-agents-brain` | Root directory used in deploy scripts and systemd units. |
| `UAB_SERVICE_USER` | Optional | `uabrain` | System user that owns the deployed service processes. |

### LiteLLM proxy

| Variable | Required | Default | Description |
|---|---|---|---|
| `LITELLM_MASTER_KEY` | **Required** | — | Auth key for all requests to the LiteLLM proxy. Startup fails if absent (`KeyError` in `agentos/model.py`). |
| `LITELLM_BASE_URL` | Optional | `http://127.0.0.1:4000/v1` | Base URL of the LiteLLM proxy (OpenAI-compatible). |
| `LITELLM_IMAGE` | Optional | `ghcr.io/berriai/litellm:main-stable` | Docker image used for the proxy container. Pinned to a tag that includes the fix for LiteLLM #23970 (preserves `nvidia_nim/` prefix on slashed model IDs). |
| `LITELLM_PORT` | Optional | `4000` | Host port the LiteLLM container exposes. |

### LiteLLM tier aliases (per-agent overrides)

Each agent reads a tier-alias env var; defaults match the tier name in `deploy/litellm/config.yaml`. Override only if you point a tier at a different LiteLLM deployment.

| Variable | Default | Used by |
|---|---|---|
| `LITELLM_ORCHESTRATOR_MODEL` | `orchestrator` | supervisor team, heavy reasoning |
| `LITELLM_RESEARCH_MODEL` | `research-worker` | `worker.research`, multi-angle research |
| `LITELLM_DEFAULT_MODEL` | `default-worker` | standard agent runs |
| `LITELLM_CHEAP_MODEL` | `cheap-worker` | fast/low-cost tasks |
| `LITELLM_PRIVATE_MODEL` | `private-worker` | local-only sensitive tasks |

### LM Studio (local model server)

| Variable | Required | Default | Description |
|---|---|---|---|
| `LM_STUDIO_API_BASE` | Optional | `http://localhost:1234/v1` | LM Studio OpenAI-compatible endpoint. Use the LM Link URL when accessing from a VPS. |
| `LM_STUDIO_API_KEY` | Optional | `lm-studio` | API key sent to LM Studio (any non-empty string is accepted). |
| `LM_STUDIO_MODEL` | Optional | `lm-studio-primary` | Model identifier (as shown in LM Studio, e.g. `qwen3-32b-mlx`). Maps to the `orchestrator` / `default-worker` tiers. |
| `LM_STUDIO_FAST_MODEL` | Optional | `lm-studio-fast` | Lighter model for the `cheap-worker` tier. Falls back to `LM_STUDIO_MODEL` if not set. |

### Cloud LLM fallbacks

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Optional | — | Used by the `cloud-sonnet` fallback tier. Required in production if LM Studio is unreachable. |
| `OPENAI_API_KEY` | Optional | — | Available for future OpenAI-routed tiers. Not wired to a tier in v1. |
| `GROQ_API_KEY` | Optional | — | Used by the `cloud-groq` fallback tier (`llama-3.3-70b-versatile`). |
| `OPENROUTER_API_KEY` | Optional | — | Available for OpenRouter-backed tiers. Not wired in v1. |
| `NVIDIA_NIM_API_KEY` | Optional | — | NVIDIA NIM (build.nvidia.com) — free tier 40 RPM/model. **Required** by orchestrator, research-worker, and default-worker NIM fallback aliases. |
| `XAI_API_KEY` | Optional | — | xAI Grok (api.x.ai). Placeholder — purchase credits at console.x.ai before adding `xai/grok-*` aliases to `deploy/litellm/config.yaml`. |

### Eval system

These variables control the live judge worker (`agentos/live_judge.py`) and the recorder policy (`agentos/eval_live_policy.py`). All default to disabled/zero so the production request path is never slowed by judging.

| Variable | Required | Default | Description |
|---|---|---|---|
| `EVAL_LIVE_JUDGE_ENABLED` | Optional | `false` | Set to `true` on the VPS to enable automatic scoring of recorded performance rows. When `false`, the recorder marks rows but `live_judge` never runs. |
| `EVAL_LIVE_SAMPLE_RATE` | Optional | `0.0` | Fraction of eligible runs to judge (0.0–1.0). `1.0` is safe for low-traffic deployments using a local Gemma judge. Sampling is deterministic via SHA-256 of `agent_id:run_id`. |
| `EVAL_LIVE_SAMPLE_RATE_<AGENT>` | Optional | — | Per-agent sample rate override. Replace `<AGENT>` with the uppercased agent ID (e.g. `EVAL_LIVE_SAMPLE_RATE_CURATOR=0.5`). Takes precedence over the global rate for that agent. |
| `EVAL_LIVE_MAX_ATTEMPTS` | Optional | `3` | Maximum judge attempts per row before it is marked `failed_max_attempts` and skipped permanently. |
| `EVAL_LIVE_ALLOW_CONTENT_READ` | Optional | `false` | Set to `true` to allow the judge to read full message content for agents that normally restrict it (e.g. `ingest`). Default redacts output to metadata shape only for those agents. |
| `EVAL_LIVE_MAX_PAYLOAD_CHARS` | Optional | `12000` | Maximum total character length of the judge payload. Rows exceeding this are skipped with `payload_too_large`. |

**Experience notes path:** after judging, `live_judge.py` writes a structured Markdown note to `<SECOND_BRAIN_DIR>/_system/experiences/<agent_id>/<date>-<run_id>.md` and immediately reindexes the vault so the experience is searchable on the next agent run.

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
| `HERMES_TELEGRAM_WEBHOOK_URL` | Optional | — | Public HTTPS URL Telegram POSTs to for Hermes webhook delivery. Must be reachable from Telegram's servers. Hermes is being phased out — see [docs/CONNECTIONS-ROADMAP.md](./CONNECTIONS-ROADMAP.md) §2.4. |
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

| Tier name | Purpose |
|---|---|
| `orchestrator` | Heavy reasoning + supervisor team coordination (NIM DeepSeek V4 Pro → GLM-5.1 → cloud-sonnet) |
| `research-worker` | Multi-angle research workers (NIM DeepSeek V4 Flash → Llama 3.1 405B → cloud-sonnet) |
| `default-worker` | Standard agent runs (LM Studio Gemma → NIM Llama 3.3 70B → Mistral 2 Large → cloud-groq) |
| `cheap-worker` | Fast / low-cost local tier |
| `private-worker` | Local-only by contract (no cloud fallbacks) |
| `cloud-sonnet` | Cloud fallback (`claude-sonnet-4-6`) |
| `cloud-groq` | Cloud fallback (`llama-3.3-70b-versatile`) |

NVIDIA NIM is treated as cloud-allowed (equivalent privacy posture to Anthropic / Groq); `private-worker` stays strictly local. Cloud tiers activate automatically through the fallback chain when local endpoints are unreachable.

### Pre-call hook: `strip_response_format`

`deploy/litellm/strip_response_format.py` is registered as a LiteLLM custom callback. It strips `response_format` from requests that also pass `tools=` when routing to a local model that returns HTTP 400 on the combination (Groq, certain LM Studio configs). Keep this file mounted in `docker-compose.yml` and referenced in `config.yaml` — removing it will re-introduce the Phase 12 Groq 400s.

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

## Systemd service units

All units read `/opt/ultra-agents-brain/.env` via `EnvironmentFile=`. The services below are deployed to the VPS; timers trigger the oneshot services on schedule.

| Unit | Type | Schedule / trigger | Description |
|---|---|---|---|
| `uab-brain.service` | `simple` | Always-on (auto-restart) | AgentOS FastAPI server. Hardcodes `AGENTOS_HOST=127.0.0.1` and `AGENTOS_PORT=7000` at the service level (overrides `.env` value on the VPS). |
| `uab-telegram.service` | `simple` | Always-on (auto-restart) | Telegram adapter. Hardcodes `AGENTOS_BASE_URL=http://127.0.0.1:7000`. Requires `uab-brain.service`. |
| `uab-digest.service` + `.timer` | `oneshot` | Daily at 20:00 UTC | Triggers the curator agent's `digest` task via `POST /agents/curator/runs`. |
| `uab-monitor.service` + `.timer` | `oneshot` | Every 4 hours | Triggers the curator agent's `poll_feeds` task. |
| `uab-review.service` + `.timer` | `oneshot` | Sundays at 18:00 UTC | Triggers the curator agent's weekly `review` task. |
| `uab-live-judge.service` + `.timer` | `oneshot` | Every 2 minutes (after boot) | Runs `python -m agentos live-judge --once --limit 20`. Processes up to 20 pending performance eval rows per invocation. `ReadWritePaths` includes `/srv/second-brain` for experience note writes. Requires `EVAL_LIVE_JUDGE_ENABLED=true` in `.env` to do useful work. |

---

## Required vs Optional Settings

The following variables cause startup failure if absent:

| Variable | Component | Error |
|---|---|---|
| `LITELLM_MASTER_KEY` | `agentos/model.py` | `KeyError: 'LITELLM_MASTER_KEY'` — hard `os.environ["LITELLM_MASTER_KEY"]` lookup with no default |

All other variables have defaults or are purely optional integrations (Telegram, cloud keys, vault sync, eval system).

---

## Per-Environment Overrides

| Environment | Approach |
|---|---|
| **Local development (Mac)** | `LM_STUDIO_API_BASE=http://localhost:1234/v1`. Use `lm-studio` as `LM_STUDIO_API_KEY`. Cloud keys optional. `EVAL_LIVE_JUDGE_ENABLED=false` (default). |
| **VPS / production** | `LM_STUDIO_API_BASE` set to the LM Link endpoint from LM Studio. `SECOND_BRAIN_DIR=/srv/second-brain`. `EVAL_LIVE_JUDGE_ENABLED=true`, `EVAL_LIVE_SAMPLE_RATE=1.0` for full coverage with local judge. `POSTGRES_DSN_SESSIONS` set for session and eval run persistence. Systemd unit reads `.env` from `UAB_PROJECT_ROOT`. |
| **macOS port conflict** | `AGENTOS_PORT=7001` to avoid conflict with macOS ControlCenter which occupies port 7000. Note: the VPS systemd unit (`uab-brain.service`) hardcodes `AGENTOS_PORT=7000` at the unit level, which takes precedence over `.env` on Linux. |

There are no `.env.development` or `.env.production` files — all overrides are applied by editing the single `.env` file on each host.
