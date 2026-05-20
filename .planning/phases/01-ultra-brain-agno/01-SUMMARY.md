---
phase: 1
slug: ultra-brain-agno
status: complete
plan: 01-01-PLAN.md
uat: 01-UAT.md
security: 01-SECURITY.md
completed_at: 2026-05-19
---

# Phase 1 Summary — ultra-brain-agno

Replaced the hallucinated Hermes Docker runtime with a real Agno-based AgentOS. All
`ultra_brain/*.py` modules are wrapped as Agno tools. A FastAPI package (`agentos/`)
hosts 5 agents; `channels/telegram_adapter.py` long-polls Telegram and POSTs to AgentOS.
Five systemd units deployed to VPS at `/opt/ultra-agents-brain/`.

## Requirements Delivered

| Req ID | Description | Status |
|--------|-------------|--------|
| W1.1 | Agno docs reviewed; LiteLLM proxy compatibility confirmed | done |
| W1.2 | `scripts/smoke_agno.py` — Agno smoke test against gemma-4-e4b | done |
| W2.1 | `requirements.txt` with agno==2.6.7 pinned | done |
| W2.2 | `agentos/knowledge.py` — MarkdownKnowledgeBase wrapping `/srv/second-brain` | done |
| W2.3 | `agentos/tools/vault.py` — 7 @tool wrappers (ingest, query, research, digest, review, lint, poll) | done |
| W2.4 | `agentos/tools/safety.py` — trust_gate decorator with HITL integration | done |
| W2.5 | 5 agent files: chat, ingest, query, research, curator | done |
| W2.6 | `agentos/app.py` — AgentOS app on :7000; all 5 agents registered | done |
| W3.1 | `channels/telegram_adapter.py` — long-poll adapter with routing + HITL approval flow | done |
| W3.2 | Local smoke test (API-verified) | done |
| W4.1 | 5 systemd units: uab-brain, uab-telegram, uab-digest.timer, uab-review.timer, uab-monitor.timer | done |
| W4.2 | Rsync deploy to VPS root@31.97.130.253:/opt/ultra-agents-brain/ | done |
| W4.3 | VPS install + systemd enable — both services active (running) | done |
| W4.4 | Cleanup: old ultra-agents-brain.service disabled | done |
| SEC.1 | Telegram adapter fails fast on empty TELEGRAM_ALLOWED_CHAT_IDS | done |
| SEC.2 | callback_data validated before URL interpolation (no injection) | done |
| SEC.3 | Both systemd services run as `uabrain` user (not root) | done |
| SEC.4 | Hardcoded LITELLM_MASTER_KEY fallback removed | done |

## Key Files Changed

| File | Change |
|------|--------|
| `agentos/__init__.py` | New — package root |
| `agentos/app.py` | New — AgentOS host on :7000 |
| `agentos/model.py` | New — LiteLLM model config (fallback key removed) |
| `agentos/db.py` | New — SqliteDb session store |
| `agentos/knowledge.py` | New — MarkdownKnowledgeBase |
| `agentos/tools/vault.py` | New — 7 tool wrappers |
| `agentos/tools/safety.py` | New — trust_gate HITL decorator |
| `agentos/agents/chat.py` | New |
| `agentos/agents/ingest.py` | New |
| `agentos/agents/query.py` | New |
| `agentos/agents/research.py` | New |
| `agentos/agents/curator.py` | New |
| `channels/telegram_adapter.py` | New — long-poll Telegram bridge (security-patched) |
| `deploy/systemd/uab-brain.service` | New — runs as uabrain user |
| `deploy/systemd/uab-telegram.service` | New — runs as uabrain user |
| `deploy/systemd/uab-digest.timer` | New — daily 20:00 |
| `deploy/systemd/uab-review.timer` | New — Sun 18:00 |
| `deploy/systemd/uab-monitor.timer` | New — every 4h |

## UAT Results

| Total | Passed | Skipped | Issues |
|-------|--------|---------|--------|
| 11    | 6      | 5       | 0      |

Skipped tests (5) require live Telegram interaction — cannot be automated from CLI.
All infrastructure tests pass. No open issues at phase close.

## Verify Commands

```bash
# VPS health
ssh root@31.97.130.253 "systemctl status uab-brain uab-telegram"
ssh root@31.97.130.253 "curl -sf 127.0.0.1:7000/health"

# Chat API
ssh root@31.97.130.253 "curl -sf -X POST 127.0.0.1:7000/agents/chat/runs -F 'message=hi' -F 'stream=false'"

# Timers
ssh root@31.97.130.253 "systemctl list-timers | grep uab"
```

## Decisions During Execution

- Used `agno.os.app.AgentOS` (not hand-rolled FastAPI) — enables os.agno.com dashboard
- agno pinned at 2.6.7 to avoid API drift
- Session key strategy: `telegram-{chat_id}` per Telegram chat
- Security hardening applied retroactively before phase close (STRIDE audit)
- `uabrain` system user created on VPS for service isolation
