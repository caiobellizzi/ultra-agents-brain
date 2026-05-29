---
phase: 13
slug: knowledge-surface-activation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-23
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pytest.ini` / `pyproject.toml` (existing) |
| **Quick run command** | `.venv/bin/pytest tests/test_instrumented_knowledge.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q -m "not live"` |
| **Live integration command** | `.venv/bin/pytest tests/ -q -m live` (requires `POSTGRES_DSN_KNOWLEDGE` + `POSTGRES_DSN_SESSIONS`) |
| **Estimated runtime (unit only)** | ~30s |
| **Estimated runtime (live)** | ~90s |

---

## Sampling Rate

- **After every task commit:** Run quick command for the file(s) touched.
- **After every plan wave:** Run full non-live suite.
- **Before `/gsd:verify-work`:** Full non-live suite green + live suite green against a local Postgres.
- **Max feedback latency (unit):** 30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 13-01-* | 01 | 1 | KNOW-01 / KNOW-03 / DIAG-BL-05/06 / OBS-01 (write) | T-13-01 stub-fallback hiding misconfig | WARNING log emitted on stub fallback; reindex never silently no-ops on missing DSN | unit | `pytest tests/test_knowledge_reindex.py -q` | ❌ W0 | ⬜ pending |
| 13-02-* | 02 | 2 | KNOW-02 / OBS-01 (access) | T-13-02 wrapper crash kills RAG | search()/asearch() log-and-swallow; agent reply still goes out | unit + live | `pytest tests/test_instrumented_knowledge.py -q` and `pytest tests/test_instrumented_knowledge_live.py -q -m live` | ❌ W0 | ⬜ pending |
| 13-03-* | 03 | 3 | All phase reqs verification gate | — | VERIFICATION.md captures evidence | manual | n/a | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_knowledge_reindex.py` — unit stubs for KNOW-01, KNOW-03, DIAG-BL-06 (stub-fallback WARNING)
- [ ] `tests/test_instrumented_knowledge.py` — unit stubs for KNOW-02 wrapper (mocks PgVector + PostgresDb)
- [ ] `tests/test_instrumented_knowledge_live.py` — `@pytest.mark.live` integration stubs (tmp vault, real Postgres)
- [ ] `tests/conftest.py` — add `tmp_vault` fixture (writes `.md` files under `tmp_path`, sets `VAULT_PATH` env var before imports)

*Existing `tests/conftest.py` already has eval/recorder fixtures from phase 12 — extend, do not replace.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| os.agno.com Knowledge tab renders content rows + access_count column | KNOW-01 + KNOW-02 success criteria 1 + 2 | UI rendering verification requires a logged-in browser session against the deployed VPS | Operator: open https://os.agno.com → Knowledge tab → confirm `ultra-brain-vault` instance exists with non-zero content count; send a Telegram message that triggers RAG; reload tab; confirm `access_count` increased for the hit file. Capture screenshot in 13-03 VERIFICATION.md. |
| `journalctl -u uab-brain.service` shows OBS-01 lines on prod | OBS-01 | journald is per-host operational evidence | After phase 13 deploy: `sudo journalctl -u uab-brain.service --since "1 hour ago" \| grep '"path":"knowledge"'` shows both `"op":"index"` (from reindex) and `"op":"search"` (from at least one chat agent run) lines. |

---

## Validation Sign-Off

- [ ] All 13-01/13-02 tasks have `<automated>` verify commands (13-03 verification closeout is manual by design)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 stubs land before any 13-01 / 13-02 implementation task in their respective waves
- [ ] No `pytest --watch` or `--forever` flags
- [ ] Feedback latency < 30s for unit suite
- [ ] `nyquist_compliant: true` set in frontmatter after planner fills in concrete task IDs

**Approval:** pending
