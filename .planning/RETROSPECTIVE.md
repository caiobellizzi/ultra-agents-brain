# Project Retrospective — ultra-agents-brain

*A living document updated after each milestone. Lessons feed forward into future planning.*

---

## Milestone: v1.0 — Knowledge Layer on Agno

**Shipped:** 2026-05-19
**Phases:** 1 | **Plans:** 1 | **Sessions:** ~1 day of focused work

### What Was Built

- Full Agno-based AgentOS (`agentos/` package) wrapping all `ultra_brain/*.py` modules as tools
- 5 agents (chat, ingest, query, research, curator) with HITL gates on write tools
- Telegram long-poll adapter with inline approval buttons, allowlist security, and routing logic
- 5 systemd units deployed to VPS; both services active and running as `uabrain` user
- 3 cron timers (digest 20:00, review Sun 18:00, poll_feeds every 4h)
- 4 STRIDE security mitigations applied retroactively (zero threats open at ship)
- 38-test automated suite (pytest); Nyquist compliant

### What Worked

- **4-wave structure** — right granularity for a 1-person 1-day build; each wave had a clear smoke test before advancing.
- **Agno as framework choice** — provided memory, HITL, knowledge, and session persistence as first-class primitives. Eliminated ~500 LOC of would-be custom code.
- **Wrap, don't rewrite** — keeping `ultra_brain/*.py` intact meant zero regression risk on core logic.
- **GSD retroactive validation** — gsd-nyquist-auditor filled 8 gaps on first pass; 38 tests green with no debug iteration.
- **Security as a phase gate** — STRIDE audit before phase close caught 4 real issues (T-01 injection, E-01/I-02 root process, E-02 open allowlist, I-01 hardcoded key). All closed before ship.

### What Was Inefficient

- **Hermes hallucination** — the original plan assumed a `hermes` Docker image that didn't exist. Cost ~0.5h of investigation before pivoting to Agno. Lesson: verify base image existence before planning.
- **Agno 2.6.7 HITL quirk** — `requires_confirmation=True` + `/continue` endpoint behavior not in docs; required a fix cycle (commit e010792). Would have been caught by pre-build Agno spike.
- **Route shape drift** — REQUIREMENTS.md documented `/v1/agents/chat` but Agno uses `/agents/{id}/runs`. Discovered at audit, not at plan time. Plan should specify actual Agno route conventions.
- **Duplicate "2.py" files** — macOS Finder created 33 duplicate files that required cleanup at audit. Gitignore or commit hygiene should prevent this.
- **CostLedger wired late** — REQ-011 was missed during execution, caught only at audit. Cost tracking hook should be in Wave 2 plan as an explicit task.

### Patterns Established

- **Channels as dumb adapters** — AgentOS owns all agent logic; channel adapters only route and format. Pattern holds for Discord/WhatsApp additions.
- **litellm success_callback for cost tracking** — registered at app startup in `agentos/cost.py`; fires transparently for all model calls.
- **systemd + uabrain user** — process isolation pattern for VPS services; `PrivateTmp=true`, `NoNewPrivileges=true`, `ReadWritePaths=` whitelist.
- **Agno HITL via SqliteDb** — approvals survive restarts; single shared db at `/var/lib/uab/agno.db` for all agents.
- **GSD retroactive Nyquist** — when phase was executed manually outside executor, `gsd-validate-phase` + `gsd-nyquist-auditor` filled all gaps retroactively with zero escalations.

### Key Lessons

1. **Spike Agno HITL behavior before Wave 3** — the `/continue` endpoint shape is underdocumented; a 30-min spike would have eliminated the HITL fix cycle.
2. **Add cost ledger task to Wave 2 explicitly** — "wire CostLedger" is easy to forget because it's not visible at execution time; add it to any plan that involves LLM calls.
3. **Lock route shapes in the plan** — when a framework owns the HTTP surface (Agno, FastAPI), document the actual routes in the plan, not the intended ones.
4. **Run `gsd-audit-milestone` before declaring done** — caught 5 unsatisfied requirements that SUMMARY.md and UAT.md both missed.
5. **macOS Finder creates "* 2.py" duplicates** — add `"* 2.*"` to `.gitignore` or check for duplicates before committing new file trees.

### Cost Observations

- Model mix: primarily Sonnet 4.6 (session work) + Haiku 4.5 (summaries via claude-mem)
- Build time: ~1 day (single session)
- LLM cost: local LM Studio (gemma-4-e4b), $0 for inference
- Notable: GSD audit workflow (audit-milestone + validate-phase) added ~45 min but caught all 5 requirement gaps before tagging

---

## Cross-Milestone Trends

*Will be updated after v2.0.*

### Process Evolution

| Milestone | Key Process Change |
|-----------|------------------|
| v1.0 | First use of GSD retroactive Nyquist validation; established channels-as-adapters pattern |
