# Phase 13 Discussion Log

**Date:** 2026-05-23
**Phase:** 13 — Knowledge Surface Activation
**Mode:** default (4 areas selected, single-question turns)

---

## Selected gray areas

All 4 presented gray areas selected: ingest mechanism, idempotency, RAG access logging, loud-fail on stub fallback.

---

## Area 1 — Ingest mechanism & trigger

**Question:** How should vault `.md` content actually get embedded into PgVector?

**Options presented:**
1. CLI reindex only (Recommended)
2. Startup auto-ingest
3. Both — startup + CLI
4. Curator-driven incremental

**User selected:** CLI reindex only.

**Notes:**
- Reindex is sole writer; startup registers Knowledge but doesn't ingest
- Curator vault writes do NOT trigger auto-indexing (deferred to v2.1+)
- Simplest, most predictable, easiest to test path picked

---

## Area 2 — Reindex idempotency strategy

**Question:** How should re-running the reindex avoid creating duplicate rows?

**Options presented:**
1. Content-hash skip-unchanged (Recommended)
2. Upsert by stable id
3. Wipe-and-rebuild
4. Rely on Agno's native dedup

**User selected:** Content-hash skip-unchanged.

**Notes:**
- SHA-256 of file contents + rel_path composite key
- Hash storage location flagged as research item (Agno metadata column vs. PgVector metadata vs. owned side-table)
- File deletion between reindexes deliberately NOT auto-removed in phase 13 (backlog: "knowledge-gc on vault delete")

---

## Area 3 — RAG access logging (KNOW-02)

**Question:** How should agentic-RAG hits get recorded so they appear in the os.agno.com Knowledge tab?

**Options presented:**
1. InstrumentedKnowledge wrapper (Recommended)
2. Post-run agent hook
3. Rely on Agno-native event hooks

**User selected:** InstrumentedKnowledge wrapper.

**Notes:**
- Mirrors Phase 11/12 proven pattern (subclass + override + structured log)
- Open research item: whether OBS-01 logs are sufficient for KNOW-02 UI surface, or whether the wrapper must also `db.upsert_knowledge_content()`-style write a per-hit row
- Log-and-swallow on exception (return empty hits, never crash agent run)

---

## Area 4 — Loud-fail on stub fallback (DIAG-BL-06)

**Question:** What should happen when POSTGRES_DSN_KNOWLEDGE is unset or DB init fails?

**Options presented:**
1. Warn loudly + keep stub (Recommended)
2. Raise on prod, stub on dev
3. Always raise
4. Leave silent

**User selected:** Warn loudly + keep stub.

**Notes:**
- WARNING-level structured log at startup; empty Knowledge() stub kept for test/dev compatibility
- No UAB_ENV toggle — single behavior across envs
- Unit test will assert WARNING is emitted on stub fallback

---

## Wrap-up question

**Question:** Anything else to lock for Phase 13 before I write CONTEXT.md?

**Options presented:**
1. Looks complete — write CONTEXT.md (Recommended)
2. Also discuss plan split
3. Also discuss vault scope

**User selected:** Looks complete — write CONTEXT.md.

**Notes:**
- Plan split mirrors phase 11/12 (3 plans: write, access, verification) — not re-discussed because precedent is clear
- Vault scope (`_system/`, `.trash/` filtering) deferred to planner discretion; can be raised if researcher surfaces it as material

---

## Deferred ideas captured

- Knowledge GC on vault delete (file removal cleanup)
- Curator-driven incremental indexing on vault writes
- Startup auto-ingest
- Cron-scheduled reindex
- Embedder swap from all-MiniLM-L6-v2
- Async background re-embedding
- PII / secret redaction in knowledge content
- Per-agent knowledge scoping

---

## Claude's discretion items (planner picks)

- Module name `agentos/instrumented_knowledge.py` (mirrors `instrumented_memory.py`)
- Factor a shared `agentos/obs.py` log helper now vs. later
- CLI summary line format
- Subclass vs. composition for InstrumentedKnowledge (depends on agno 2.6.7 Knowledge shape)
- Whether to expose a Python `reindex()` entry point alongside `python -m`
