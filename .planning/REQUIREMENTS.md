# Requirements — ultra-agents-brain

**Milestone:** v1.0
**Source:** PROJECT.md + plans/continue-from-las-session-tender-wand.md

## v1.0 Requirements

### Functional

| REQ-ID | Requirement | Phase |
|--------|-------------|-------|
| REQ-001 | AgentOS exposes `POST /v1/agents/chat` for conversational requests | 1 |
| REQ-002 | AgentOS exposes `POST /v1/agents/ingest` that writes a URL → vault note (via `Filer.file`) | 1 |
| REQ-003 | AgentOS exposes `POST /v1/agents/query` returning evidence-cited answers from vault | 1 |
| REQ-004 | AgentOS exposes `POST /v1/agents/research` returning multi-angle research summary | 1 |
| REQ-005 | AgentOS exposes `POST /v1/agents/curator` accepting `task: "digest" \| "review" \| "poll_feeds"` | 1 |
| REQ-006 | Telegram adapter long-polls and routes incoming messages to `/v1/agents/chat` | 1 |
| REQ-007 | Telegram adapter renders inline approval buttons for any tool gated by Agno HITL | 1 |
| REQ-008 | Telegram adapter ignores messages from non-allowed chat IDs | 1 |
| REQ-009 | All write-tools (ingest, curator) are wrapped by `trust_gate` calling `classify_action` | 1 |
| REQ-010 | All LLM calls go through `OpenAIProvider(base_url="http://127.0.0.1:4000/v1")` (LiteLLM) | 1 |
| REQ-011 | Cost ledger entries written to `_system/cost-ledger.md` for every LLM call | 1 |
| REQ-012 | systemd timers fire `digest` (20:00 daily), `review` (Sun 18:00), `poll_feeds` (every 4h) | 1 |
| REQ-013 | Agno `SqliteDb` at `/var/lib/uab/` persists session memory and pending HITL approvals | 1 |

### Non-functional

| REQ-ID | Requirement | Phase |
|--------|-------------|-------|
| REQ-100 | AgentOS responds to `/health` within 200 ms when idle | 1 |
| REQ-101 | Session memory survives `systemctl restart uab-brain` | 1 |
| REQ-102 | Pending HITL approvals resume cleanly after restart | 1 |
| REQ-103 | `agno` version is pinned exactly in `requirements.txt` (no `>=`) | 1 |
| REQ-104 | AgentOS binds to `127.0.0.1:7000` only (no public network exposure) | 1 |
| REQ-105 | `uab-telegram.service` declares `After=uab-brain.service` dependency | 1 |
| REQ-106 | Cost-gate refusals are returned to the user with a clear reason | 1 |

### Operational

| REQ-ID | Requirement | Phase |
|--------|-------------|-------|
| REQ-200 | Old `deploy/hermes/` directory deleted from VPS | 1 |
| REQ-201 | Old `ultra-agents-brain.service` disabled and removed from VPS | 1 |
| REQ-202 | `ultra_brain/llm.py` deleted after Agno migration verified end-to-end | 1 |
| REQ-203 | Plan source `plans/swift-sniffing-meerkat.md` marked as superseded (not deleted) | 1 |
| REQ-204 | Bot token rotated via BotFather `/revoke` after Wave 4 verification passes | 1 |

## Out of Scope (deferred to v2.0+)

- `ultra-workshop` (Agno orchestrator + OpenHands coder sandbox)
- Discord / WhatsApp / Slack channel adapters
- Public HTTPS reverse proxy for AgentOS
- Webhook mode for Telegram (replaces long-poll)
- TTS / voice output
- Migration off LM Studio / LM Link
- Vault encryption at rest

## Acceptance criteria

A v1.0 ship requires all rows in the verification matrix from `plans/continue-from-las-session-tender-wand.md` to pass on the VPS, plus REQ-204 (token rotation) complete.
