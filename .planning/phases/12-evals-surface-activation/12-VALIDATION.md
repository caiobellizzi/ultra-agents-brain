---
phase: 12
slug: evals-surface-activation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-23
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (already installed; see `pyproject.toml`, `evals/conftest.py`) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` + `evals/conftest.py` |
| **Quick run command** | `pytest tests/unit/test_eval_recorder.py -q` |
| **Full suite command** | `pytest tests/ evals/ -q` |
| **Estimated runtime** | ~25 s unit; ~3 min full (suite hits LiteLLM) |

Wave 0 is empty — pytest framework, `eval_db` fixture, and `judge_model` fixture already exist from phase 7 + phase 11. Phase 12 only adds new test files inside the existing tree.

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/unit/test_eval_recorder.py -q`
- **After every plan wave:** Run the same plus the relevant integration test (`-m live`)
- **Before `/gsd:verify-work`:** `pytest tests/ -q` must be green; `evals/` smoke (`-m "not live"`) must be green
- **Max feedback latency:** 30 s for unit; ~3 min for the suite hop

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | EVAL-01 | T-12-01 | `EvalType.AGENT_AS_JUDGE` enum value used; never the string `'run'` | unit | `pytest tests/unit/test_eval_recorder.py::test_wrap_writes_row_on_success -q` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | EVAL-01 | T-12-02 | wrapper never propagates DB exceptions to agent reply | unit | `pytest tests/unit/test_eval_recorder.py::test_wrap_swallows_db_error -q` | ❌ W0 | ⬜ pending |
| 12-01-03 | 01 | 1 | OBS-01 | T-12-03 | structured log line emitted on success and failure | unit | `pytest tests/unit/test_eval_recorder.py::test_wrap_emits_obs01_schema -q` | ❌ W0 | ⬜ pending |
| 12-01-04 | 01 | 1 | EVAL-01 | — | wrapper applied to all 6 constructed agents/team | unit | `pytest tests/unit/test_eval_recorder.py::test_app_wires_all_six_recorders -q` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 2 | EVAL-02 | T-12-04 | conftest hook writes one accuracy row per case when `eval_db` set | integration (live) | `pytest tests/integration/test_eval_suite_surface.py::test_single_case_writes_row -m live -q` | ❌ W0 | ⬜ pending |
| 12-02-02 | 02 | 2 | EVAL-02 | T-12-05 | pytest retry produces no duplicate-row exception | unit | `pytest tests/unit/test_eval_suite_hook.py::test_hook_swallows_duplicate -q` | ❌ W0 | ⬜ pending |
| 12-02-03 | 02 | 2 | EVAL-02 | — | hook is no-op when `eval_db is None` (offline / pre-commit path) | unit | `pytest tests/unit/test_eval_suite_hook.py::test_hook_skips_when_db_none -q` | ❌ W0 | ⬜ pending |
| 12-03-01 | 03 | 3 | EVAL-03 | — | two-tier smoke captures distinct `model_id` per tier | manual | see Manual-Only Verifications below | ❌ W0 | ⬜ pending |
| 12-03-02 | 03 | 3 | EVAL-01, EVAL-02, EVAL-03, OBS-01 | — | `/eval-runs` HTTP 200 + non-empty `data[]`; dashboard renders both row types | manual | see Manual-Only Verifications below | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

Sampling continuity check: no 3 consecutive tasks lack automated verify. ✓ (Wave 3 is the only manual block; all of Wave 1 & 2 are automated.)

---

## Wave 0 Requirements

Wave 0 is **empty**. All infrastructure exists:

- `pyproject.toml` already declares pytest + asyncio + sqlalchemy + agno deps.
- `evals/conftest.py` already exposes `eval_db`, `judge_model`, `write_baseline`, `update_baseline`.
- `tests/unit/test_instrumented_memory.py` proves the unit-test pattern for an `Instrumented*` module.
- Postgres test target is the same VPS-side DB used by the suite already.

*New test files (`tests/unit/test_eval_recorder.py`, `tests/unit/test_eval_suite_hook.py`, `tests/integration/test_eval_suite_surface.py`) are created as part of the plan tasks above — not as a separate Wave 0 prerequisite.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `EVAL_JUDGE_TIER` swap produces distinct `model_id` rows | EVAL-03 | Operator-driven; needs LiteLLM availability for both tiers and a Postgres connection only the operator can reach | (1) `POSTGRES_DSN_SESSIONS=… EVAL_JUDGE_TIER=private-worker pytest evals/chat/ -q` — capture row count + sample `eval_data.model_id` via `psql -c "SELECT eval_data->>'model_id' FROM ai.agno_eval_runs ORDER BY created_at DESC LIMIT 5"`. (2) Re-run with `EVAL_JUDGE_TIER=orchestrator`. (3) Assert the two captured `model_id` sets are disjoint. Paste evidence into `evidence/eval-tier-swap-2026-05-XX.md`. |
| AgentOS `/eval-runs` API + os.agno.com Evals tab render | EVAL-01, EVAL-02 | Hits live VPS + remote SaaS dashboard | (1) `curl -s ${BRAIN_URL}/eval-runs?db_id=ultra-brain-main \| jq '.data \| length'` returns ≥1. (2) Operator opens https://os.agno.com → Evals tab; confirms rows show with both `agent_as_judge` and `accuracy` eval_types. (3) Screenshot saved to `evidence/eval-dashboard-2026-05-XX.png`. |
| OBS-01 log lines appear in journal | OBS-01 | systemd-journal access on VPS | `journalctl -u uab-brain.service -n 100 \| grep '"path":"eval"' \| jq '.'` shows well-formed JSON with all D-15 fields including at least one `status="error"` line generated by the fault-injection unit test re-run on the VPS (or a deliberate transient DB blip). |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or are listed under Manual-Only Verifications with explicit instructions
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (Wave 3 is the only manual block; isolated)
- [x] Wave 0 covers all MISSING references (no MISSING — infrastructure pre-exists)
- [x] No watch-mode flags
- [x] Feedback latency < 30 s for unit, < 3 min for full
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending — operator review at phase verification
