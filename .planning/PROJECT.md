# ultra-agents-brain

**Status:** Active — v2.0 shipped 2026-05-28 (planning v2.1)
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
- ✓ Memory surface — `InstrumentedMemoryManager` wired; os.agno.com Memory tab shows 74 rows — v2.0 Phase 11
- ✓ Knowledge surface — vault 3,291 pgvector rows; `InstrumentedKnowledge` wrapping RAG hits — v2.0 Phase 13
- ✓ Approvals surface — `ApprovalRecorder` wired; HITL events appear in AgentOS approvals UI — v2.0 Phase 14
- ✓ db_id architecture — shared `db_id="ultra-brain-main"` for all 5 agents; single workspace model — v2.0 Phase 10
- ✓ Observability — OBS-01 structured logging on all 9 write events across 4 surfaces — v2.0 Phases 11–14
- ✓ worker.monitor polish — daily-brief date mismatch fixed; vault sync `--delete` safety fixed — v2.0 Phase 15
- ✓ `make check-surfaces` smoke tool — psycopg3, all 4 surfaces verified non-zero — v2.0 Phase 15
- ✓ Brain Vault Overhaul — TELOS filled, inbox sweep, operating manual, SPEC.md generator, 4 automation loops — v2.5 Phase 16
- ✓ Multi-repo brain pipelines — nightly LLM prose summaries via GitHub Actions → `repos/*.md` → vault — v2.6 Phase 17
- ✓ Auto-sync second-brain → VPS — SSH deploy key, git-sync.sh, reindex-vault.sh triggered on `.md` changes — v2.6 Phase 18

### Active (v2.1 — Channels)

- [ ] Discord adapter using `channels/` pattern
- [ ] WhatsApp adapter using `channels/` pattern
- [ ] Webhook mode for Telegram (replace long-poll)
- [ ] Vault GitHub remote bidirectional sync (Mac ↔ VPS via Obsidian-Git + cron)

### Deferred to v2.1+

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
| `db_id="ultra-brain-main"` shared by all 5 agents | ✓ Good | Simpler than per-agent isolation for a single-owner system; os.agno.com workspace model works correctly |
| Post-run wrapper for eval recording (no subclass) | ✓ Good | Avoids Agno internal coupling; `InstrumentedEvalRecorder.wrap(agent)` pattern is portable |
| `performance` vs `accuracy` eval row semantics | ✓ Good | Live telemetry rows are `performance` parents; suite rows are `accuracy`; optional child `agent_as_judge` rows |
| Stacked `@approval + @tool(requires_confirmation=True)` was root cause | ✓ Resolved | Single `@approval` on `ingest_to_vault` is the fix; double-decoration blocks the approval event |
| psycopg3 for check_surfaces.py | ✓ Good | Project uses psycopg[binary]>=3.2; psycopg2 was never a transitive dep |

## Current State (post-v2.0)

**Shipped v2.0 (2026-05-28):** 6 phases (10–15), 18 plans, ~50 commits in 6 days. 281 files changed, +32,809 / −4,092 LOC.
All 4 AgentOS surfaces now populated with live data: memory 74 rows, evals 155 rows, knowledge 3,291 rows, approvals 4 rows. `db_id="ultra-brain-main"` shared workspace model. OBS-01 structured logging on all 9 write events. `make check-surfaces` smoke tool.

**Also shipped ahead of milestone schedule:**
- v2.5 Brain Vault Overhaul (Phase 16, 2026-05-26): TELOS filled, inbox sweep, operating manual, SPEC.md generator, 4 automation loops
- v2.6 Brain Knowledge Pipelines (Phases 17–18, 2026-05-27): nightly LLM prose summaries via GitHub Actions, auto-sync second-brain → VPS, git-sync.sh + pgvector reindex on `.md` changes

**Tech debt forward:** eval row model_id/model_provider null; only test_curator.py wired to suite; vault reindex is manual CLI; check_surfaces.py VPS-only (SSH required); MEM-03 enable_user_memories never set (agentic path active).

## Next Milestone: v2.1 — Channels

**Goal:** Expand the channel surface — Discord adapter, WhatsApp adapter, Telegram webhook mode, vault GitHub remote bidirectional sync.

**Gating:** Begin after 2–4 weeks of v2.0 production observation to validate Brain stability before adding complexity.

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

*Last updated: 2026-05-28 after v2.0 milestone close*
