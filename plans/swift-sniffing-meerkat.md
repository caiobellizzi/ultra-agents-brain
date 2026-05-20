> **Status: SUPERSEDED** — replaced by Phase 1 (ultra-brain-agno) which uses Agno instead of a native Telegram bot.

# Replace Hermes with a Native Python Telegram Bot

## Context

The original ultra-agents-brain plan called for `ghcr.io/nousresearch/hermes-agent:v2026.5.16` as the orchestration runtime — a "154k★ MIT NousResearch agent framework" that would handle Telegram I/O, intent classification, skill dispatch, cron operations, and trust gates. **This Docker image does not exist publicly.** NousResearch publishes LLM model weights (Hermes-3, Hermes-2-Pro), not an agent runtime. The plan document hallucinated this dependency.

The rest of the stack is fully working on VPS `srv847330.hstgr.cloud` (31.97.130.253):
- LiteLLM proxy on port 4000 (Docker, host network mode) — verified end-to-end inference works
- LM Link tunnel to Caio's MacBook with `google/gemma-4-e4b` loaded
- `ultra_brain` Python package synced to `/opt/ultra-agents-brain/` with all 12 modules implemented and tested (8/8 tests pass)
- Vault scaffold at `/srv/second-brain/` and at `~/Documents/second-brain` on the Mac
- Telegram bot `@ultra_agents_brain_bot` token in `.env`, chat ID `7113965359` allowed, test message delivered

**The need:** build a ~200 LOC Python Telegram bot on the VPS that performs every role Hermes was supposed to perform, using `python-telegram-bot` and the existing `ultra_brain` package. No new Docker images, no external runtime dependency, full control.

## Architecture

```
Telegram                         VPS (31.97.130.253)
   │                                 │
   │  long-polling (no HTTPS needed) │
   └─────────────────────────────────► uab-bot (systemd, Python)
                                        │
                                        ├── intents.py  (LLM-classify message → intent)
                                        ├── handlers.py (one function per intent)
                                        │      │
                                        │      ├── ingest_url      → ultra_brain.ingest
                                        │      ├── query_vault     → ultra_brain.query
                                        │      ├── research_topic  → ultra_brain.research
                                        │      ├── daily_digest    → ultra_brain.express
                                        │      ├── weekly_review   → ultra_brain.review
                                        │      ├── lint_vault      → ultra_brain.lint
                                        │      ├── telos_interview → ultra_brain.telos
                                        │      └── conversational  → llm.complete (chitchat)
                                        │
                                        ├── sessions.py   (SQLite: pending approvals + TELOS session)
                                        ├── sender.py     (outbound message helper)
                                        └── llm calls     → http://127.0.0.1:4000/v1 (LiteLLM)

systemd timers:
  uab-digest.timer    — daily 20:00 → ultra_brain digest
  uab-review.timer    — Sunday 18:00 → ultra_brain review
  uab-monitor.timer   — every 4h     → ultra_brain monitor
```

## Files to create

**New `bot/` package on Mac (synced to VPS):**

| File | LOC | Purpose |
|------|-----|---------|
| `bot/__init__.py` | 3 | Package marker + version |
| `bot/__main__.py` | ~50 | Entry: load env, start polling, register handlers |
| `bot/intents.py` | ~40 | `classify(message: str) -> Intent` — LLM via LiteLLM `cheap-worker` |
| `bot/handlers.py` | ~80 | One `async def` per intent, dispatches to `ultra_brain.*` |
| `bot/sessions.py` | ~40 | SQLite store for pending approvals (action + cost + TTL) |
| `bot/sender.py` | ~20 | `send(chat_id, text)` + `send_with_buttons(...)` |
| `requirements.txt` | 2 lines | `python-telegram-bot>=21.0` |

**New systemd units in `deploy/systemd/`:**

| File | Purpose |
|------|---------|
| `uab-bot.service` | Long-running bot process, auto-restart, env from `/opt/ultra-agents-brain/.env` |
| `uab-digest.service` + `uab-digest.timer` | Daily 20:00 — calls `python3 -m ultra_brain --vault /srv/second-brain digest`, pipes to Telegram via `curl` |
| `uab-review.service` + `uab-review.timer` | Sunday 18:00 — calls `... review`, pipes to Telegram |
| `uab-monitor.service` + `uab-monitor.timer` | Every 4h — calls `... monitor`, logs only |

## Code that already exists (reuse, don't rebuild)

| Need | Existing function | File |
|------|-------------------|------|
| URL ingestion | `Filer(vault).file(extraction)` | `ultra_brain/ingest.py` |
| Vault Q&A | `query_vault(question, vault, llm_model=...)` | `ultra_brain/query.py` |
| Daily digest | `daily_digest(vault, llm_model=...)` | `ultra_brain/express.py` |
| Research planning | `plan_research(topic)` + `worker_summary(...)` | `ultra_brain/research.py` |
| RSS poll | `run_poll(feeds, vault)` | `ultra_brain/monitor.py` |
| TELOS interview state | `TelosSessionStore.start()` / `.answer()` | `ultra_brain/telos.py` |
| Risk classification | `classify_action(description) -> TrustDecision` | `ultra_brain/trust.py` |
| Approval prompt text | `approval_prompt(action, decision, cost)` | `ultra_brain/trust.py` |
| Cost cap enforcement | `CostLedger.gate(amount, limit_key)` | `ultra_brain/cost.py` |
| LLM call | `llm.complete(prompt, *, model, system)` | `ultra_brain/llm.py` |

## Intent classifier (the one new LLM call)

`bot/intents.py` sends each incoming message to `cheap-worker` (~zero-cost via LM Studio) with this system prompt (cached):

```
You are an intent classifier for a personal second-brain agent.
Output ONE of these intent labels and nothing else:
  ingest_url | query | research | digest | review | lint
  telos_interview | conversational | help

Rules:
  - Message contains a URL → ingest_url
  - "what do you know about X" / "find my notes on X" → query
  - "research X" / "look into X" → research
  - Anything else conversational → conversational
```

Response is a single token, parsed to enum.

## Approval flow (medium-risk actions)

1. Handler calls `trust.classify_action(description)` before executing.
2. If `decision.needs_approval`:
   - Generate unique `pending_id`
   - Store `(pending_id, chat_id, action_callable, cost_estimate, created_at)` in `bot/sessions.py` SQLite
   - Send Telegram message with inline buttons: `[✅ Approve] [❌ Deny]` (callback_data=`approve:<pending_id>`)
   - Bot's `CallbackQueryHandler` reads the click, looks up the pending action, executes or discards
3. If no approval needed: execute immediately.

## Deployment steps

1. **Local (Mac):** create `bot/` package + `requirements.txt` + `deploy/systemd/*` files.
2. **Sync:** rsync to VPS at `/opt/ultra-agents-brain/`.
3. **VPS:** `pip install -r requirements.txt --break-system-packages` (or use `uv venv`).
4. **VPS:** copy `deploy/systemd/*.service` and `*.timer` to `/etc/systemd/system/`, run `systemctl daemon-reload`.
5. **VPS:** `systemctl enable --now uab-bot uab-digest.timer uab-review.timer uab-monitor.timer`.
6. **Verify:** send "/start" to `@ultra_agents_brain_bot`, then "ingest https://example.com" → should file to vault Inbox + reply with path.

## Verification

| Test | Expected |
|------|----------|
| Send "hi" to bot | Conversational reply via gemma-4-e4b |
| Send "ingest https://anthropic.com" | Note filed to `/srv/second-brain/Inbox/...`, reply with path |
| Send "what do I know about claude" | Evidence-cited answer from vault |
| Send "research observability" | Reply "plan: 5 angles, ~$0 budget" then async fan-out (Phase 2) |
| `systemctl status uab-bot` | `active (running)` |
| `journalctl -u uab-digest --since today` | Empty until 20:00, then digest output |
| Wait until 20:00 | Telegram receives digest message |
| Approval flow: send "ingest <private URL>" | Bot replies with approve/deny buttons |

## Out of scope for this plan (phase 2+)

- Webhook mode (long-polling sufficient for personal use; switch later if traffic grows)
- Inline voice / TTS (placeholder exists in `express.py`)
- Multi-chat support (only Caio's chat_id whitelisted for now)
- The Telegram webhook URL in `.env` (`HERMES_TELEGRAM_WEBHOOK_URL`) is now unused — keep for future webhook switch
- Coolify integration (we explicitly avoid this)

## Risk flags

- **`python-telegram-bot` v21+ requires Python ≥3.9** — VPS has Python 3.12.3, OK.
- **Bot crash = no Telegram replies until systemd restarts it.** Mitigation: `Restart=on-failure` + `RestartSec=10` in service file; health-check.sh already pings Telegram via cron.
- **Long-polling holds a connection open** — fine on Hostinger, no LB timeout issues expected.
- **Bot token leaked in earlier chat turn.** Recommend rotating via BotFather `/revoke` after Phase 5 ends — straightforward token swap in `.env`, no code change needed.
