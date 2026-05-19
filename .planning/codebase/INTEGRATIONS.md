# External Integrations

**Analysis Date:** 2026-05-19

## LLM / Model Gateway

**LiteLLM Proxy (self-hosted):**
- Purpose: OpenAI-compatible proxy that exposes model-tier aliases to all skills and the Hermes agent
- Image: `ghcr.io/berriai/litellm:main-latest` (env: `LITELLM_IMAGE`)
- Endpoint: `http://127.0.0.1:4000/v1` (env: `LITELLM_BASE_URL`)
- Auth: Bearer token via `LITELLM_MASTER_KEY`
- Config: `deploy/litellm/config.yaml`
- Client in Python: `ultra_brain/llm.py` — pure `urllib.request`, no SDK

**Model Tiers defined in `deploy/litellm/config.yaml`:**

| Alias | Backend | Tier |
|-------|---------|------|
| `orchestrator` | LM Studio primary model | A — heavy |
| `default-worker` | LM Studio primary model | B — balanced |
| `cheap-worker` | LM Studio fast model | C — cost-optimized |
| `private-worker` | LM Studio primary model | D — on-prem/private |
| `cloud-sonnet` | Anthropic Claude | B-cloud fallback |
| `cloud-groq` | Groq Llama 3.3 70B | C-cloud fallback |

**Fallback chain:** `orchestrator → cloud-sonnet`, `default-worker → cloud-sonnet → cloud-groq`, `cheap-worker → default-worker → cloud-groq`

## Local LLM Backend

**LM Studio (OpenAI-compatible, local):**
- Purpose: Primary inference backend; LiteLLM routes to it via OpenAI-compatible API
- Local dev endpoint: `http://localhost:1234/v1` (env: `LM_STUDIO_API_BASE`)
- VPS access: via LM Link (remote endpoint set in `LM_STUDIO_API_BASE`)
- Auth: `LM_STUDIO_API_KEY` (default: `lm-studio`, unauthenticated)
- Model IDs: `LM_STUDIO_MODEL` (primary), `LM_STUDIO_FAST_MODEL` (fast tier)
- No SDK; LiteLLM proxy handles all routing

## Cloud LLM APIs (fallback only)

**Anthropic:**
- Model: `claude-sonnet-4-6`
- Auth: `ANTHROPIC_API_KEY`
- Used only when LM Studio is unreachable (LiteLLM fallback)
- No direct Anthropic SDK in Python package; routed through LiteLLM

**Groq:**
- Model: `llama-3.3-70b-versatile`
- Auth: `GROQ_API_KEY`
- Used as Tier C cloud fallback
- Routed through LiteLLM

**OpenAI / OpenRouter:**
- Auth: `OPENAI_API_KEY`, `OPENROUTER_API_KEY`
- Defined in `.env.example` but no model aliases configured in `deploy/litellm/config.yaml`
- Available for future config additions

## Agent Runtime

**Hermes Agent:**
- Purpose: Conversational agent runtime that loads skills, handles Telegram webhook, manages session and memory state
- Image: `ghcr.io/nousresearch/hermes-agent:v2026.5.16` (pinned, env: `HERMES_IMAGE`)
- HTTP port: `127.0.0.1:8787` (env: `HERMES_HTTP_PORT`)
- Config: `deploy/hermes/config.yaml`
- Connects to LiteLLM proxy via `http://litellm:4000/v1` (Docker internal network)
- Loaded skills: `brain.ingest`, `brain.query`, `brain.lint`, `brain.express`, `brain.review`, `telos.interview`, `telos.check`, `worker.research`, `worker.monitor`

## Messaging / User Interface

**Telegram Bot API:**
- Purpose: Primary user interface — all user interaction with the agent goes through Telegram
- Mode: Webhook (not polling)
- Webhook URL: `HERMES_TELEGRAM_WEBHOOK_URL` (public HTTPS URL pointing at Hermes)
- Webhook path: `/telegram/webhook`
- Auth: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`
- ACL: `TELEGRAM_ALLOWED_CHAT_IDS` (allowlist)
- Alert channel: `TELEGRAM_ALERT_CHAT_ID` (health check and cost alerts)
- Direct API calls from shell scripts (`scripts/health-check.sh`, `scripts/cost-check.sh`) via `curl https://api.telegram.org/bot.../sendMessage`
- Trust model: medium-risk actions require `/approve` or `/deny` reply in Telegram

## Web Content Extraction

**Crawl4AI (optional, local Docker):**
- Purpose: Clean Markdown extraction from URLs (JS-rendered, anti-bot pages)
- Endpoint: `http://127.0.0.1:11235/mcp` (env: `CRAWL4AI_MCP_URL`)
- Used by: `ultra_brain/ingest.py` (`Extractor._extract_crawl4ai`) and Hermes `mcp.crawl4ai` config
- Auth: None (local only)
- Fallback: Jina Reader if Crawl4AI unavailable

**Jina Reader (`r.jina.ai`):**
- Purpose: Fallback web-to-Markdown extraction when Crawl4AI is absent or fails
- Endpoint: `https://r.jina.ai/<url>` (public service, no auth)
- Used by: `ultra_brain/ingest.py` (`Extractor._extract_jina`)
- Client: `urllib.request`, no SDK

## Data Storage

**Vault (Markdown filesystem):**
- Type: Plain Markdown files in a git-tracked directory
- Location on VPS: `/srv/second-brain` (env: `SECOND_BRAIN_DIR`)
- Structure: PARA (Projects / Areas / Resources / Archives / Inbox) + `_system/`
- No database; all notes, logs, cost ledger, and TELOS data are Markdown/JSON flat files

**SQLite (Hermes internal):**
- Purpose: Hermes agent session and memory state
- Session store: `/var/lib/hermes/sessions.sqlite`
- Memory store: `/var/lib/hermes/memory.sqlite`
- Managed entirely by the Hermes container; not accessed by `ultra_brain` Python code

**JSON flat files (Python package):**
- Dedup store: `vault/_system/monitor-seen.json` — RSS dedup hash set
- TELOS sessions: `vault/_system/telos-sessions.json` — interview Q&A

**Markdown flat files (Python package):**
- Cost ledger: `vault/_system/cost-ledger.md` — pipe-delimited cost rows
- Operations log: `vault/_system/log.md` — append-only structured log
- Lint report: `vault/_system/lint-report.md`

## Version Control / Vault Sync

**Git:**
- The vault at `/srv/second-brain` is a git repository
- Sync script: `scripts/git-sync.sh` — pull (fast-forward only) and push operations
- Remote: `VAULT_REMOTE_URL` (env; e.g. private GitHub repo)
- Branch: `VAULT_DEFAULT_BRANCH` (default: `main`)
- Health check verifies vault is clean (no uncommitted changes) via `git status --porcelain`

## Networking

**Tailscale:**
- Purpose: Secure private network between developer Mac and VPS, enabling LM Studio access via LM Link
- Installed by `scripts/vps-bootstrap.sh`
- Required for routing `LM_STUDIO_API_BASE` to a local Mac running LM Studio

**UFW (firewall):**
- Allows: SSH, 80/tcp, 443/tcp
- LiteLLM (4000) and Hermes (8787) bound to `127.0.0.1` only — not exposed publicly

## CI/CD & Deployment

**Hosting:**
- VPS running Debian/Ubuntu (bootstrapped via `scripts/vps-bootstrap.sh`)
- No cloud provider specified; any apt-compatible Linux host

**Process management:**
- systemd unit: `deploy/systemd/ultra-agents-brain.service` — starts/stops Docker Compose stack
- Cron: `deploy/cron/ultra-agents-brain.cron` — scheduled Python and shell jobs

**CI Pipeline:**
- Not detected — no GitHub Actions, CircleCI, or similar config present

## Environment Configuration Summary

**Required env vars (from `.env.example`):**

| Variable | Purpose |
|----------|---------|
| `LITELLM_MASTER_KEY` | LiteLLM API auth |
| `LM_STUDIO_API_BASE` | LM Studio inference endpoint |
| `LM_STUDIO_API_KEY` | LM Studio auth (default: `lm-studio`) |
| `LM_STUDIO_MODEL` | Primary model ID in LM Studio |
| `LM_STUDIO_FAST_MODEL` | Fast model ID in LM Studio |
| `TELEGRAM_BOT_TOKEN` | Telegram bot auth |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Allowlisted user chat IDs |
| `TELEGRAM_ALERT_CHAT_ID` | Chat ID for health/cost alerts |
| `TELEGRAM_WEBHOOK_SECRET` | Webhook signature verification |
| `HERMES_TELEGRAM_WEBHOOK_URL` | Public HTTPS URL for Telegram webhook |
| `SECOND_BRAIN_DIR` | Vault filesystem path |
| `DAILY_COST_CAP_USD` | Hard daily spend cap (default: 20) |
| `VAULT_REMOTE_URL` | Git remote for vault sync |

**Optional env vars:**

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Cloud fallback (claude-sonnet-4-6) |
| `GROQ_API_KEY` | Cloud fallback (llama-3.3-70b) |
| `OPENAI_API_KEY` | Reserved, no model config yet |
| `OPENROUTER_API_KEY` | Reserved, no model config yet |
| `CRAWL4AI_MCP_URL` | Crawl4AI local endpoint |
| `CRAWL4AI_ENDPOINT` | Crawl4AI endpoint for ingest.py |
| `ALLOW_DIRTY_VAULT` | Skip clean-vault health check |
| `HEALTH_NOTIFY_ON_SUCCESS` | Telegram alert on clean health |

**Secrets location:** `.env` file at `$UAB_PROJECT_ROOT/.env` on VPS only. Never committed to git.

## Webhooks & Callbacks

**Incoming:**
- `POST /telegram/webhook` — Telegram sends user messages to Hermes (port 8787, protected by `TELEGRAM_WEBHOOK_SECRET`)

**Outgoing:**
- `https://api.telegram.org/bot.../sendMessage` — health alerts, cost alerts, approval prompts sent from `scripts/health-check.sh` and `scripts/cost-check.sh`

---

*Integration audit: 2026-05-19*
