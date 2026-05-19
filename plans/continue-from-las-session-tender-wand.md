# Build `ultra-brain` on Agno — Knowledge Layer First, Workshop Deferred

## Context

The original `swift-sniffing-meerkat.md` plan called for ~200 LOC of native Python (`python-telegram-bot` + the existing `ultra_brain` package). During grilling we surfaced that the 200-LOC plan silently descoped the things you actually care about — long-term memory, context engineering, HITL approval flows, observability — and would balloon to ~800 LOC within weeks. Research confirmed **Agno** (Apache-2.0, 39k★, Python, OpenAI-compatible) gives all of those as first-class primitives and points natively at the LiteLLM proxy you already run on `:4000`.

We then surfaced a bigger pivot: this project isn't one bot, it's a **two-tier architecture**:

- **Tier 1 — `ultra-brain` (Knowledge Layer):** always-on, autonomously ingests/curates a vault, serves RAG context to both humans (chat) and other agents (HTTP API). This file is its build plan.
- **Tier 2 — `ultra-workshop` (Execution Layer):** on-demand orchestrator that spawns specialist agents (research → architect → coder → reviewer → tester → PR → deploy) for "build me X" goals. Will use Agno orchestration + OpenHands as a sandboxed-coding tool. **Deferred** until tier 1 is shipped and used daily for 2-4 weeks.

You picked **Brain-first**. This plan covers that and only that. `ultra-workshop` becomes a separate repo/project; we'll plan it in a future session once the Brain is real and you've discovered what it actually needs to serve.

## Why Brain-first (locked in)

- Workshop agents need a populated vault to query; building Workshop first means it reads an empty vault and ships shallow output for weeks.
- Brain is smaller scope (~3-5 days of focused build) vs Workshop (~weeks).
- Brain is the foundation; Workshop is the application. Foundation first.
- Building Brain reveals real query patterns that should shape Workshop's design — not the other way around.

## Architecture: `ultra-brain` on Agno

```
                  ┌──────────────────────────────────────────┐
                  │  /srv/second-brain  (existing vault)     │
                  │  - Markdown notes                        │
                  │  - PRDs, ADRs, research summaries        │
                  └────────────────────┬─────────────────────┘
                                       │ read/write via ultra_brain.* tools
                  ┌────────────────────▼─────────────────────┐
                  │  AgentOS (FastAPI, Agno)                 │
                  │  127.0.0.1:7000  systemd: uab-brain      │
                  │                                          │
                  │  Agents:                                 │
                  │   - chat_agent     (conversational)      │
                  │   - ingest_agent   (URL → vault)         │
                  │   - query_agent    (RAG over vault)      │
                  │   - research_agent (multi-angle dive)    │
                  │   - curator_agent  (autonomous, cron)    │
                  │                                          │
                  │  Tools (wrap existing ultra_brain code): │
                  │   Filer.file, query_vault, plan_research │
                  │   daily_digest, run_poll, classify_action│
                  │   CostLedger.gate, llm.complete          │
                  │                                          │
                  │  Memory: SqliteDb at /var/lib/uab/db     │
                  │  HITL:   Agno approval gates             │
                  └────────────────────┬─────────────────────┘
                                       │ HTTP POST /v1/agents/chat
                  ┌────────────────────▼─────────────────────┐
                  │  channels/telegram_adapter.py            │
                  │  systemd: uab-telegram                   │
                  │  long-poll → POST AgentOS → reply        │
                  └──────────────────────────────────────────┘

systemd timers (call AgentOS via curl, not Python directly):
  uab-digest.timer    20:00 daily   → POST /v1/agents/curator {task:"digest"}
  uab-review.timer    Sun 18:00     → POST /v1/agents/curator {task:"review"}
  uab-monitor.timer   every 4h      → POST /v1/agents/curator {task:"poll_feeds"}
```

**Why this shape:**
- AgentOS is the single source of truth for agent behavior; channels are dumb adapters.
- Channels are pluggable — adding Discord/WhatsApp later means a new `channels/*_adapter.py`, no agent code change.
- Cron timers hit HTTP, not Python — so curator behavior is shared with whatever invokes it (chat, cron, or workshop later).
- HITL gates live in Agno, not in the adapter — approval state survives bot restarts.

## Migration strategy: WRAP, don't rewrite

The existing `ultra_brain/*.py` modules stay as-is. Each becomes a **tool** registered on the appropriate Agno agent:

| Existing function | File | Becomes tool on |
|---|---|---|
| `Filer.file(extraction)` | `ultra_brain/ingest.py` | `ingest_agent` |
| `query_vault(question, vault, ...)` | `ultra_brain/query.py` | `query_agent`, `chat_agent` |
| `plan_research(topic)`, `worker_summary(...)` | `ultra_brain/research.py` | `research_agent` |
| `daily_digest(vault, ...)` | `ultra_brain/express.py` | `curator_agent` |
| `weekly_review(...)` | `ultra_brain/review.py` | `curator_agent` |
| `lint_vault(...)` | `ultra_brain/lint.py` | `curator_agent` |
| `run_poll(feeds, vault)` | `ultra_brain/monitor.py` | `curator_agent` |
| `TelosSessionStore.start/.answer` | `ultra_brain/telos.py` | `chat_agent` (telos sub-mode) |
| `classify_action(description)` | `ultra_brain/trust.py` | called before every write-tool execution |
| `approval_prompt(action, decision, cost)` | `ultra_brain/trust.py` | fed into Agno HITL gate |
| `CostLedger.gate(amount, key)` | `ultra_brain/cost.py` | wrapped around every LLM call |
| `llm.complete(prompt, ...)` | `ultra_brain/llm.py` | replaced by Agno's `OpenAIProvider(base_url=...)` |

**What gets replaced (not wrapped):**
- `ultra_brain/llm.py` — Agno's model providers handle this. Delete after migration.
- Custom session/state code (none merged yet, but the `bot/sessions.py` from swift-sniffing-meerkat is dropped — Agno's `SqliteDb` handles it).
- Any direct intent-classification logic — Agno agents handle routing internally.

## Files to create

### New `agentos/` package on Mac (synced to VPS):

| File | LOC | Purpose |
|---|---|---|
| `agentos/__init__.py` | 3 | Package marker |
| `agentos/app.py` | ~80 | Build AgentOS FastAPI app, register all agents |
| `agentos/agents/chat.py` | ~40 | `chat_agent` — conversational, has `query_vault` tool |
| `agentos/agents/ingest.py` | ~40 | `ingest_agent` — wraps `Filer.file()`, gated by `classify_action` |
| `agentos/agents/query.py` | ~30 | `query_agent` — pure RAG over vault |
| `agentos/agents/research.py` | ~50 | `research_agent` — multi-call fan-out, uses `plan_research`+`worker_summary` |
| `agentos/agents/curator.py` | ~50 | `curator_agent` — runs digest/review/monitor on POST |
| `agentos/tools/__init__.py` | 2 | |
| `agentos/tools/vault.py` | ~80 | `@tool`-decorated wrappers around existing `ultra_brain.*` functions |
| `agentos/tools/trust_gate.py` | ~30 | Decorator that wraps any tool with `classify_action` + Agno HITL |
| `agentos/knowledge.py` | ~30 | `MarkdownKnowledgeBase` pointing at `/srv/second-brain` |
| `agentos/__main__.py` | ~20 | `uvicorn agentos.app:app --host 127.0.0.1 --port 7000` |
| `requirements.txt` | ~5 lines | `agno`, `uvicorn`, `fastapi`, `python-telegram-bot`, `markdown` |

### Channels:

| File | LOC | Purpose |
|---|---|---|
| `channels/telegram_adapter.py` | ~120 | Long-poll Telegram → POST to AgentOS → reply. Handles inline approval buttons by calling Agno HITL resume endpoint. |
| `channels/__init__.py` | 2 | |

### Systemd:

| File | Purpose |
|---|---|
| `deploy/systemd/uab-brain.service` | AgentOS uvicorn process, `Restart=on-failure`, env from `/opt/ultra-agents-brain/.env` |
| `deploy/systemd/uab-telegram.service` | Telegram adapter, depends on `uab-brain.service` |
| `deploy/systemd/uab-digest.service` + `.timer` | Daily 20:00, `ExecStart=/usr/bin/curl -X POST http://127.0.0.1:7000/v1/agents/curator -d '{"task":"digest"}'` (or equivalent — exact path depends on Agno's AgentOS routing, verify during build) |
| `deploy/systemd/uab-review.service` + `.timer` | Sunday 18:00, `task:"review"` |
| `deploy/systemd/uab-monitor.service` + `.timer` | Every 4h, `task:"poll_feeds"` |

### Cleanup:

| Path | Action | Why |
|---|---|---|
| `deploy/hermes/` | **Delete** | Hermes image doesn't exist; config is dead weight |
| `deploy/systemd/ultra-agents-brain.service` (existing) | Delete | Replaced by `uab-brain.service` |
| `ultra_brain/llm.py` | Delete **after** Agno migration verified | Replaced by Agno provider |
| `plans/swift-sniffing-meerkat.md` | Keep, mark as **superseded** at top | History of the design pivot |

## Execution checklist

### Phase 1 — Read Agno docs (Mac, ~2 hours)

1. Read Agno's "Getting Started", "Agents", "Tools", "Knowledge", "Memory", "HITL", "AgentOS" sections. Reference: https://docs.agno.com/
2. Skim one end-to-end example that pairs AgentOS + a custom tool + a `MarkdownKnowledgeBase`.
3. Confirm `OpenAIProvider(base_url="http://127.0.0.1:4000/v1", model="cheap-worker")` works against LiteLLM (write a 10-line smoke script before touching anything else).

### Phase 2 — Local scaffolding (Mac, ~1 day)

4. `python3 -m venv .venv && source .venv/bin/activate`
5. Create `requirements.txt`, `pip install -r requirements.txt`
6. Build `agentos/knowledge.py` pointing at `~/Documents/second-brain`
7. Build `agentos/tools/vault.py` wrapping existing `ultra_brain.*` functions
8. Build `agentos/tools/trust_gate.py` decorator
9. Build `agentos/agents/*.py` — one at a time, smoke-test each in a REPL before moving on
10. Build `agentos/app.py` + `agentos/__main__.py`
11. `python -m agentos` → curl `127.0.0.1:7000/v1/agents/chat` with a test prompt

### Phase 3 — Telegram adapter (Mac, ~half day)

12. Build `channels/telegram_adapter.py` — long-poll, POST to AgentOS, handle inline button callbacks
13. Smoke test: `python -m channels.telegram_adapter` on Mac, send "hi" to `@ultra_agents_brain_bot`, expect reply
14. Test approval flow: "ingest https://anthropic.com" → buttons → approve → note in vault

### Phase 4 — VPS deployment (~half day)

15. `rsync -av --exclude '.venv' --exclude '__pycache__' /Users/caiobellizzi/Documents/Projects/ultra-agents-brain/ root@31.97.130.253:/opt/ultra-agents-brain/`
16. SSH: `pip install -r requirements.txt --break-system-packages` (or `uv venv` if preferred)
17. SSH: `mkdir -p /var/lib/uab && chown root:root /var/lib/uab`
18. SSH: `cp deploy/systemd/uab-*.service deploy/systemd/uab-*.timer /etc/systemd/system/ && systemctl daemon-reload`
19. SSH: `systemctl enable --now uab-brain uab-telegram uab-digest.timer uab-review.timer uab-monitor.timer`
20. SSH: `rm -rf /opt/ultra-agents-brain/deploy/hermes`
21. SSH: `systemctl disable --now ultra-agents-brain.service 2>/dev/null; rm /etc/systemd/system/ultra-agents-brain.service`

### Phase 5 — End-to-end verification

22. `systemctl status uab-brain uab-telegram` → both `active (running)`
23. Telegram: send "/start" → help text
24. Telegram: send "hi" → conversational reply via gemma-4-e4b
25. Telegram: send "ingest https://anthropic.com" → approval buttons → ✅ → note at `/srv/second-brain/Inbox/...`, reply with path
26. Telegram: send "what do I know about claude" → evidence-cited answer from vault
27. Telegram: send "research observability" → plan returned, worker fan-out runs async, summary posted
28. `systemctl list-timers | grep uab` → all three timers scheduled
29. Wait until 20:00 → Telegram receives digest message
30. `journalctl -u uab-brain --since "1h ago"` → no errors, OTel traces visible

## Verification matrix

| Test | Expected |
|---|---|
| `curl 127.0.0.1:7000/health` (or Agno's equiv) | 200 |
| `curl 127.0.0.1:7000/v1/agents/chat -d '{"message":"hi"}'` | conversational reply |
| Telegram from allowed chat | works |
| Telegram from non-allowed chat | silently ignored |
| `systemctl restart uab-brain` mid-conversation | session memory persists (SqliteDb survives restart) |
| Approval pending when bot restarts | resumes on click after restart (Agno HITL persistence) |
| Cost ledger exceeded | tool call refuses with reason, sent to chat |

## Out of scope (deferred)

- **`ultra-workshop` project** (the code-writing/PR/deploy agent team) — separate repo, future session. Won't be touched here.
- Discord / WhatsApp adapters — `channels/` pattern is in place but only Telegram is implemented now.
- Public HTTPS for AgentOS — stays on `127.0.0.1`. Workshop will reach it locally via `host.docker.internal` later.
- Webhook mode for Telegram — long-poll is fine.
- Migration off LM Studio / LM Link — kept.

## Risk flags

- **Agno API surface is evolving.** Pin `agno==<latest>` in `requirements.txt` and don't auto-upgrade. The `openai:` prefix → `OpenAIResponses` change has bitten users; verify against current docs during Phase 1.
- **AgentOS endpoint paths** in the cron services are illustrative — confirm exact routes during build and update the systemd `ExecStart` lines.
- **Bot token still exposed from earlier chat turn.** Rotate via BotFather `/revoke` after Phase 5 passes; update `.env`. No code change needed.
- **VPS Python 3.12.3** satisfies Agno's requirement (≥3.10). OK.
- **`/srv/second-brain` is currently empty** (or near-empty). Curator agent will have little to digest for the first few days. Expected; not a bug.
- **Two systemd services with one rsync.** A bad deploy can break both at once. Mitigation: `systemctl restart uab-brain && sleep 5 && curl 127.0.0.1:7000/health` before restarting `uab-telegram`.

## What `ultra-workshop` will look like (preview only — DO NOT BUILD HERE)

When Brain is shipped and used for 2-4 weeks, the Workshop plan will roughly be:

- New repo `ultra-workshop` (separate from `ultra-agents-brain`)
- Agno orchestrator agent decomposes goals into specialist tasks
- Specialist agents: `researcher`, `architect`, `coder`, `reviewer`, `tester`, `deployer`
- `coder` agent delegates to **OpenHands** running in a Docker sandbox (one container per task)
- Reads context from Brain via HTTP (`POST http://brain:7000/v1/agents/query`)
- Writes back ADRs / lessons learned via `POST http://brain:7000/v1/agents/ingest`
- Same Telegram bot, different intent prefix (`/build <goal>`, `/fix <issue-url>`)
- HITL approval gates at every task boundary

This preview is documented so future-you doesn't redesign it from scratch. Don't act on it yet.
