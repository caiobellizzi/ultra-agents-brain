# Roadmap — ultra-agents-brain

## Milestones

- ✅ **v1.0 — Knowledge Layer on Agno** — shipped 2026-05-19 ([archive](milestones/v1.0-ROADMAP.md))
- ✅ **v1.5 — Agno Full Reconfiguration** — shipped 2026-05-22, 9 phases, 15 plans ([archive](milestones/v1.5-ROADMAP.md))
- ✅ **v2.0 — AgentOS Surface Activation** — shipped 2026-05-28, 6 phases, 18 plans ([archive](milestones/v2.0-ROADMAP.md))
- 📋 **v2.1 — Channels** — planned (Discord + WhatsApp + Telegram webhook + vault GitHub sync)
- ✅ **v2.5 — Brain Vault Overhaul** — shipped 2026-05-26 (Phase 16, 4 plans) ([phases/16-brain-vault-overhaul](phases/16-brain-vault-overhaul/))
- ✅ **v2.6 — Brain Knowledge Pipelines** — shipped 2026-05-27 (Phases 17–18, 3 plans) ([phases/17-multi-repo-brain-pipelines](phases/17-multi-repo-brain-pipelines/))
- 📋 **v3.0 — ultra-workshop** — planned (separate repo, after 2–4 weeks of v2.0 production operation)

---

## Phases

<details>
<summary>✅ v1.5 — Agno Full Reconfiguration (Phases 2–9) — SHIPPED 2026-05-22</summary>

- [x] Phase 2: wave-0-infra (DB wiring, model factory, Agno bootstrap) — completed 2026-05-20
- [x] Phase 3: wave-1-schemas (typed result schemas + model factory) — completed 2026-05-20
- [x] Phase 4: wave-2-agents (5 agents reconfigured, PgVector knowledge layer) — completed 2026-05-20
- [x] Phase 5: wave-3-wiring (PostgresDb, shared MemoryManager, MCP + A2A) — completed 2026-05-21
- [x] Phase 6: wave-4-adapter (Telegram adapter, vault reindex entry point) — completed 2026-05-21
- [x] Phase 7: wave-5-evals (48-case evals + pre-commit router) — completed 2026-05-21
- [x] Phase 8: litellm-nim-routing (NVIDIA NIM + per-agent model routing) — completed 2026-05-22
- [x] Phase 9: litellm-provider-label (LiteLLM label on Agno dashboard) — completed 2026-05-22

Archive: [milestones/v1.5-ROADMAP.md](milestones/v1.5-ROADMAP.md)
</details>

<details>
<summary>✅ v2.0 — AgentOS Surface Activation (Phases 10–15) — SHIPPED 2026-05-28</summary>

**Goal:** Make os.agno.com show real data on all 4 feature surfaces (evals, memory, knowledge, approvals) by fixing the upstream write pipelines. Resolve shared-`db_id` question. Clean v1.5 worker.monitor tech debt.

- [x] Phase 10: Diagnostic Audit (2/2 plans) — completed 2026-05-22
- [x] Phase 11: Memory Surface Activation (3/3 plans) — completed 2026-05-23
- [x] Phase 12: Evals Surface Activation (4/4 plans) — completed 2026-05-24
- [x] Phase 13: Knowledge Surface Activation (3/3 plans) — completed 2026-05-23
- [x] Phase 14: Approvals Surface Activation (3/3 plans) — completed 2026-05-28
- [x] Phase 15: worker.monitor Polish + Final Verify (3/3 plans) — completed 2026-05-28

**Live VPS row counts at close:** memory 74 · evals 155 · knowledge 3,291 · approvals 4

Archive: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md) · [milestones/v2.0-REQUIREMENTS.md](milestones/v2.0-REQUIREMENTS.md) · [milestones/v2.0-MILESTONE-AUDIT.md](milestones/v2.0-MILESTONE-AUDIT.md)
</details>

<details>
<summary>✅ v2.5 — Brain Vault Overhaul (Phase 16) — SHIPPED 2026-05-26</summary>

**Goal:** Turn the Obsidian second brain from a read-it-later pile into a genuine leverage multiplier — TELOS-scored ingestion, spec-driven shipping from brain, and automated hygiene loops.

- [x] Phase 16: Brain Vault Overhaul (4/4 plans) — completed 2026-05-26
  - 16-01: Fill TELOS (mission/goals/values/dont-do); flip status to active
  - 16-02: Inbox sweep (scripts/inbox_sweep.py) + write _system/operating-manual.md
  - 16-03: Graph bridge (reindex_bridge.sh) + Brief→SPEC.md generator (spec_gen.py)
  - 16-04: Automation loops (daily triage, weekly review HITL, monthly TELOS recheck, project-mirror sync)
</details>

<details>
<summary>✅ v2.6 — Brain Knowledge Pipelines (Phases 17–18) — SHIPPED 2026-05-27</summary>

**Goal:** Make all enrolled repos queryable from Telegram by compiling nightly LLM prose summaries via GitHub Actions and landing them in the second-brain vault as `repos/<name>.md` files.

- [x] Phase 17: Multi-Repo Brain Pipelines (1/1 plans) — completed 2026-05-27
  - Full pipeline: brain-pipelines repo + aggregate + local script cleanup + caller stub
- [x] Phase 18: Auto-sync second-brain → VPS + pgvector reindex (2/2 plans) — completed 2026-05-27
  - 18-01: SSH deploy key setup (manual checkpoint)
  - 18-02: reindex-vault.sh + git-sync.sh edit + VPS deploy + end-to-end smoke test
</details>

---

## Future milestones (preview)

### 📋 v2.1 — Channels

Discord adapter, WhatsApp adapter, Telegram webhook mode, vault GitHub remote bidirectional sync, X/Twitter + LinkedIn ingestion in worker.monitor.

### 📋 v3.0 — ultra-workshop

Separate repo. Gated on 2–4 weeks of v2.0 production operation. On-demand coding/PR/deploy agent team using OpenHands.

---

## Progress

| Phase | Milestone | Plans Complete | Status   | Completed  |
|-------|-----------|----------------|----------|------------|
| 10. Diagnostic Audit | v2.0 | 2/2 | Complete | 2026-05-22 |
| 11. Memory Surface Activation | v2.0 | 3/3 | Complete | 2026-05-23 |
| 12. Evals Surface Activation | v2.0 | 4/4 | Complete | 2026-05-24 |
| 13. Knowledge Surface Activation | v2.0 | 3/3 | Complete | 2026-05-23 |
| 14. Approvals Surface Activation | v2.0 | 3/3 | Complete | 2026-05-28 |
| 15. worker.monitor Polish | v2.0 | 3/3 | Complete | 2026-05-28 |
| 16. Brain Vault Overhaul | v2.5 | 4/4 | Complete | 2026-05-26 |
| 17. Multi-Repo Brain Pipelines | v2.6 | 1/1 | Complete | 2026-05-27 |
| 18. Auto-sync second-brain → VPS | v2.6 | 2/2 | Complete | 2026-05-27 |
