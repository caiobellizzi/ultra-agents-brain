# Roadmap — ultra-agents-brain

## Milestones

- ✅ **v1.0 — Knowledge Layer on Agno** — shipped 2026-05-19 ([archive](milestones/v1.0-ROADMAP.md))
- ✅ **v1.5 — Agno Full Reconfiguration** — shipped 2026-05-22, 9 phases, 15 plans ([archive](milestones/v1.5-ROADMAP.md))
- 🚧 **v2.0 — AgentOS Surface Activation** — in planning (6 phases, 16 requirements)
- 📋 **v2.1 — Channels** — planned (Discord + WhatsApp + Telegram webhook + vault GitHub sync)
- 📋 **v3.0 — ultra-workshop** — planned (separate repo, after 2–4 weeks of v1.5+v2.0 production operation)

---

## Current milestone — v2.0 AgentOS Surface Activation

**Goal:** Make os.agno.com show real data on all 4 feature surfaces (evals, memory, knowledge, approvals) by fixing the upstream write pipelines. Resolve the shared-`db_id` question. Clean v1.5 worker.monitor tech debt.

**Strategy:** Diagnose first → fix each surface in dependency order → final verification. Phase numbering continues from v1.5.

| #  | Phase                                  | Goal                                                                                       | Requirements                                  | Criteria |
|----|----------------------------------------|--------------------------------------------------------------------------------------------|-----------------------------------------------|----------|
| 10 | Diagnostic Audit                       | Trace every write path; decide db_id model                                                 | DIAG-01, DIAG-02                              | 3        |
| 11 | Memory Surface Activation              | Memory tab in os.agno.com shows entries after agent runs                                   | MEM-01, MEM-02, MEM-03, OBS-01 (memory path)  | 4        |
| 12 | Evals Surface Activation               | 3/3 | Complete   | 2026-05-23 |
| 13 | Knowledge Surface Activation           | 2/3 | In Progress|  |
| 14 | Approvals Surface Activation           | Telegram HITL events surface in Approvals UI with state updates                            | APPR-01, APPR-02, APPR-03, OBS-01 (appr path) | 4        |
| 15 | worker.monitor Polish + Final Verify   | Daily-brief date bug fixed; vault-sync delete bug fixed; surface-smoke verification doc    | MON-01, MON-02, OBS-02                        | 4        |

**6 phases · 16 requirements · 100% coverage**

---

### Phase 10: Diagnostic Audit

**Goal:** Produce a written audit doc tracing every write path from agent run → DB row → AgentOS API response, and a decision doc on the `db_id` architecture (per-agent vs. shared workspace).

**Requirements:** DIAG-01, DIAG-02

**Success criteria:**
1. `phases/10-diagnostic-audit/AUDIT.md` exists and traces all 4 write paths (memory, eval, knowledge, approval) end-to-end with code references and DB-row evidence (or absence-of-evidence).
2. `phases/10-diagnostic-audit/DB-ID-DECISION.md` states the chosen model (per-agent or shared) with Agno-source-backed rationale and explicit consequences for downstream phases.
3. Operator can read both docs and explain why each surface currently returns empty data.

---

### Phase 11: Memory Surface Activation — ✅ shipped 2026-05-23 (3 plans, all requirements satisfied)

**Goal:** Wire memory extraction so chat-agent runs persist memory rows that os.agno.com Memory tab displays.

**Requirements:** MEM-01 ✅, MEM-02 ✅, MEM-03 ✅, OBS-01 (memory path) ✅ — both auto-extraction (`create_user_memories`) and the agentic-memory-tool path (`update_memory_task`) emit structured log lines. Closed by plan 11-03 (2026-05-23).

**Success criteria:**
1. Run a chat-agent conversation containing memory-worthy content; within 5 seconds, the Memory tab in os.agno.com shows ≥1 new entry.
2. Memory entries are scoped per the Phase 10 db_id decision (verified by querying the DB directly).
3. `enable_user_memories=True` (or equivalent) is asserted active for chat (and other memory-enabled agents) by an integration test.
4. Each memory.add call emits a structured log line with `path=memory`, `agent_id`, `db_id`, `row_id`, `latency_ms`, status.

---

### Phase 12: Evals Surface Activation

**Goal:** Wire eval recording so per-run scores and the 48-case suite show up in the Evals dashboard.

**Requirements:** EVAL-01, EVAL-02, EVAL-03, OBS-01 (eval path)

**Success criteria:**
1. Each agent run creates a row in the AgentOS evals table (visible via API and dashboard).
2. Running the 48-case eval suite produces per-case scored entries in the evals table; dashboard shows them.
3. Swapping `EVAL_JUDGE_TIER` continues to work post-wire-up (verified by a smoke run with two tiers).
4. Eval write path emits a structured log line on success and failure.

---

### Phase 13: Knowledge Surface Activation ✅ COMPLETE (2026-05-23)

**Goal:** Ensure vault content is indexed into the knowledge table and agentic RAG hits are recorded.

**Requirements:** KNOW-01, KNOW-02, KNOW-03, OBS-01 (knowledge path) — all verified.

**Success criteria:**
1. ✅ Vault `.md` content appears in the AgentOS Knowledge tab; row counts in pgvector match expected document count. *(125 files → 125 ai.agno_knowledge rows, 136 ai.vault chunks)*
2. ✅ An agentic RAG query during an agent run records a knowledge-access event visible in the UI. *(10 hits bumped access_count 0→1)*
3. ✅ Running the vault reindex entry point twice produces no duplicate rows. *(BEFORE=136, AFTER=136; sha256-skip working)*
4. ✅ Knowledge write/access paths emit structured log lines. *(125 OBS-01 index lines + OBS-01 search lines on every search call)*

See `phases/13-knowledge-surface-activation/13-VERIFICATION.md` for full evidence.

---

### Phase 14: Approvals Surface Activation

**Goal:** Surface HITL approval events from Telegram in the AgentOS approvals UI, with state updates flowing back.

**Requirements:** APPR-01, APPR-02, APPR-03, OBS-01 (approval path)

**Success criteria:**
1. A tool call gated by `trust_gate` creates an approval row visible in the AgentOS approvals list.
2. Approving/rejecting via Telegram inline button flips the AgentOS approval row state (pending → approved/rejected) within 2 seconds.
3. The approval row in the UI displays the tool name and arguments awaiting approval.
4. Approval write path emits a structured log line on creation and on state change.

---

### Phase 15: worker.monitor Polish + Final Verification

**Goal:** Fix v1.5 worker.monitor tech debt and deliver a smoke-verification doc that proves all 4 surfaces remain populated.

**Requirements:** MON-01, MON-02, OBS-02

**Success criteria:**
1. Daily-brief no longer misses monitor-filed items; a regression test reproduces the original date-mismatch bug and now passes.
2. Vault sync `--delete` flag preserves VPS-generated inbox items; a regression test asserts this.
3. `make check-surfaces` (or equivalent doc + script) runs a smoke flow and prints non-zero row counts for memory, evals, knowledge, and approvals tables.
4. v2.0 retrospective added to RETROSPECTIVE.md.

---

## Future milestones (preview)

### 📋 v2.1 — Channels

Discord adapter, WhatsApp adapter, Telegram webhook mode, vault GitHub remote bidirectional sync, X/Twitter + LinkedIn ingestion in worker.monitor.

### 📋 v3.0 — ultra-workshop

Separate repo. Agno orchestrator + OpenHands coder sandbox. Reads from Brain via HTTP. Begins only after v2.0 has been running daily for 2–4 weeks.
