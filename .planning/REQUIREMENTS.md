# Requirements — v2.0 AgentOS Surface Activation

**Milestone goal:** Make the AgentOS UI (os.agno.com) show real data on all 4 feature surfaces — evals, memory, knowledge, approvals — by fixing the upstream write pipelines and resolving the shared-`db_id` question. Also clean v1.5 worker.monitor tech debt.

**Scope:** 1-week deep dive. Fixes + worker.monitor polish only. No new ingestion sources.

---

## v2.0 Requirements

### DIAG — Diagnostic Foundation

- [x] **DIAG-01**: Operator can read a written audit doc that traces every write path (memory.add, eval.record, knowledge.ingest, approval.create) from agent run → DB row → AgentOS API response
- [x] **DIAG-02**: Operator can read a decision doc stating whether all 5 agents keep a shared `db_id` or move to per-agent isolation, with Agno-source-backed rationale

### MEM — Memory Surface

- [x] **MEM-01**: After a chat-agent run with memory-worthy content, os.agno.com Memory tab shows ≥1 new entry within 5 seconds
- [x] **MEM-02**: Memory entries are scoped correctly per the db_id decision (DIAG-02) — either per-agent or correctly attributed in shared workspace
- [x] **MEM-03**: `enable_user_memories=True` (or equivalent Agno config) is verified active on agents that should accumulate memory

### EVAL — Evals Surface

- [x] **EVAL-01**: Each agent run records an entry in the AgentOS evals table (run-level, not just the 48-case suite)
- [x] **EVAL-02**: The 48-case eval suite (`evals/`) writes scored results to the AgentOS evals table when run; dashboard shows scores per case
- [x] **EVAL-03**: `EVAL_JUDGE_TIER` swap continues to work after the wire-up

### KNOW — Knowledge Surface

- [x] **KNOW-01**: Vault `.md` content is indexed into the Agno knowledge table (pgvector) and visible via the AgentOS Knowledge tab
- [x] **KNOW-02**: Agentic RAG hits during agent runs are recorded as knowledge-access events visible in the UI
- [x] **KNOW-03**: Re-indexing vault content (vault reindex entry point) updates the knowledge table without duplicates

### APPR — Approvals Surface

- [x] **APPR-01**: HITL approval events created via Telegram inline buttons appear in the AgentOS approvals UI list
- [x] **APPR-02**: Approving/rejecting via Telegram updates the AgentOS approval row state (pending → approved/rejected)
- [x] **APPR-03**: Approvals UI displays the underlying tool call and arguments awaiting approval

### OBS — Observability

- [x] **OBS-01**: Each of the 4 write paths emits a structured log line (level, path, agent_id, db_id, row_id, latency_ms) on success and on failure
- [x] **OBS-02**: A simple ops doc (or `make check-surfaces`) verifies all 4 surfaces have non-zero rows after a smoke-run

### MON — worker.monitor Polish

- [x] **MON-01**: Daily-brief date-mismatch bug (monitor-filed items missed by brief) is fixed and covered by a regression test
- [x] **MON-02**: Vault sync `--delete` flag no longer wipes VPS-generated inbox items (fix verified by test)

---

## Future Requirements (deferred to v2.1+)

- Discord adapter using `channels/` pattern
- WhatsApp adapter using `channels/` pattern
- Webhook mode for Telegram (replace long-poll)
- Vault GitHub remote bidirectional sync (Mac ↔ VPS via Obsidian-Git + cron)
- X/Twitter + LinkedIn ingestion in worker.monitor
- CostLedger verification report after 1 week of v1.5+v2.0 production use

---

## Out of Scope (v2.0)

- **New ingestion sources** (X/Twitter, LinkedIn) — explicitly deferred to v2.1 to keep this milestone focused on remediation.
- **New adapters** (Discord, WhatsApp) — v2.1 work.
- **ultra-workshop** — separate repo, v3.0, gated on 2–4 weeks of production operation.
- **Public HTTPS reverse proxy for AgentOS** — stays on 127.0.0.1.
- **Rewriting Agno internals** — if Agno itself blocks a surface from populating, file an upstream issue; do not fork.

---

## Traceability

| REQ-ID  | Phase                                      |
|---------|--------------------------------------------|
| DIAG-01 | 10 — Diagnostic Audit                       |
| DIAG-02 | 10 — Diagnostic Audit                       |
| MEM-01  | 11 — Memory Surface Activation              |
| MEM-02  | 11 — Memory Surface Activation              |
| MEM-03  | 11 — Memory Surface Activation              |
| EVAL-01 | 12 — Evals Surface Activation               |
| EVAL-02 | 12 — Evals Surface Activation               |
| EVAL-03 | 12 — Evals Surface Activation               |
| KNOW-01 | 13 — Knowledge Surface Activation           |
| KNOW-02 | 13 — Knowledge Surface Activation           |
| KNOW-03 | 13 — Knowledge Surface Activation           |
| APPR-01 | 14 — Approvals Surface Activation           |
| APPR-02 | 14 — Approvals Surface Activation           |
| APPR-03 | 14 — Approvals Surface Activation           |
| OBS-01  | 11, 12, 13, 14 (instrumented per surface)   |
| OBS-02  | 15 — worker.monitor Polish + Final Verify   |
| MON-01  | 15 — worker.monitor Polish + Final Verify   |
| MON-02  | 15 — worker.monitor Polish + Final Verify   |
