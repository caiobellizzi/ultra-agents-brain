# Roadmap — ultra-agents-brain

## Milestones

- ✅ **v1.0 — Knowledge Layer on Agno** — Phase 1 (shipped 2026-05-19)
- 🔄 **v1.5 — Agno Full Reconfiguration** — Phases 2–7 (in progress)
- 📋 **v2.0 — Channels** — planned
- 📋 **v3.0 — ultra-workshop** — planned (after 2–4 weeks v1.0 production operation)

## Phases

<details>
<summary>✅ v1.0 — Knowledge Layer on Agno (Phase 1) — SHIPPED 2026-05-19</summary>

- [x] Phase 1: ultra-brain-agno (1/1 plan) — completed 2026-05-19

</details>

### 🔄 v1.5 — Agno Full Reconfiguration

Upgrade all 5 agents from minimal v1.0 config to Agno 2.6.7 production-grade feature set:
Postgres/pgvector, per-user semantic memory, agentic RAG over vault, ReasoningTools, Pydantic-typed outputs, MCP server, A2A protocol, and comprehensive evals.

- [x] Phase 2: wave-0-infra — Postgres 16 + pgvector on VPS (1/1 plan) — completed 2026-05-20
- [x] Phase 3: wave-1-schemas — Pydantic schemas + model factory (1 plan) (completed 2026-05-20)
- [ ] Phase 4: wave-2-agents — Per-agent reconfiguration, 5 commits (5 plans)
- [ ] Phase 5: wave-3-agentos — AgentOS surface: PostgresDb, MemoryManager, MCP, A2A (1 plan)
- [ ] Phase 6: wave-4-adapter — Telegram adapter typed responses + vault reindex (1 plan)
- [ ] Phase 7: wave-5-evals — Evals scaffolding, coverage, and baselines (3 plans)

### 📋 v2.0 — Channels (Planned)

Add Discord and WhatsApp adapters using the `channels/` pattern established in v1.0. Optional: webhook mode for Telegram.

### 📋 v3.0 — ultra-workshop (Planned)

Separate repo. Agno orchestrator + OpenHands coder sandbox. Reads from Brain via HTTP. Begins only after v1.0 has been running daily for 2–4 weeks.

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|---------------|--------|-----------|
| 1. ultra-brain-agno | v1.0 | 1/1 | Complete | 2026-05-19 |
| 2. wave-0-infra | v1.5 | 1/1 | Complete | 2026-05-20 |
| 3. wave-1-schemas | v1.5 | 1/1 | Complete   | 2026-05-20 |
| 4. wave-2-agents | v1.5 | 4/5 | In Progress|  |
| 5. wave-3-agentos | v1.5 | 0/1 | Planned | — |
| 6. wave-4-adapter | v1.5 | 0/1 | Planned | — |
| 7. wave-5-evals | v1.5 | 0/3 | Planned | — |
