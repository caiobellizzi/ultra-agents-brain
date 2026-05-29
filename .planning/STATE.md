---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: AgentOS Surface Activation
current_phase: complete
status: complete
last_updated: "2026-05-28T19:14:24.343Z"
last_activity: 2026-05-28 -- v2.0 milestone closed
progress:
  total_phases: 7
  completed_phases: 7
  total_plans: 25
  completed_plans: 25
  percent: 100
---

# STATE — ultra-agents-brain

**Updated:** 2026-05-22
**Milestone:** v1.5 — Agno Full Reconfiguration
**Status:** Executing Phase 15
**Current phase:** 15

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-19)

**Core value:** Always-on personal knowledge layer — vault RAG + autonomous routines + HITL
**Current focus:** Phase 15 — worker-monitor-polish-final-verification

## Shipped

- v1.0 (2026-05-19): AgentOS on Agno, Telegram adapter, 5 systemd units on VPS. 1 phase, 1 plan, 38 tests green.
- Phase 02 (wave-0-infra): DB wiring, model factory, Agno bootstrap — COMPLETE
- Phase 03 (wave-1-schemas): Typed result schemas + model factory — COMPLETE, verified 2026-05-20
- Phase 04 (wave-2-agents): All 5 agents reconfigured (memory, session, RAG, typed output) + PgVector knowledge layer — COMPLETE, verified 2026-05-20, 49 tests green
- Phase 05 (wave-3-wiring): PostgresDb, shared MemoryManager, MCP + A2A wired into AgentOS — COMPLETE, 54 tests green
- Phase 06 (wave-4-adapter): Telegram adapter typed response extraction, vault reindex entry point — COMPLETE, verified 2026-05-21, 55 tests green
- Phase 07 (wave-5-evals): evals/ scaffold + 18 real cases + baselines + pre-commit router — COMPLETE, verified 2026-05-21, 30 smoke tests green
- Phase 08 (litellm-nim-routing): NVIDIA NIM via LiteLLM + per-agent model routing — COMPLETE, 48/48 evals green, shipped 2026-05-22
- Phase 09 (litellm-provider-label): Relabel Agno dashboard provider OpenAI→LiteLLM — COMPLETE, shipped 2026-05-22
- Phase 11 (memory-surface-activation): PostgresDb.id pinned to `ultra-brain-main`, explicit Agent/Team ids, curator+ingest opted out of auto-extract, `InstrumentedMemoryManager` wired (with `update_memory_task` overrides for the agentic-tool path added in 11-03), supervisor `reasoning=False` unhung the team, telegram adapter `httpx.Timeout(read=90)` shape. MEM-01/02/03 ✅, OBS-01 ✅ (memory path fully satisfied — both auto-extraction and agentic-tool paths emit structured log lines). Shipped 2026-05-23.

## Deferred to v2.0+

- Vault GitHub remote sync (Mac ↔ VPS via Obsidian-Git + cron)
- Discord / WhatsApp channel adapters
- CostLedger full coverage — verify `_system/cost-ledger.md` fills after 1 week of use

## Key Decisions (summary — full log in PROJECT.md)

| Decision | Outcome |
|----------|---------|
| Build on Agno | ✓ Right call — HITL/memory/knowledge as first-class primitives |
| Wrap ultra_brain/*.py, don't rewrite | ✓ Zero regressions |
| Single-phase 4-wave roadmap | ✓ Right granularity for 1-day build |
| Defer ultra-workshop | — Pending 2–4 weeks production observation |

## v1.5 Decisions (locked from grill-me 2026-05-20)

| Decision | Outcome |
|----------|---------|
| Full reconfiguration sweep (all agents) | ✓ Not incremental — every agent gets full feature set |
| Postgres + pgvector (not Qdrant/Chroma) | ✓ Single DB for sessions + knowledge + evals |
| SentenceTransformerEmbedder all-MiniLM-L6-v2 | ✓ Local, offline, no API cost |
| MCP + A2A via Agno (no custom FastAPI routes) | ✓ Standard protocols discoverable by workshop |
| enable_mcp_server=True on AgentOS() only (get_app() reads it — no kwarg needed) | ✓ Actual Agno 2.6.7 API differs from docs |
| a2a-sdk pinned <1.0 (v1.0.3 broke SendMessageSuccessResponse import) | ✓ Fixed for agno 2.6.7 compatibility |
| PostgresDb with SqliteDb fallback when POSTGRES_DSN_SESSIONS absent | ✓ Dev/test environments need no Postgres |
| Eval pre-commit routing (not CI/systemd) | ✓ ≤15s single-agent, ≤90s full suite |
| EVAL_JUDGE_TIER env-var (default private-worker) | ✓ Free offline judge, override for releases |
| note_path checked before actions_taken in extract_reply_text | ✓ IngestResult carries both keys; note_path is primary discriminator |

## Current Position

Phase: 15 (worker-monitor-polish-final-verification) — EXECUTING
Plan: 1 of 3
Status: Executing Phase 15
Last activity: 2026-05-28 -- Phase 15 execution started

## Deferred Items

Items acknowledged and deferred at milestone close on 2026-05-28:

| Category | Item | Status |
|----------|------|--------|
| verification_gap | Phase 15 `15-VERIFICATION.md` | `human_needed` — VPS smoke run required human SSH; operator confirmed all 4 surfaces populated during UAT. Milestone audit scored passed. |
| verification_gap | Phase 16 `16-VERIFICATION.md` | `human_needed` — Phase 16 belongs to v2.5 milestone (out of v2.0 scope). |
