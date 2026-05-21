---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: — Agno Full Reconfiguration
current_phase: 5 (wave-3-wiring)
status: in-progress
last_updated: "2026-05-21T01:13:14.985Z"
progress:
  total_phases: 7
  completed_phases: 5
  total_plans: 13
  completed_plans: 9
  percent: 69
---

# STATE — ultra-agents-brain

**Updated:** 2026-05-20
**Milestone:** v1.5 — Agno Full Reconfiguration
**Status:** in-progress
**Current phase:** 5 (wave-3-wiring)

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-19)

**Core value:** Always-on personal knowledge layer — vault RAG + autonomous routines + HITL
**Current focus:** v1.5 — Agno full reconfiguration sweep (Phases 2–7)

## Shipped

- v1.0 (2026-05-19): AgentOS on Agno, Telegram adapter, 5 systemd units on VPS. 1 phase, 1 plan, 38 tests green.
- Phase 02 (wave-0-infra): DB wiring, model factory, Agno bootstrap — COMPLETE
- Phase 03 (wave-1-schemas): Typed result schemas + model factory — COMPLETE, verified 2026-05-20
- Phase 04 (wave-2-agents): All 5 agents reconfigured (memory, session, RAG, typed output) + PgVector knowledge layer — COMPLETE, verified 2026-05-20, 49 tests green
- Phase 05 (wave-3-wiring): PostgresDb, shared MemoryManager, MCP + A2A wired into AgentOS — COMPLETE, 54 tests green

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
