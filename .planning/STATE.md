---
gsd_state_version: 1.0
milestone: v1.5
milestone_name: — Agno Full Reconfiguration
current_phase: 3 (wave-1-schemas)
status: in-progress
last_updated: "2026-05-20T19:10:00.000Z"
progress:
  total_phases: 7
  completed_phases: 2
  total_plans: 13
  completed_plans: 3
  percent: 23
---

# STATE — ultra-agents-brain

**Updated:** 2026-05-20
**Milestone:** v1.5 — Agno Full Reconfiguration
**Status:** in-progress
**Current phase:** 3 (wave-1-schemas)

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-19)

**Core value:** Always-on personal knowledge layer — vault RAG + autonomous routines + HITL
**Current focus:** v1.5 — Agno full reconfiguration sweep (Phases 2–7)

## Shipped

- v1.0 (2026-05-19): AgentOS on Agno, Telegram adapter, 5 systemd units on VPS. 1 phase, 1 plan, 38 tests green.

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
| enable_mcp_server=True on BOTH AgentOS() AND get_app() | ✓ Gotcha from docs-research |
| Eval pre-commit routing (not CI/systemd) | ✓ ≤15s single-agent, ≤90s full suite |
| EVAL_JUDGE_TIER env-var (default private-worker) | ✓ Free offline judge, override for releases |
