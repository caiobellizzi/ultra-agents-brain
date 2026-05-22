# Plan 10-02 SUMMARY — decision + backlog

**Phase:** 10-diagnostic-audit
**Plan:** 02
**Status:** Complete (operator-driven interactive execution)
**Date:** 2026-05-22

## What this plan produced

- `.planning/phases/10-diagnostic-audit/DB-ID-DECISION.md` — chosen registration model + per-phase consequences + citations table.
- `.planning/phases/10-diagnostic-audit/BACKLOG.md` — 6 pre-populated + 6 audit-surfaced parked items.
- `.planning/phases/10-diagnostic-audit/AUDIT.md` Appendix B — finalized to quote the DB-ID-DECISION TL;DR verbatim and reference BACKLOG.

## 1. Chosen option + one-sentence rationale

**Option A — Pin one shared `BaseDb.id` across all five agents + AgentOS** (`id="ultra-brain-main"` in `agentos/app.py`). Rationale: **none of the four root-cause tags in `AUDIT.md` blames the single-DB architecture**, so the trivial 1-line `id=` pin is the right answer; Option B would force a 5-DSN migration that doesn't resolve any RC tag and would break the dashboard until every caller learned to pass `db_id`.

## 2. Backlog items audit-surfaced beyond the pre-populated six

Six additional items were added in the "Audit-surfaced section" of `BACKLOG.md`:

| ID | Why surfaced |
|---|---|
| DIAG-BL-05 | The `agno_knowledge` Postgres DB has **zero tables** in any schema — strongest single piece of evidence for `RC-knowledge-not-registered`. Not present in `10-RESEARCH.md`. |
| DIAG-BL-06 | `VaultKnowledge` silent fallback to empty stub when DSN check fails — explains why `/knowledge/config` returns `Available IDs: []` despite `AgentOS(knowledge=[kb], …)`. |
| DIAG-BL-07 | AgentOS runs as **systemd** on the VPS, not docker — plan/research assumed docker compose exec. Docs/dev-mode need reconciliation. |
| DIAG-BL-08 | `GET /databases` returns HTTP 404 in agno 2.6.7 — the endpoint isn't exposed. Plan/research instructions need updating. |
| DIAG-BL-09 | AgentOS is **open** on prod — `/memories` etc. return 200 without auth. Possibly intentional (network-layer firewall) but undocumented. |
| DIAG-BL-10 | Agno tables live in the `ai` schema, not `public` — undocumented; caused initial `\d agno_*` queries to "relation does not exist". |

Also, `DIAG-BL-04` (from `10-RESEARCH.md`) was retained but with a **corrected framing**: the project uses `enable_agentic_memory=True`, not the legacy `enable_user_memories=True` the research assumed. Phase 11's flag-flip story is therefore already done; what remains is DIAG-BL-01 (`BaseDb.id` pin).

## 3. Phase-wide secret-scan result

```
grep -rE "password=|secret=|Bearer eyJ|postgresql://[^*]+:[^*]+@" .planning/phases/10-diagnostic-audit/
```

Returns 4 matches, **all of which are self-references** — the secret-scan regex itself appears as a literal string inside `10-01-PLAN.md`, `10-02-PLAN.md`, `10-01-SUMMARY.md` (in the acceptance-criterion text that documents the scan). The discriminating scan (excluding regex-self-references) returns **zero matches**. **No actual secret values leaked into committed files.**

```
$ grep -rE "password=|secret=|Bearer eyJ|postgresql://[^*]+:[^*]+@" .planning/phases/10-diagnostic-audit/ \
    | grep -vE "rtk grep|grep -E.*password|grep -rE.*password|grep -rqE.*password"
(zero output)
```

## 4. Phase 10 status

**Ready-for-close.** All three phase 10 success criteria from `ROADMAP.md` are satisfied:

1. ✅ `AUDIT.md` (DIAG-01) — single readable doc, traces all four write paths end-to-end with code references + row evidence.
2. ✅ `DB-ID-DECISION.md` (DIAG-02) — written decision with ≥3 Agno-source citations and per-phase consequences.
3. ✅ Operator can read both docs and explain why each surface returns the data state it returns (matrix + 4 RC tags + 12 backlog items make this unambiguous).

Phase 11 (memory) is unblocked: the precondition (DIAG-BL-01 / Option A `id=` pin) is a 1-line change. Phase 12 (evals), phase 13 (knowledge), and phase 14 (approvals) have their root-cause tags + suggested remediation paths already specified in `AUDIT.md` and `DB-ID-DECISION.md`.

## What's next for the operator

- Read `DB-ID-DECISION.md` end-to-end and confirm Option A is the right call (or flag a concern — the per-phase consequences section is the most actionable surface to push back on).
- Read `BACKLOG.md` and decide which (if any) of the 12 items should be promoted to `REQUIREMENTS.md` before phase 11 planning starts. Recommended for promotion: `DIAG-BL-01` (the Option A precondition), `DIAG-BL-05` (the unmigrated knowledge DB), `DIAG-BL-09` (the open-auth exposure if not intentional).
- Decide whether to commit phase 10 deliverables now (suggested: yes, as a single commit `docs(10): close diagnostic-audit phase — AUDIT, DB-ID-DECISION, BACKLOG`) and whether to also stage the deletions of phases 01–09's intermediate planning artifacts currently in the working tree (separate from phase 10 — recommend a separate commit).
