# ultra-agents-brain

**Status:** Active — v2.0 in planning (v1.5 shipped 2026-05-22)
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
- ✓ Evals surface writes corrected AgentOS rows: live `performance` parents, suite `accuracy` rows, optional child `agent_as_judge` rows — Phase 12

### Active (v2.0 — AgentOS Surface Activation)

- [ ] Memory surface — agent runs trigger memory extraction; os.agno.com Memory tab shows real entries
- [ ] Knowledge surface — vault ingest populates knowledge table; agentic RAG hits visible in UI
- [ ] Approvals surface — HITL approval events surface in AgentOS approvals UI (not just Telegram)
- [ ] db_id architecture decision — investigate whether Agno expects per-agent db_ids; isolate vs. shared
- [ ] Observability — structured logging on each write path (memory, eval, knowledge, approval)
- [ ] worker.monitor polish — fix daily-brief date mismatch; v1.5 data-pipeline tech debt cleanup

### Deferred to v2.1+

- [ ] Discord adapter using channels/ pattern
- [ ] WhatsApp adapter using channels/ pattern
- [ ] Webhook mode for Telegram (replace long-poll)
- [ ] Vault GitHub remote for bidirectional sync (Mac ↔ VPS via Obsidian-Git + cron)
- [ ] X/Twitter + LinkedIn ingestion in worker.monitor

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

## Current State (post-v1.5)

**Shipped v1.5 (2026-05-22):** 9 phases, 15 plans, 51 commits over 3 days. 128 files, +6,093 / −950 LOC.
All 5 agents now run on Agno 2.6.7 production-grade config: Postgres+pgvector, semantic memory, agentic RAG, ReasoningTools, Pydantic-typed outputs, MCP+A2A, 5-tier LiteLLM routing with NVIDIA NIM. 48-case eval suite green with pre-commit router.

**Tech debt forward:** pre-commit install + real baseline regeneration (Phase 07), CostLedger verification after 1 week of use, VERIFICATION.md backfill for phases 1/2/8/9 (docs only).

**Phase 12 complete (2026-05-24):** eval row semantics corrected after live verification. New live agent rows are `performance` telemetry parents, suite rows remain deterministic `accuracy` rows, and optional live judgments are child `agent_as_judge` rows. Historical `Untitled Evaluation` rows are intentionally not migrated.

## Current Milestone: v2.0 AgentOS Surface Activation

**Goal:** Make the AgentOS UI (os.agno.com) show real data on all 4 feature surfaces — evals, memory, knowledge, approvals — by fixing the upstream write pipelines and resolving the shared-db_id question.

**Target features:**
- Diagnostic spike — trace every write path end-to-end (memory.add, eval.record, knowledge.ingest, approval.create)
- db_id architecture decision — per-agent isolation vs. shared workspace, based on Agno expectations
- Memory + Evals + Knowledge + Approvals surfaces all populate with real data after agent runs
- Observability — structured logging on each write path so future silent failures are detectable
- worker.monitor polish — daily-brief date mismatch + v1.5 data-pipeline tech debt cleanup

**Scope:** 1-week deep dive. Fixes + worker.monitor polish only — no new ingestion sources (X/Twitter, LinkedIn deferred to v2.1).

**Channels (Discord/WhatsApp/webhook) and vault GitHub sync:** deferred to v2.1.

**v3.0 — ultra-workshop** (separate repo, gated): begins after 2–4 weeks of v1.5+v2.0 production operation.

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

<details>
<summary>Earlier context (v1.0 shipped 2026-05-19)</summary>

1 phase, 1 plan, ~20 commits in one day. ~1,200 LOC Python across `agentos/`, `channels/`, `deploy/systemd/`. 38 automated tests. 5 systemd units on VPS.

</details>

---

*Last updated: 2026-05-24 — Phase 12 eval-row semantics corrected*
