---
phase: 12-evals-surface-activation
plan: 03
subsystem: evals
tags: [verification, smoke, vps-deploy, obs-01, tier-swap, deep-copy-fix]

requires:
  - phase: 12-evals-surface-activation
    provides: plan 12-01 + 12-02 — InstrumentedEvalRecorder, evals/conftest hook, OBS-01 schema, sample suite adoption
provides:
  - 12-VERIFICATION.md status=passed (7/7 must-haves)
  - Live-traffic, tier-swap, and OBS-01 failure evidence on the VPS
  - Deep_copy survival fix for the recorder (class-level patch)
affects: [phase 13 readiness — knowledge surface, future async judging worker, dashboard adoption]

tech-stack:
  added: []
  patterns:
    - Class-level instrumentation pattern for Pydantic-Agno objects that survives deep_copy
    - VPS-only verification via SSH + inline Python heredocs (the deployment isn't a git checkout)
    - Suite-recorder fixture adoption is incremental (one test file at a time, additive)

key-files:
  created:
    - .planning/phases/12-evals-surface-activation/12-VERIFICATION.md
    - .planning/phases/12-evals-surface-activation/evidence/eval-live-traffic-2026-05-23.md
    - .planning/phases/12-evals-surface-activation/evidence/eval-suite-private-worker-2026-05-23.md
    - .planning/phases/12-evals-surface-activation/evidence/eval-tier-swap-2026-05-23.md
    - .planning/phases/12-evals-surface-activation/evidence/eval-obs01-failure-2026-05-23.md
  modified:
    - agentos/eval_recorder.py (added patch_classes_for_recording — survives deep_copy)
    - agentos/app.py (uses class-level patch instead of instance wrap loop)
    - evals/test_curator.py (sample suite adoption — calls eval_recorder per parametrized case)

key-decisions:
  - "Deep-copy survival via class-level patch — instance-level wrap was bypassed by Agno's per-request deep_copy()"
  - "Streaming and background paths are pass-through (documented limitation, not a blocker for EVAL-01 acceptance)"
  - "Suite adoption is incremental — test_curator.py first; other five test files adopt the same 5-line pattern in follow-up work"
  - "Dashboard render (V6) deferred to operator visual verification; API + psql is the load-bearing proof"

patterns-established:
  - "When wrapping Pydantic-Agno objects, always check if the framework deep_copies instances — class-level patches survive, instance-level patches do not"
  - "Use evidence files under evidence/ as a flat log of operator-observable behaviour during verification — each file maps to one verification protocol item"

requirements-completed: [EVAL-01, EVAL-02, EVAL-03, OBS-01]

duration: 38min
completed: 2026-05-23
---

# Phase 12-03: Verification + Closeout

**Phase 12 closed with status=passed. Six verification protocol items: five ✓ + one ⚠ deferred (SaaS-side dashboard render). All 7 must-haves landed, EVAL-01/02/03 + OBS-01 proven live on the VPS.**

## What this plan accomplished

Verification of the code shipped by plans 12-01 and 12-02 against the deployed VPS, plus one architectural fix discovered during smoke (`patch_classes_for_recording`).

### The deep_copy discovery

The very first live HTTP smoke (Task 1) revealed that plan 12-01's instance-level `InstrumentedEvalRecorder.wrap(agent)` was silently bypassed in production. Agno's HTTP route (`agno.os.utils.resolve_agent` → `get_agent_by_id(create_fresh=True)`) calls `agent.deep_copy()` for every request, and Pydantic's deep_copy did not preserve the instance-set `arun` closure. Fresh deep_copies had the original `Agent.arun` — no eval row written, no OBS-01 log line emitted.

The fix ships in this plan's evidence trail (commit `fix(12-01): class-level patch survives Agno deep_copy per HTTP request`): a new `patch_classes_for_recording(db)` function replaces `Agent.run / arun / Team.run / arun` at the class level (idempotent). Fresh deep_copy instances inherit the patched class methods, so every HTTP request now flows through the recorder. The 5 unit tests from 12-01 still pass — the existing instance-level `wrap()` is unchanged for direct callers and tests; the new function is used at AgentOS construction time.

### Verification results

| Check | Status |
|-------|--------|
| V1 EVAL-01 (live agent run writes agent_as_judge row) | ✓ run_id `6053a34f-...` returned from curl, found in `ai.agno_eval_runs` |
| V2 OBS-01 success path schema | ✓ journalctl line with all D-15 fields |
| V3 EVAL-02 (suite writes accuracy row) | ✓ tier 1 run: 0→3 row delta, 3 distinct case_ids, judge_model="private-worker" |
| V4 EVAL-03 (tier swap distinct judge_model) | ✓ {private-worker} vs {orchestrator} — disjoint, +3 rows each tier |
| V5 OBS-01 failure path schema | ✓ status=error, error_type=RuntimeError, agent reply preserved |
| V6 dashboard render | ⚠ deferred (operator visual; API + psql is the load-bearing proof) |

## What ships out of plan 12-03

- `12-VERIFICATION.md` with `status: passed`, 7/7 must-haves, 5 ✓ + 1 deferred.
- 4 evidence files under `evidence/` covering the four code-observable verification items + the pre-existing 12-02 live evidence.
- A class-level `patch_classes_for_recording(db)` function added to `agentos/eval_recorder.py` and wired in `agentos/app.py` (replaces the previous instance-loop).
- `evals/test_curator.py::test_curator_field_assertions` extended with the `eval_recorder` + `eval_db` + `judge_model` fixtures — the first concrete suite adoption.

## Threat mitigations confirmed

| Threat | Status |
|--------|--------|
| T-12-08 (operator forgets to redeploy → stale rows) | MITIGATED — explicit redeploy + `systemctl is-active` check + smoke before reading rows |
| T-12-09 (first-tier and second-tier resolve to same model) | DISPROVEN — disjoint judge_model sets across the two tiers |
| T-12-10 (dashboard shows nothing but DB has rows) | ACKNOWLEDGED — V6 explicitly accepts API + psql as the load-bearing proof |
| T-12-11 (verification falsely passed despite failing sub-check) | MITIGATED — every must-have row in the table links to a real evidence file with a checkable assertion |

## Self-Check: PASSED

- ✅ 6 tasks executed and committed atomically (deploy + smoke → tier 1 → tier 2 → failure → VERIFICATION + SUMMARY)
- ✅ 5/6 verification protocol items ✓; 1/6 deferred with documented justification (V6)
- ✅ 7/7 must-haves landed with evidence linked
- ✅ Critical deep_copy bug found, fixed, and re-verified end-to-end during this plan
- ✅ No regressions: all unit tests still pass; pre-commit eval router (`pytest evals/`) collects 48 tests identically

## Handoff to Phase 13

Phase 13 (Knowledge Surface Activation) does not depend on any in-flight phase 12 work. Sample suite adoption for the other 5 agent files (chat, ingest, query, research, supervisor) is documented as a follow-up; can be picked up anytime — the helper function and fixture are already shipped and proven.
