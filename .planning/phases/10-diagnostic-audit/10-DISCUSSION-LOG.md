# Phase 10: Diagnostic Audit - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-22
**Phase:** 10-diagnostic-audit
**Areas discussed:** Evidence sources, db_id decision method, Audit doc structure, Tech-debt findings handling

---

## Evidence sources

| Option | Description | Selected |
|--------|-------------|----------|
| All four | Code trace + VPS prod DB direct psql + AgentOS API response + UI screenshot | ✓ |
| Code + DB only | Trace code path and query the VPS DB; infer from row presence/absence | |
| Code + local repro | Code trace + run agents locally against a fresh DB | |
| Code-only tracing | Static analysis only | |

**User's choice:** All four (recommended).
**Notes:** Strongest evidence accepted despite expense. Audit is read-only against prod DB.

---

## db_id decision method

| Option | Description | Selected |
|--------|-------------|----------|
| Agno docs/source first, spike if ambiguous | Read Agno persistence model; spike only if docs leave behavior ambiguous | ✓ |
| Spike-driven | Run real Agno agent with each model against a test DB | |
| Docs + spike (both) | Read AND spike for highest confidence | |
| Decide from existing v1.5 evidence | Use what we already know — surfaces are empty under shared db_id | |

**User's choice:** Agno docs/source first, spike if ambiguous.
**Notes:** Spike, if needed, runs against throwaway local SQLite — not VPS prod.

---

## Audit doc structure

| Option | Description | Selected |
|--------|-------------|----------|
| 5-section per surface | Write path → DB schema → API → UI → root-cause hypothesis | ✓ |
| 3-section per surface | Code path → DB evidence → root cause | |
| Single narrative | Freeform prose per surface | |
| Table-first + narrative appendix | Matrix table + narrative explanation per row | |

**User's choice:** 5-section per surface (recommended).
**Notes:** Plus top-level summary matrix at head of AUDIT.md for fast scanning by downstream phase planners.

---

## Tech-debt findings handling

| Option | Description | Selected |
|--------|-------------|----------|
| BACKLOG.md in phase 10 dir | Capture with severity + suggested phase | ✓ |
| Inline appendix in AUDIT.md | `## Appendix: Other findings` section | |
| REQUIREMENTS.md updates | Promote findings to new requirements | |
| Don't capture | Out of scope — surface only in conversation | |

**User's choice:** BACKLOG.md in phase 10 dir (recommended).
**Notes:** Pre-populate with S21808 (daily-brief date) and S21815 (vault sync --delete), both tagged phase 15. Operator decides what gets promoted to REQUIREMENTS.md.

---

## Claude's Discretion

- Order in which the 4 surfaces are audited.
- Exact psql query phrasing.
- Whether to inline screenshots or link to `evidence/` files.

## Deferred Ideas

- Fixing surfaces — phases 11–14.
- worker.monitor date-mismatch + vault-sync `--delete` fixes — phase 15.
- Promoting backlog items to REQUIREMENTS.md — operator decision post-audit.
- Schema migrations from db_id decision — phases 11–14 design work.
- Production DB writes / test data injection — explicitly excluded.
