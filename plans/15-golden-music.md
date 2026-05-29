# Phase 15 — Security Threat Verification Plan

## Context

Phase 15 ("worker-monitor-polish-final-verification") has no SECURITY.md. No `<threat_model>` blocks exist in any of the three PLAN.md files — `register_authored_at_plan_time = false` → **retroactive-STRIDE mode** is required.

The phase delivered:
- `ultra_brain/brief.py` — `_read_inbox_items` with `lookback_days=2` fix (MON-01)
- `tests/unit/test_brief.py` + `tests/unit/test_sync_vault.py` — regression tests (MON-02)
- `scripts/check_surfaces.py` — PostgreSQL surface row-count smoke checker (OBS-02)
- `Makefile` — `check-surfaces` target
- `RETROSPECTIVE.md` — v2.0 milestone retrospective

A code review (`15-REVIEW.md`) found 2 criticals and 4 warnings. A fix pass (`15-REVIEW-FIX.md`) reports all 6 in-scope findings as **fixed** on 2026-05-28. The current code already reflects those fixes.

---

## Retroactive STRIDE Threat Register

Trust boundaries identified:
- VPS filesystem → Python process (vault Inbox `.md` files)
- Python process → PostgreSQL (psycopg2)
- Python process → LiteLLM proxy (HTTP REST)
- Python process → Telegram API (HTTPS)

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-15-01 | Tampering | `DedupStore.add_new` (monitor.py) | mitigate | `fcntl.flock` exclusive lock on sidecar `.lock` file wraps load+write cycle; eliminates concurrent-write corruption | verify |
| T-15-02 | EoP / Injection | `check_surfaces.py:count_table` | mitigate | `psycopg2.sql.SQL("SELECT COUNT(*) FROM {}").format(psycopg2.sql.Identifier(table_name))` — parameterised identifier, no f-string interpolation | verify |
| T-15-03 | Information Disclosure | `check_surfaces.py` exception handler | accept | `except Exception as exc: print(f"... ERROR: {exc}")` could expose DSN creds if connection string is in exc message. Script is admin-only CLI; no user-facing exposure. | accept |
| T-15-04 | Information Disclosure | `ultra_brain/llm.py` ValueError | accept | CR-02 fix raises `ValueError` with full LiteLLM response context for diagnostics. Dev-only tooling; not user-facing. | accept |
| T-15-05 | DoS | `_read_inbox_items` vault glob | accept | No file-count cap on Inbox glob. Inbox is a controlled system directory populated only by the monitor worker; unbounded growth is an operational concern, not an attack surface. | accept |
| T-15-06 | Spoofing | Vault Inbox file content → LLM prompt | accept | Inbox files are written by the monitor worker under operator control. No external party can inject files. Prompt injection via malicious article titles is in-scope for the LLM layer (LiteLLM), not this phase. | accept |
| T-15-07 | Repudiation | brief generation audit | accept | `append_log` in `brief.py` writes item count + path to `_system/log.md`. No cryptographic receipt — accepted for an internal tool. | accept |

Threats requiring auditor verification: **T-15-01, T-15-02** (mitigate disposition).
Threats accepted: **T-15-03 through T-15-07** (documented above; no mitigation code required).

---

## Execution Steps

### Step 1 — Spawn `gsd-security-auditor` (retroactive-STRIDE mode)

Auditor task: **Verify mitigations for T-15-01 and T-15-02 are present in the implementation.**

Files to read:
- `ultra_brain/monitor.py` (DedupStore — T-15-01)
- `scripts/check_surfaces.py` (count_table — T-15-02)
- `.planning/phases/15-worker-monitor-polish-final-verification/15-REVIEW-FIX.md` (fix evidence)

Auditor config: `asvs_level: L2`, `block_on: CRITICAL`

Expected return: `## SECURED` (both mitigations are present in the current code based on pre-audit read).

### Step 2 — Write `15-SECURITY.md`

Using the SECURITY.md template at `$HOME/.claude/get-shit-done/templates/SECURITY.md`.

Output path: `.planning/phases/15-worker-monitor-polish-final-verification/15-SECURITY.md`

Frontmatter: `threats_open: 0`, `asvs_level: L2`, `status: verified`

Sections:
- Trust Boundaries table (4 boundaries)
- Threat Register (7 threats, T-15-01/02 closed, T-15-03 through T-15-07 accepted)
- Accepted Risks Log (5 entries for T-15-03 through T-15-07)
- Security Audit Trail (today's run)
- Sign-Off: `Approval: verified 2026-05-28`

### Step 3 — Commit

```bash
gsd-sdk query commit "docs(phase-15): add security threat verification"
```

---

## Verification

After execution:
- `.planning/phases/15-worker-monitor-polish-final-verification/15-SECURITY.md` exists
- `threats_open: 0` in frontmatter
- `status: verified` in frontmatter
- T-15-01 shows `closed` with flock evidence
- T-15-02 shows `closed` with psycopg2.sql.Identifier evidence
- T-15-03 through T-15-07 in Accepted Risks Log with rationale

Routing after success:
```
▶ /gsd:validate-phase 15    validate test coverage
▶ /gsd:verify-work 15       run UAT
```
