---
phase: 15
slug: worker-monitor-polish-final-verification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-27
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | none (uses Makefile) |
| **Quick run command** | `PYTHONPATH=. .venv/bin/pytest tests/unit/ -q` |
| **Full suite command** | `PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_core.py -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `PYTHONPATH=. .venv/bin/pytest tests/unit/ -q`
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| brief-lookback | 15-01 | 1 | MON-01 | pytest | `pytest tests/unit/test_brief.py -q` | pending |
| brief-dedup-lookback | 15-01 | 1 | MON-01 | pytest | `pytest tests/unit/test_brief.py::test_no_duplicates_across_days -q` | pending |
| sync-order | 15-02 | 1 | MON-02 | pytest | `pytest tests/unit/test_sync_vault.py::test_pull_before_push_delete -q` | pending |
| sync-functional | 15-02 | 1 | MON-02 | pytest | `pytest tests/unit/test_sync_vault.py::test_vps_generated_items_survive_delete_sync -q` | pending |
| check-surfaces-script | 15-03 | 2 | OBS-02 | manual smoke | `make check-surfaces` (VPS only) | pending |
| retrospective | 15-03 | 2 | — | manual | file exists + non-empty | pending |

---

## Validation Architecture

### Dimension 1 — Unit test coverage
- `tests/unit/test_brief.py` — MON-01 regression (date lookback, no dedup regressions)
- `tests/unit/test_sync_vault.py` — MON-02 regression (pull-before-push-delete ordering; functional rsync test)

### Dimension 2 — Smoke test
- `make check-surfaces` on VPS: prints non-zero row counts for all 4 surfaces

### Dimension 3 — Documentation
- `RETROSPECTIVE.md` exists and covers v2.0 milestone

### Dimension 8 — Nyquist compliance
Tests must exist for every requirement before the phase can be marked complete.
