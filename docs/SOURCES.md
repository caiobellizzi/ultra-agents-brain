# SOURCES

Every data source connected to the second brain — what it does, where it's configured, and how data flows into and out of the vault. For day-to-day maintenance see [MAINTENANCE.md](./MAINTENANCE.md). For gaps and additions see [CONNECTIONS-ROADMAP.md](./CONNECTIONS-ROADMAP.md).

**Status legend:** ✅ active · 🟡 configured but partial · ⚪ planned · ⛔ explicitly skipped

---

## System map

```
                ┌─────────────────────────┐
   inputs ────► │      _inbox/            │ ──► brain.ingest ──► PARA folders
                └─────────────────────────┘                              │
   RSS  ──► worker.monitor ──┐                                           │
   Bluesky ──► bluesky ──────┤                                           ▼
   Telegram inbound ─────────┤                                  brain.lint (nightly)
   manual notes ─────────────┘                                  brain.review (weekly)
                                                                         │
   vault ◄─► Obsidian MCP                                                ▼
   vault ◄─► qmd (BM25 + vectors)                              brain.express ─► Telegram
   vault ◄─► PostgresDb (agno_knowledge / agno_sessions)
   vault ◄─► claude-mem (cross-session memory)

   LLM calls ──► LiteLLM proxy ──► Anthropic / Groq / OpenAI / NVIDIA NIM / LM Studio / OpenRouter / xAI

   eval feedback ──► live_judge ──────────────────────────────► vault/_system/experiences/
```

---

## Input sources (writers to the vault)

### RSS — `worker.monitor` ✅
- **Config:** `skills/worker.monitor/feeds.yaml` (canonical, 126 lines with metadata), `skills/worker.monitor/feeds.txt` (CLI default, one URL per line)
- **Includes:** vendor blogs (OpenAI, HuggingFace, DeepMind, Google AI), researcher blogs (Karpathy, Weng, Willison, Jack Clark), ArXiv categories (cs.LG, cs.AI, cs.CL), **Hacker News**, **GitHub** trending/release feeds — the approved source stack per decision 2026-05-22 is RSS + Bluesky + GitHub + HN, all delivered through this single pipeline
- **Cadence:** every 4 h on VPS cron
- **Lands in:** `vault/_inbox/`
- **Dedup:** `vault/_system/monitor-seen.json` (machine-local, excluded from rsync)
- **Code:** `ultra_brain/monitor.py`, `skills/worker.monitor/monitor.py`
- **Failure modes:** dead URLs silently skipped, malformed feeds logged to `_system/log.md`
- **Maintenance:** prune dead URLs monthly; both `feeds.yaml` and `feeds.txt` must stay in sync until the CLI is unified (see roadmap §2.1)

### Bluesky 🟡
- **Status:** working CLI, **not** in VPS cron
- **Config:** `skills/worker.monitor/bluesky-handles.txt` (14 handles)
- **Lands in:** `vault/_inbox/`
- **Dedup:** `vault/_system/bluesky-seen.json`
- **Code:** `ultra_brain/bluesky.py`
- **Maintenance:** add `bluesky` subcommand to `deploy/cron/ultra-agents-brain.cron` to activate (see roadmap)

### Telegram inbound ✅
- **Config:** `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_CHAT_IDS`, `TELEGRAM_WEBHOOK_SECRET` in `.env`
- **Service:** `ops/systemd/uab-telegram.service` (VPS) + `ops/systemd/uab-bot.service`
- **Code:** `channels/telegram_adapter.py`, `ultra_brain/telegram_bot.py`, `ultra_brain/telegram.py`
- **Lands in:** routed to the appropriate skill (capture → inbox, query → search, etc.)
- **Smoke:** `channels/SMOKE.md` documents the manual test flow

### Manual notes ✅
- **Surface:** Obsidian app on Mac, edits to `vault/**/*.md`
- **Propagates via:** `ops/sync-vault-to-vps.sh` LaunchAgent (5 min)

### X/Twitter ⛔ · LinkedIn ⛔
- **Decision:** S604 — out of scope. Re-evaluate if a clean public-post API becomes available.

---

## Knowledge backends (storage + retrieval)

### Obsidian MCP ✅
- **Endpoint:** `@bitbonsai/mcpvault` pointed at `~/Documents/second-brain`
- **Symlink:** `vault → ~/Documents/second-brain` (so CC projects + agentos see the same brain)
- **Used by:** Claude Code when reading/writing notes outside the Python CLI
- **Maintenance:** runs as part of the global Claude config; nothing project-side

### qmd ✅
- **Role:** local Markdown search (BM25 + vectors); also an MCP server
- **Collection:** `second-brain` (41 docs at last `qmd status`)
- **Used by:** `skills/brain.query/qmd_client.py`, `brain.query` CLI
- **Maintenance:** run `qmd update` after batch refines; `qmd embed` for missing vectors

### SqliteDb (Agno) — local/dev default ✅
- **Path:** `UAB_DB_PATH` (defaults to `~/Documents/uab-state/agno.db`)
- **Code:** `agentos/db.py` — always-on; used when `POSTGRES_DSN_SESSIONS` is unset, also used as `db=` for every Agent
- **Role:** session memory across agents, survives systemd restarts

### PostgresDb (Agno) — VPS production ✅
- **DSNs:** `POSTGRES_DSN_SESSIONS`, `POSTGRES_DSN_KNOWLEDGE` in `.env`
- **Activation:** `agentos/db.py` lazily creates `POSTGRES_DB = PostgresDb(id="ultra-brain-main", ...)` when `POSTGRES_DSN_SESSIONS` is set; silently falls back to `None` if `psycopg` is missing or DB unreachable
- **Service:** `ops/systemd/uab-postgres.service` (VPS)
- **Schemas:** `agno_sessions` (chat history), `agno_knowledge` (vectorized vault, pgvector)
- **Reindex:** `python -m agentos.knowledge --reindex`
- **Instrumentation:** `agentos/instrumented_memory.py`, `agentos/instrumented_knowledge.py` (Phase 11+ observability — wraps Agno's Memory/Knowledge with structured logging)

### claude-mem ✅
- **Role:** automatic cross-session memory for Claude Code
- **Configured globally** (`~/.claude-mem/`); no project-side config
- **Used for:** "did we already do X?" lookups, decision history

---

## LLM providers

### LiteLLM proxy ✅
- **Endpoint:** `http://127.0.0.1:4000/v1` (VPS), `LITELLM_BASE_URL` env var
- **Container:** `ghcr.io/berriai/litellm:main-stable` pinned in `.env`
- **Config:** `deploy/litellm/config.yaml`
- **Custom hook:** `deploy/litellm/strip_response_format.py` — strips `response_format` for local models when `tools` are also present (memory 21777, fixes Groq HTTP 400)
- **Tier aliases:** `cheap-worker`, `default-worker`, `orchestrator`, `research-worker`, `private-worker` (configurable via `LITELLM_*_MODEL` env vars)
- **Smoke:** `bash scripts/smoke-litellm.sh`

### Provider keys (consumed by LiteLLM)
| Provider | Env var | Status |
|----------|---------|--------|
| Anthropic | `ANTHROPIC_API_KEY` | ✅ (memory 21770: was unset on VPS — verify) |
| OpenAI | `OPENAI_API_KEY` | configured slot |
| Groq | `GROQ_API_KEY` | ✅ (memory 21770: was unset on VPS — verify) |
| OpenRouter | `OPENROUTER_API_KEY` | configured slot |
| NVIDIA NIM | `NVIDIA_NIM_API_KEY` | ✅ free tier (40 RPM/model) |
| xAI Grok | `XAI_API_KEY` | configured slot — needs console.x.ai credits before adding aliases |
| LM Studio | `LM_STUDIO_API_BASE` + `LM_STUDIO_API_KEY` | ✅ local fallback |

---

## External research

### NotebookLM 🟡
- **MCP:** `notebooklm-mcp-cli` installed (`~/.local/bin/notebooklm-mcp`)
- **Blocker:** needs `nlm login` (interactive Google auth) before the MCP can connect (inventory.md TODO)
- **Role when active:** tier-1 curated knowledge in the [knowledge hierarchy](../CLAUDE.md)

### Perplexity 🟡
- **Status:** no `PERPLEXITY_API_KEY` in `.env` (memory 21772)
- **MCP available:** `@perplexity-ai/mcp-server` registered globally
- **Role when active:** tier-4 fresh web search

### Context7 ✅
- **MCP:** library/framework docs lookup
- **Tier:** mandatory before any web search for library questions
- **Used by:** Claude Code globally; not invoked by Python CLI

### Crawl4AI ✅
- **MCP endpoint:** `CRAWL4AI_MCP_URL=http://127.0.0.1:11235/mcp` in `.env`
- **Use:** clean-Markdown extraction from JS-heavy pages; can be called by `worker.research`

---

## Output channels

### Telegram bot ✅
- **Adapter:** `channels/telegram_adapter.py`
- **Daily brief delivery:** `ultra_brain/telegram.py` (one-shot send) vs `ultra_brain/telegram_bot.py` (long-running listener)
- **Alerts:** `TELEGRAM_ALERT_CHAT_ID` receives health-check failures
- **Service:** `ops/systemd/uab-telegram.service`

### Hermes gateway 🟡
- **Env:** `HERMES_IMAGE`, `HERMES_HTTP_PORT=8787`, `HERMES_TELEGRAM_WEBHOOK_URL`
- **Status:** mostly eliminated from runtime path (memory 20353); env vars + image pin retained for compatibility; `scripts/health-check.sh` still probes `http://127.0.0.1:8787/health`
- **Decision needed:** finish removal or restore — currently in limbo

### TTS 🟡
- **Code:** `skills/brain.express/tts.py`
- **Status:** wired for daily brief audio; gated as medium-trust (cost). Not enabled by default.

### AgentOS HTTP API ✅
- **App:** `agentos/app.py`
- **Surfaces:** chat, query, research, ingest, curator, supervisor team (`id="supervisor"`) — all with explicit IDs (memory 21840–21846)
- **Web UI:** [os.agno.com](https://os.agno.com) (memory S598 — wiring incomplete)

---

## Observability

### Eval recorder ✅
- **Module:** `agentos/eval_recorder.py` — instruments `Agent.run` / `Agent.arun` / `Agent.continue_run` / `Agent.acontinue_run` and `Team` equivalents at **class level** via `patch_classes_for_recording(db)`. Class-level patching ensures Agno's `deep_copy()` path (used per HTTP request) inherits the instrumentation automatically.
- **What it writes:** one `EvalRunRecord` per non-streaming, non-background run, with `eval_type=PERFORMANCE` and `score=null` (score is filled later by the live judge). Rows land in `ai.agno_eval_runs`.
- **Skipped paths:** streaming (`stream=True`), background (`background=True`), and paused/HITL runs (`response.is_paused=True`) — these do not produce eval rows.
- **Privacy gate + sampling:** `agentos/eval_live_policy.py` (`EvalLivePolicy`) is consulted at record time. Controls whether a row is tagged `judge_status=pending` (eligible for judging), based on `EVAL_LIVE_JUDGE_ENABLED`, `EVAL_LIVE_SAMPLE_RATE`, per-agent `EVAL_LIVE_SAMPLE_RATE_{AGENT}` overrides, and a regex secret-marker check. Disabled by default (`enabled=False`).
- **Rubrics:** `agentos/eval_rubrics.py` — maps `agent_id` → rubric. Five rubrics defined:
  | Rubric ID | Agent | Strategy | Threshold |
  |-----------|-------|----------|-----------|
  | `chat-helpfulness-v1` | `chat` | binary | 1.0 |
  | `query-groundedness-v1` | `query` | numeric | 0.7 |
  | `ingest-fidelity-v1` | `ingest` | numeric | 0.7 |
  | `curator-quality-v1` | `curator` | numeric | 0.7 |
  | `research-grounding-v1` | `research` | numeric | 0.7 |
- **Pre-commit gate:** `tools/precommit_eval_router.sh`
- **EVAL-02 hook:** `tests/conftest.py` (memory 21861, 21862)

### Live judge ✅
- **Module:** `agentos/live_judge.py` — timer-fired worker that reads `pending` performance rows, runs an LLM judge (`AgentAsJudgeEval` via `private-worker` tier), and writes `agent_as_judge` child rows back to `ai.agno_eval_runs`.
- **Systemd unit:** `deploy/systemd/uab-live-judge.service` (oneshot) + `deploy/systemd/uab-live-judge.timer` (fires every 2 min, `OnUnitActiveSec=2min`)
- **CLI:** `python -m agentos live-judge --once --limit 20`
- **Flow per row:** fetch pending `PERFORMANCE` rows → privacy check → rubric lookup → `judge.evaluate()` → write child `AGENT_AS_JUDGE` row → update parent `judge_status=judged` → write experience note (see below)
- **Failure handling:** up to `EVAL_LIVE_MAX_ATTEMPTS` (default 3) retries; rows that exceed the limit are marked `failed_max_attempts`

### Experience notes ✅
- **Path:** `vault/_system/experiences/{agent_id}/` (resolved from `SECOND_BRAIN_DIR` env var, defaulting to `vault`)
- **Written by:** `live_judge._write_experience_note()` — called after each successful judgment (all rubrics for a run complete without error)
- **Filename:** `{YYYY-MM-DD}-{run_id}.md`
- **Format:** YAML frontmatter (`agent`, `run_id`, `score`, `rubric`, `status`, `date`, `tags`) followed by markdown sections: Input, Score, What worked/failed, Key pattern
- **Purpose:** agents with `enable_agentic_culture=True` can search these notes (via `agentos/knowledge`) before answering, creating a feedback loop from past judgments into future responses
- **Reindex:** `_write_experience_note` calls `agentos.knowledge.reindex()` immediately after writing so the note is searchable on the next agent run

### Cost ledger ✅
- **Per-vault:** `vault/_system/cost-ledger.md` appended by every paid LLM call via `ultra_brain/cost.py`
- **Per-skill:** `skills/common/cost_ledger.py`
- **Roll-up:** `python -m ultra_brain --vault vault cost-summary` or `bash scripts/cost-check.sh`
- **Cap:** `DAILY_COST_CAP_USD=20`

### Trust policy ✅
- **Module:** `skills/common/trust_policy.py`, `ultra_brain/trust.py`
- **Role:** graduated permissions — low/medium/high risk skills must declare cost + side effects
