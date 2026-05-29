# Milestones

## v1.0 — Knowledge Layer on Agno (Shipped 2026-05-19)

**Scope:** 1 phase, 1 plan, ~20 commits.

**Key accomplishments:**

- AgentOS on Agno exposing 5 agents (chat, ingest, query, research, curator)
- Telegram adapter with HITL approval inline buttons
- 5 systemd units running on Hostinger VPS
- 38-test automated suite green; Nyquist compliant
- LiteLLM gateway + CostLedger integration

Archive: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md) · [milestones/v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md) · [milestones/v1.0-MILESTONE-AUDIT.md](milestones/v1.0-MILESTONE-AUDIT.md)

---

## v1.5 — Agno Full Reconfiguration (Shipped 2026-05-22)

**Scope:** 9 phases, 15 plans, 51 commits, 128 files, +6,093 / −950 LOC. Built in 3 days (2026-05-20 → 2026-05-22).

**Key accomplishments:**

- Postgres 16 + pgvector running on VPS — single DB for sessions, knowledge, evals; SqliteDb fallback for dev/test.
- All 5 agents reconfigured for Agno 2.6.7: semantic memory, agentic RAG, ReasoningTools, Pydantic-typed outputs.
- MCP server + A2A protocol wired via `AgentOS(enable_mcp_server=True)` — discoverable surface for future ultra-workshop.
- 48-case eval suite with pre-commit router (≤15s single-agent, ≤90s full); `EVAL_JUDGE_TIER` swap for stronger judges in releases.
- 5-tier LiteLLM matrix with NVIDIA NIM as third cloud backend + capability-routed fallbacks; pre-call hook strips `response_format` when models combine it with tools.
- Telegram adapter typed-response extraction + vault reindex entry point.
- Agno dashboard reports every agent as `provider: LiteLLM` (instead of misleading "OpenAI") via `LiteLLMChat` subclass.

Archive: [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md) · [v1.5-MILESTONE-AUDIT.md](v1.5-MILESTONE-AUDIT.md)

**Tech debt forward:** pre-commit install + real-baseline regeneration (Phase 07), CostLedger verification after 1 week of use, missing VERIFICATION.md on phases 1, 2, 8, 9 (docs only — features verified inline).

---

## v2.0 — AgentOS Surface Activation (Shipped 2026-05-28)

**Scope:** 6 phases (10–15), 18 plans, ~50 commits, 281 files changed, +32,809 / −4,092 LOC. Built in 6 days (2026-05-22 → 2026-05-28).

**Key accomplishments:**

- All 4 AgentOS surfaces populated with live data: memory (74 rows), evals (155), knowledge (3,291), approvals (4)
- `db_id="ultra-brain-main"` shared workspace model adopted across all 5 agents — single Postgres workspace for os.agno.com
- `InstrumentedMemoryManager`, `InstrumentedEvalRecorder`, `InstrumentedKnowledge`, `ApprovalRecorder` — OBS-01 structured logging on all 9 write events
- `@approval` root cause found and fixed: stacked decorator bug was blocking all approval rows
- Daily-brief date-mismatch bug fixed (regression test); vault sync `--delete` safety fixed (regression test)
- `make check-surfaces` smoke tool written (psycopg3 migration applied)

**Known deferred items at close:** 2 (see STATE.md Deferred Items — Phase 15 VPS-only verification already confirmed by human; Phase 16 is v2.5 scope)

Archive: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md) · [milestones/v2.0-REQUIREMENTS.md](milestones/v2.0-REQUIREMENTS.md) · [milestones/v2.0-MILESTONE-AUDIT.md](milestones/v2.0-MILESTONE-AUDIT.md)

---
