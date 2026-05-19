# ultra-agents-brain

**Status:** Active (Milestone v1.0)
**Created:** 2026-05-19
**Source vision:** `plans/continue-from-las-session-tender-wand.md`

## What it is

A **personal AI second brain** built on the [Agno](https://docs.agno.com/) agent framework. Always-on, autonomously ingests and curates a Markdown vault (Obsidian-compatible), and serves RAG context over chat (Telegram today, other channels later) and HTTP (for future agent teams).

This is **Tier 1 — Knowledge Layer** of a planned two-tier architecture. **Tier 2 — `ultra-workshop`** (on-demand coding/PR/deploy agent team using OpenHands) is deferred to a separate repo and future session, after this Brain has been running daily for 2–4 weeks.

## Why it exists

Owner wants a single trusted system that:
1. Captures useful content (URLs, notes, research prompts) into a structured vault without manual filing.
2. Answers questions over that vault with evidence-cited responses.
3. Runs daily/weekly/4-hourly autonomous routines (digest, review, feed polling) without supervision.
4. Gates expensive or irreversible actions with cost/trust controls + HITL approval.
5. Acts as the foundational knowledge layer for a future coding-agent team.

The original "200-LOC native Python bot" plan was descoped — real requirements (long-term memory, HITL, observability) would inflate it to 800+ LOC in weeks. Agno provides all those as first-class primitives.

## Architecture (locked)

```
Vault (/srv/second-brain, Markdown) ←→ AgentOS (FastAPI, Agno, :7000)
                                              ↑
                                              │ POST /v1/agents/*
                              ┌───────────────┼────────────────┐
                              │               │                │
                       Telegram adapter   systemd timers   (future: HTTP
                       (long-poll)        (curl POST)       clients)
```

**Key invariants:**
- **AgentOS is the single source of truth** for agent behavior. Channels are dumb adapters.
- **Existing `ultra_brain/*.py` modules are WRAPPED, not rewritten** as Agno tools.
- **Cron timers hit HTTP, not Python** — curator behavior shared across invokers.
- **HITL gates live in Agno** (SqliteDb persistence) — approvals survive restarts.
- **LLM access via LiteLLM proxy** on `127.0.0.1:4000` (already running on VPS) using `OpenAIProvider(base_url=...)`. Routes to LM Studio gemma-4-e4b on Mac via LM Link.

## Stack (locked)

- **Language:** Python 3.10+
- **Agent framework:** Agno (Apache-2.0, pinned version)
- **HTTP:** FastAPI + uvicorn
- **Bot:** python-telegram-bot (long-poll)
- **Knowledge store:** Markdown files on disk + Agno's `MarkdownKnowledgeBase`
- **Memory/HITL:** Agno `SqliteDb` at `/var/lib/uab/`
- **LLM gateway:** LiteLLM (already deployed)
- **Process supervision:** systemd (`uab-brain.service`, `uab-telegram.service`, 3 timers)
- **Hosting:** Hostinger VPS at `srv1381850.hstgr.cloud` (31.97.130.253)

## Out of scope (v1.0)

- `ultra-workshop` (coding/PR/deploy agent team) — separate repo, future
- Discord, WhatsApp, Slack adapters — channel pattern in place, only Telegram implemented
- Public HTTPS for AgentOS — stays on `127.0.0.1`
- Webhook mode for Telegram — long-poll is fine
- Migration off LM Studio / LM Link — kept

## Success picture (v1.0 = Milestone Complete)

Owner can:
- Send `ingest <url>` to the Telegram bot, approve via inline button, find the note in the vault within ~30 s.
- Ask "what do I know about X" and get an evidence-cited answer pulled from the vault.
- Receive an automatic daily digest at 20:00 in Telegram.
- Restart `uab-brain.service` mid-conversation — session memory and pending approvals survive.
- Audit cost spend via `_system/cost-ledger.md` after a week's use.

## Owner constraints

- Building solo, evenings/weekends — keep scope tight to ~3–5 days of focused work.
- No third-party paid services beyond what's already running (LiteLLM + Hostinger VPS).
- Bot token + LLM gateway are owner-managed (token rotation post-deploy noted).
