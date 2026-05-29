---
phase: 15
slug: worker-monitor-polish-final-verification
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-27
audited: 2026-05-28
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
| brief-lookback | 15-01 | 1 | MON-01 | pytest | `pytest tests/unit/test_brief.py -q` | covered |
| brief-dedup-lookback | 15-01 | 1 | MON-01 | pytest | `pytest tests/unit/test_brief.py::test_no_duplicates_across_days -q` | covered |
| sync-order | 15-02 | 1 | MON-02 | pytest | `pytest tests/unit/test_sync_vault.py::test_pull_before_push_delete -q` | covered |
| sync-functional | 15-02 | 1 | MON-02 | pytest | `pytest tests/unit/test_sync_vault.py::TestSyncDeleteSafety::test_vps_generated_items_survive_delete_sync -q` | covered |
| check-surfaces-script | 15-03 | 2 | OBS-02 | manual smoke | `make check-surfaces` (VPS only) | manual-verified |
| retrospective | 15-03 | 2 | — | manual | file exists + non-empty | manual-verified |

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

---

## Validation Audit 2026-05-28

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Automated tests verified | 4 (9 assertions total — 7 brief + 2 sync) |
| Manual-only items | 2 (check-surfaces VPS, RETROSPECTIVE.md) |

**Verdict:** NYQUIST-COMPLIANT. All requirements (MON-01, MON-02, OBS-02) have automated or explicitly manual-verified coverage. Test suite green: `7 passed` (test_brief.py) + `2 passed` (test_sync_vault.py).
