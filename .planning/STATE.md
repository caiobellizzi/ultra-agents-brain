# STATE — ultra-agents-brain

**Updated:** 2026-05-19
**Milestone:** v1.0 — COMPLETE
**Status:** shipped

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-19)

**Core value:** Always-on personal knowledge layer — vault RAG + autonomous routines + HITL
**Current focus:** Production observation (2–4 weeks) before v2.0 planning

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
