# ultra-agents-brain

**Status:** Active — v1.0 shipped 2026-05-19
**Created:** 2026-05-19

## What it is

A **personal AI second brain** built on the [Agno](https://docs.agno.com/) agent framework. Always-on, autonomously ingests and curates a Markdown vault (Obsidian-compatible), and serves RAG context over chat (Telegram today, other channels later) and HTTP (for future agent teams).

**Tier 1 — Knowledge Layer** of a planned two-tier architecture. **Tier 2 — `ultra-workshop`** (on-demand coding/PR/deploy agent team using OpenHands) is deferred to a separate repo, to begin after 2–4 weeks of Brain production operation.

## Why it exists

Owner wants a single trusted system that:
1. Captures useful content (URLs, notes, research prompts) into a structured vault without manual filing.
2. Answers questions over that vault with evidence-cited responses.
3. Runs daily/weekly/4-hourly autonomous routines (digest, review, feed polling) without supervision.
4. Gates expensive or irreversible actions with cost/trust controls + HITL approval.
5. Acts as the foundational knowledge layer for a future coding-agent team.

## Architecture

```
Vault (/srv/second-brain, Markdown) ←→ AgentOS (FastAPI, Agno, :7000)
                                              ↑
                                              │ POST /agents/{id}/runs
                              ┌───────────────┼────────────────┐
                              │               │                │
                       Telegram adapter   systemd timers   (future: HTTP
                       (long-poll)        (curl POST)       clients)
```

**Key invariants:**
- AgentOS is the single source of truth for agent behavior. Channels are dumb adapters.
- Existing `ultra_brain/*.py` modules are WRAPPED, not rewritten, as Agno tools.
- Cron timers hit HTTP, not Python — curator behavior shared across invokers.
- HITL gates live in Agno (SqliteDb persistence) — approvals survive restarts.
- LLM access via LiteLLM proxy on `127.0.0.1:4000`.

## Stack

- **Agent framework:** Agno 2.6.7 (pinned)
- **HTTP:** FastAPI + uvicorn (via Agno AgentOS)
- **Bot:** python-telegram-bot (long-poll)
- **Knowledge store:** Markdown + Agno `MarkdownKnowledgeBase`
- **Memory/HITL:** Agno `SqliteDb` at `/var/lib/uab/`
- **LLM gateway:** LiteLLM proxy → LM Studio gemma-4-e4b via LM Link
- **Process supervision:** systemd (5 units: brain, telegram, 3 timers)
- **Hosting:** Hostinger VPS `31.97.130.253`

## Requirements

### Validated

- ✓ AgentOS exposes 5 agents (chat, ingest, query, research, curator) via Agno-native routes — v1.0
- ✓ Telegram adapter long-polls, routes messages to agents, renders HITL approval buttons — v1.0
- ✓ trust_gate (HITL) wraps all write tools; HITL approvals persist in SqliteDb — v1.0
- ✓ All LLM calls route through LiteLLM proxy on 127.0.0.1:4000 — v1.0
- ✓ CostLedger integration via litellm success_callback — v1.0
- ✓ systemd timers fire digest (20:00), review (Sun 18:00), poll_feeds (every 4h) — v1.0
- ✓ 4 STRIDE security mitigations applied (allowlist, callback_data, uabrain user, no hardcoded key) — v1.0
- ✓ 38-test automated suite green; Nyquist compliant — v1.0

### Active (v2.0+)

- [ ] Discord adapter using channels/ pattern
- [ ] WhatsApp adapter using channels/ pattern
- [ ] Webhook mode for Telegram (replace long-poll)
- [ ] Vault GitHub remote for bidirectional sync (Mac ↔ VPS via Obsidian-Git + cron)

### Out of Scope

- Public HTTPS reverse proxy for AgentOS — stays on 127.0.0.1
- Migration off LM Studio / LM Link — kept
- TTS / voice output
- ultra-workshop (separate repo, v3.0)

## Key Decisions

| Decision | Outcome | Notes |
|----------|---------|-------|
| Build on Agno (not native Python bot) | ✓ Good | Agno provided memory/HITL/observability as first-class primitives |
| Wrap `ultra_brain/*.py` as Agno tools, don't rewrite | ✓ Good | Preserved working code; only llm.py replaced |
| AgentOS = single source of truth; channels = dumb adapters | ✓ Good | Telegram adapter is 350 LOC, pure routing |
| Single-phase, 4-wave roadmap | ✓ Good | Right granularity for one-person 1-day build |
| Use `agno.os.app.AgentOS` (not hand-rolled FastAPI) | ✓ Good | Enables os.agno.com dashboard; standard route shape |
| Pin agno at exact version (2.6.7) | ✓ Good | API drift would be invisible without pinning |
| ultra-workshop deferred 2–4 weeks | — Pending | Validate Brain in daily use before building Workshop |
| Hermes Docker image was hallucinated | ✓ Resolved | Replaced with native Python + Agno from the start |

## Context

**Shipped v1.0 (2026-05-19):** 1 phase, 1 plan, ~20 commits in one day.
~1,200 LOC Python across `agentos/`, `channels/`, `deploy/systemd/`.
38 automated tests (pytest). 5 systemd units on VPS. Both services active.

Known tech debt: CostLedger via litellm callback (fires only in SDK mode, not proxy mode — monitor ledger file after 1 week of use). Vault GitHub remote sync not yet wired.

**Next:** Let Brain run for 2–4 weeks. Monitor vault quality, digest relevance, cost ledger. Then plan v2.0 (Channels) or v3.0 (ultra-workshop) based on operational learnings.

---

*Last updated: 2026-05-19 after v1.0 milestone*
