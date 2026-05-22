# Phase 10: Diagnostic Audit - Context

**Gathered:** 2026-05-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Investigative phase. Trace every AgentOS write path (memory, eval, knowledge, approval) from agent run → DB row → AgentOS API response → os.agno.com UI, and decide the `db_id` architecture (per-agent vs shared workspace).

**Deliverables (read-only / doc-only):**
- `phases/10-diagnostic-audit/AUDIT.md` — 4 write paths, end-to-end evidence per surface
- `phases/10-diagnostic-audit/DB-ID-DECISION.md` — chosen model + Agno-source-backed rationale + downstream consequences
- `phases/10-diagnostic-audit/BACKLOG.md` — tech-debt findings parked for later phases

**Out of scope:** Production code changes, schema migrations, fixes to surfaces. Those are phases 11–15.

</domain>

<decisions>
## Implementation Decisions

### Evidence sources (per write path)
- **D-01:** Use **all four evidence sources** for each of the 4 write paths: (a) static code trace with file:line refs, (b) direct psql query against the VPS production database, (c) AgentOS HTTP API response capture, (d) os.agno.com UI state observation (screenshot or text record).
- **D-02:** Evidence absence is also evidence — when a path yields zero rows / empty API response / empty UI, record that explicitly with the query/request used.
- **D-03:** Production DB reads only. No writes, no schema mutation, no test data injection. Read-only psql against VPS.

### db_id decision methodology
- **D-04:** Read Agno persistence model first — `db.py`, `memory.py`, `knowledge.py`, evals + approvals modules — to understand whether `db_id` partitions storage, controls surface routing, or both.
- **D-05:** Cross-check os.agno.com surface behavior against Agno docs (https://docs.agno.com/) for any `db_id`-scoped queries.
- **D-06:** Run a focused spike **only if** docs/source leave the behavior ambiguous. Spike, if needed, runs locally against a throwaway SQLite DB — not the VPS prod DB.
- **D-07:** `DB-ID-DECISION.md` must include: chosen model, ≥3 Agno-source citations (file:line), explicit consequence list per downstream phase (11–14), and migration implications (do existing v1.5 rows need re-scoping?).

### AUDIT.md structure
- **D-08:** Per-surface **5-section template**:
  1. Expected write path — code references (file:line) from agent run → write call
  2. DB schema + row evidence — table name, schema snippet, row count, sample row (or zero)
  3. AgentOS API response — endpoint + actual JSON response captured from VPS
  4. UI state — what os.agno.com displays for this surface
  5. Root-cause hypothesis — why the surface is empty (config? code path never reached? wrong db_id? schema mismatch?)
- **D-09:** Top-level summary table at the head of AUDIT.md: `surface × write-fn × db-row-count × api-status × ui-shows? × root-cause-tag`. Lets phases 11–14 jump straight to their row.
- **D-10:** All 4 surfaces use the same template — uniform structure for downstream consumption.

### Tech-debt findings handling
- **D-11:** Anything discovered during the audit that is **not** part of the 4 write paths goes into `BACKLOG.md` in the phase 10 directory, with: title, severity (blocking/high/medium/low), suggested phase to fix, one-line repro.
- **D-12:** Known v1.5 carryover items (worker.monitor date-mismatch bug S21808, vault sync `--delete` bug S21815) get pre-populated in BACKLOG.md tagged for phase 15 (MON-01, MON-02).
- **D-13:** Do **not** auto-promote backlog items to REQUIREMENTS.md. Operator reviews BACKLOG.md after audit and decides what gets promoted.

### Claude's Discretion
- Order in which surfaces are audited (memory/eval/knowledge/approval) — pick whichever is easiest to evidence first.
- Exact psql query phrasing for each DB read.
- Whether to inline screenshots in AUDIT.md or link to files in `phases/10-diagnostic-audit/evidence/`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` — Phase 10 success criteria (3 items: AUDIT.md, DB-ID-DECISION.md, operator-readable explanation)
- `.planning/REQUIREMENTS.md` — DIAG-01 (audit doc), DIAG-02 (db_id decision doc)
- `.planning/PROJECT.md` — architecture invariants (AgentOS = single source of truth, LiteLLM at 127.0.0.1:4000)

### Existing codebase maps
- `.planning/codebase/ARCHITECTURE.md` — system architecture overview
- `.planning/codebase/STRUCTURE.md` — module layout
- `.planning/codebase/INTEGRATIONS.md` — external service touch points (Agno, LiteLLM, Telegram)
- `.planning/codebase/CONCERNS.md` — known issues / pain points

### Agno framework (external)
- https://docs.agno.com/ — persistence model, db.py, memory, knowledge, evals, approvals docs
- Agno source (installed package) — `db.py`, `memory.py`, `knowledge.py`, evals + approvals modules; needed for D-04 source citations in DB-ID-DECISION.md

### VPS deployment context
- `deploy/docker-compose.yml` — current container topology (DB host, AgentOS, LiteLLM)
- `agentos/` module — actual deployed entry point (per S21798: VPS runs `agentos` module, not `ultra_brain`)

### Prior incident memory (claude-mem observation IDs)
- S605 — VPS deployment debug session (LiteLLM auth, eval failures, import paths)
- S21808 — daily-brief missed monitor-filed items (date mismatch) → phase 15
- S21815 — vault sync `--delete` deleting VPS-generated inbox items → phase 15
- S603 — original "missing evaluations/memory/knowledge/approvals in AgentOS UI" diagnosis seed

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agentos/` — deployed AgentOS module on VPS; entry point for tracing write paths.
- `.planning/codebase/*.md` — pre-existing codebase maps from v1.5 reduce scout cost.

### Established Patterns
- Existing `ultra_brain/*.py` modules are wrapped as Agno tools, not rewritten — write paths flow through Agno's tool execution, not direct Python calls.
- LiteLLM proxy at `127.0.0.1:4000` mediates LLM calls — audit must consider whether LLM failures (e.g., judge errors during eval) silently swallow writes.
- SqliteDb persistence for HITL gates — approval write path likely flows through Agno's SqliteDb, not Postgres.

### Integration Points
- AgentOS HTTP API (`POST /agents/{id}/runs`) — entry point that should trigger all 4 write paths.
- os.agno.com — external dashboard reading from AgentOS API; not modifiable, only observable.
- VPS PostgreSQL (and/or SQLite per Agno's persistence model) — terminal destination for write paths.

</code_context>

<specifics>
## Specific Ideas

- Pre-populate BACKLOG.md with the two known v1.5 carryover bugs (S21808 daily-brief date, S21815 vault sync delete) tagged for phase 15.
- AUDIT.md should open with a single matrix table — operator should be able to read one row and understand the state of one surface.
- Each "absence-of-evidence" finding records the exact psql query / curl command used, so phase 11–14 planners can re-run verification.

</specifics>

<deferred>
## Deferred Ideas

- Fixing any surface — phases 11–14 own that work.
- Worker.monitor date-mismatch fix and vault-sync `--delete` fix — phase 15.
- Promoting backlog items to formal requirements — operator decides after reading BACKLOG.md.
- Schema migrations driven by the db_id decision — design happens in phases 11–14, not here. Phase 10 only states the decision and its consequences.
- Production DB writes / test data injection during the audit — explicitly excluded; audit is read-only.

</deferred>

---

*Phase: 10-diagnostic-audit*
*Context gathered: 2026-05-22*
