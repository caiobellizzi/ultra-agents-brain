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

## Milestone: v2.0 — AgentOS Surface Activation

**Shipped:** 2026-05-28
**Phases:** 6 (10–15) | **Plans:** 18 | **Commits:** ~50 | **Duration:** 6 days

### What Was Built

- Phase 10 — Read-only diagnostic audit: all 4 write paths traced; `db_id="ultra-brain-main"` shared workspace decision
- Phase 11 — Memory surface: `InstrumentedMemoryManager`; both auto-extraction and agentic-tool paths emit OBS-01 lines; 74 VPS rows
- Phase 12 — Evals surface: `InstrumentedEvalRecorder.wrap()` on all 6 agents; `performance`/`accuracy` row semantics corrected; 155 VPS rows
- Phase 13 — Knowledge surface: vault 3,291 pgvector rows; `InstrumentedKnowledge` wrapping; idempotent sha256-skip reindex
- Phase 14 — Approvals surface: `@approval` stacking bug root-caused and fixed; `ApprovalRecorder`; Telegram resolve bridge; 4 VPS rows
- Phase 15 — worker.monitor polish: daily-brief lookback fix; vault sync `--delete` safety; `check_surfaces.py` psycopg3; retrospective

### What Worked

- **Diagnose first (Phase 10)** — the full read-only audit before writing a single line of code paid off immediately. The `db_id` decision in `DB-ID-DECISION.md` unblocked every subsequent phase without re-investigation.
- **Instrumentation pattern** — wrapping Agno internals without forking proved sustainable. Zero regressions on 48-case eval suite throughout all 6 phases.
- **GSD milestone audit before close** — caught 4 gaps (missing VERIFICATION.md for phases 10/11, psycopg2 bug, stale REQUIREMENTS.md checkboxes) that would have been invisible at tag time. Fixed in <2h.
- **TDD on approval + monitor fixes** — regression tests written before implementation on Phase 14 and 15 fixes. Zero re-debug cycles post-merge.
- **OBS-01 structured logging** — consistent schema across all 4 surfaces made Phase 15 smoke verification trivial.

### What Was Inefficient

- **Phases 10 and 11 had no VERIFICATION.md** — retroactive docs were needed at audit time. Discipline should be enforced at phase close, not milestone close.
- **REQUIREMENTS.md not maintained during phases** — 10 checkboxes were stale at audit time.
- **v2.5/v2.6 phases shipped before v2.0 was formally closed** — created milestone boundary confusion and forced retroactive scoping decisions.
- **check_surfaces.py psycopg2 bug** — import error undetected because the script was never run locally against a live DB. A simple `python -c "import psycopg2"` in CI would catch this.

### Patterns Established

- **Instrumented wrapper pattern** — `Instrumented*` classes wrap Agno internals and emit OBS-01 structured log lines (MemoryManager, knowledge search, eval recorder, approval recorder).
- **`db_id="ultra-brain-main"` invariant** — all agents pin to the same PostgresDb workspace; should become an env-var constant.
- **`make check-surfaces` smoke baseline** — runnable sanity check for all 4 surfaces; candidate for CI pre-deploy gate.
- **Retroactive VERIFICATION.md** — interactive phases can be verified retroactively from SUMMARY.md evidence; same format, written after execution.

### Key Lessons

1. **Write VERIFICATION.md during execution, not after** — even for read-only diagnostic phases.
2. **Propagate requirement checkboxes at each phase close** — mark `[x]` in REQUIREMENTS.md when a plan ships.
3. **Close milestones before starting the next one** — milestone boundary discipline prevents retroactive scoping confusion.
4. **Test imports against your actual dep graph** — `psycopg2` vs `psycopg3` catchable by any CI import check.
5. **The `@approval` stacking bug is non-obvious** — document Agno interaction constraints; don't stack `@approval` with `requires_confirmation=True`.

### Cost Observations

- Model mix: Sonnet 4.6 for coding sessions; Haiku 4.5 for claude-mem summaries; local LM Studio for agent inference
- GSD audit + milestone close: ~2h to fix 4 gaps found by audit
- Notable: retroactive VERIFICATION.md + requirement checkbox propagation added ~30 min but gave a clean audit pass

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Key Process Change |
|-----------|------------------|
| v1.0 | First use of GSD retroactive Nyquist validation; channels-as-adapters pattern |
| v1.5 | 9-phase 4-wave structure for large migrations; eval pre-commit router established |
| v2.0 | Diagnose-first pattern; instrumented wrapper pattern; GSD audit caught all 4 gaps |

### Recurring Issues

| Issue | v1.0 | v1.5 | v2.0 | Resolution |
|-------|------|------|------|------------|
| Missing verification docs | ✗ | ✗ | ✗ | Enforce at phase close, not milestone audit |
| Stale requirement checkboxes | n/a | n/a | ✗ | Add checkpoint to phase transition flow |
| Milestone boundary drift | n/a | n/a | ✗ | Close milestones before starting next |
