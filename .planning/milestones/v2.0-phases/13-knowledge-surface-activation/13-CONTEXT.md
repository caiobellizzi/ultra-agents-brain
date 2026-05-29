# Phase 13 CONTEXT — Knowledge Surface Activation

**Gathered:** 2026-05-23
**Status:** Ready for planning
**Source:** Discussion 2026-05-23 + phase 10 audit (RC-knowledge-not-registered, DIAG-BL-05/06) + phase 11/12 patterns.

<domain>
## Phase Boundary

Wire vault `.md` content into `ai.agno_knowledge` + the `vault` PgVector table, so the os.agno.com Knowledge tab renders rows and agentic-RAG hits are observable. Mirror phase 11/12 patterns: pinned `db_id="ultra-brain-main"`, instrumented wrapper for OBS-01, idempotent reindex, log-and-swallow failures.

**Deliverables (code):**
- `agentos/knowledge.py` rewrite — `VaultKnowledge.load()` becomes the no-op file-glob it always was; a new `reindex()` (or module-level `__main__ --reindex`) is the *only* writer. Calls `Knowledge.add_content()` per `.md` file with content-hash dedup.
- `agentos/instrumented_knowledge.py` — `InstrumentedKnowledge` subclass overriding `search()` + OBS-01 structured logging. Wired into `agentos/app.py` so the agents' `search_knowledge=True` path runs through the instrumented instance.
- Loud-warn on stub fallback when `POSTGRES_DSN_KNOWLEDGE` missing or PgVector init fails — keep the empty `Knowledge()` so tests still import, but emit a WARNING structured log line at startup.
- `evals/` and/or `tests/` integration test that runs reindex + an agent RAG query against a seeded vault directory; asserts row counts in `ai.agno_knowledge` and a knowledge-access event surface (depending on what the researcher finds for KNOW-02).
- VERIFICATION.md closeout once the Knowledge tab shows non-zero content rows AND a RAG hit is observable.

**Out of scope:**
- Approvals surface (phase 14)
- worker.monitor polish (phase 15)
- Curator-driven incremental indexing on vault writes — explicitly deferred; CLI reindex is sole writer
- Startup auto-ingest — deferred; reindex stays explicit/operator-triggered
- Replacing embedder or reranker — `all-MiniLM-L6-v2` + SentenceTransformerReranker stay locked from v1.5
- Async background re-embedding for changed files (CLI reindex is synchronous)
- PII / secret redaction inside `eval_data`-style vault content — track as future backlog (parallel to phase 11/12 backlog items)

</domain>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` — Phase 13 success criteria (4 items)
- `.planning/REQUIREMENTS.md` — KNOW-01, KNOW-02, KNOW-03, OBS-01 (knowledge path)
- `.planning/PROJECT.md` — architecture invariants (AgentOS = single source of truth; vault on Markdown; LiteLLM at 127.0.0.1:4000)

### Phase 10 audit findings (locked context)
- `.planning/phases/10-diagnostic-audit/AUDIT.md` §3 Knowledge surface (lines ~165–230) — RC-knowledge-not-registered root cause; `GET /knowledge/content` returns 400 with `Available IDs: []`; `agno_knowledge` DB has zero tables; `VaultKnowledge` silently falls back to empty stub
- `.planning/phases/10-diagnostic-audit/AUDIT.md` Section 1 (memory) — confirms the shared `db_id="ultra-brain-main"` pattern; do not deviate
- `.planning/phases/10-diagnostic-audit/DB-ID-DECISION.md` — Option A locked (shared `db_id="ultra-brain-main"`)
- `.planning/phases/10-diagnostic-audit/BACKLOG.md` DIAG-BL-05 — `agno_knowledge` Postgres DB unmigrated (zero tables in `public` or `ai`); MUST be resolved by phase 13
- `.planning/phases/10-diagnostic-audit/BACKLOG.md` DIAG-BL-06 — silent stub fallback in `VaultKnowledge`; phase 13 D-04 addresses this

### Phase 11 + 12 patterns to mirror
- `.planning/phases/11-memory-surface-activation/11-CONTEXT.md` D-08 (OBS-01 hook point), D-13 (rollback strategy)
- `.planning/phases/12-evals-surface-activation/12-CONTEXT.md` D-04 (log-and-swallow), D-13 (three-plan split), D-15 (OBS-01 log schema)
- `agentos/instrumented_memory.py` — canonical reference implementation for the `Instrumented*` wrapper + structured logger setup (`logging.getLogger("agentos.memory")` pattern; replicate as `"agentos.knowledge"`)

### Existing codebase touch points
- `agentos/knowledge.py` — current `VaultKnowledge` + `make_knowledge()` (PgVector with `table_name="vault"`, hybrid search, SentenceTransformerEmbedder + Reranker). `load()` currently only globs file paths — does not ingest.
- `agentos/app.py:20` — `from agentos.knowledge import VaultKnowledge`
- `agentos/app.py:54-56` — `VaultKnowledge()` instantiation, `vault.load()` call, `kb = vault.knowledge`
- `agentos/app.py:59-84` — `kb` passed to every agent factory and to `AgentOS(knowledge=[kb], …)`. Phase 13 replaces `kb` with the instrumented instance.
- `agentos/agents/{chat,query,research}.py` — all set `search_knowledge=True` and receive `knowledge=kb`. Curator + ingest deliberately do not (they write TO vault, don't read).
- `vault/` (symlink → `~/Documents/second-brain`) — production vault root. Test fixtures must NOT touch this; use a temp dir.

### Agno framework (external — vendor source, do not edit)
- `agno/knowledge/knowledge.py` — `Knowledge` class; the `add_content()` / `search()` API surface to wrap. Researcher must verify exact method names + signatures in agno 2.6.7.
- `agno/vectordb/pgvector/pgvector.py` — `PgVector` constructor; verify whether it auto-creates `vault` table on first write or requires explicit migration.
- `agno/db/postgres/postgres.py:2108` — `PostgresDb.upsert_knowledge_content()` (sync)
- `agno/db/postgres/async_postgres.py:1912` — async variant
- `agno/db/base.py:62` — default table name `agno_knowledge`
- `agno/os/routers/knowledge/router.py` — handler for `/knowledge/content`, `/knowledge/config`, `/knowledge/search`. Researcher must determine what makes `Available IDs` non-empty (likely a stable `id` / `name` on the Knowledge instance).
- https://docs.agno.com/ — knowledge docs (reference only; phase 10 proved doc drift exists — treat as a hint, verify in source)

### AgentOS API
- `GET /knowledge/content` — should return non-empty `data[]` after reindex
- `GET /knowledge/config` — should return `Available IDs` containing the registered knowledge id
- `POST /knowledge/search` — agentic-RAG entry point used by the UI

</canonical_refs>

<code_context>
## Reusable Assets

- **`InstrumentedMemoryManager` (`agentos/instrumented_memory.py`)** — pattern for subclass + structured logger setup + OBS-01 schema. The logger setup boilerplate (force `INFO`, install StreamHandler iff no handlers) is the part to copy verbatim; just rename `agentos.memory` → `agentos.knowledge`.
- **`PostgresDb(id="ultra-brain-main")`** — pinned in phase 11; do not duplicate the literal. Read `db.id` if the recorder needs it.
- **Existing `make_knowledge()` factory** — embedder, reranker, search_type, table_name are correct as locked in v1.5. Keep.
- **`vault/` symlink** — the production vault root is already mounted via the symlink for both Mac dev and VPS prod. Reindex CLI works the same in both environments.

## Integration Points

- `app.py` line `vault = VaultKnowledge(); vault.load(); kb = vault.knowledge` must produce an `InstrumentedKnowledge` instance (or wrap `kb` in `InstrumentedKnowledge(...)` right after).
- The Knowledge instance needs a stable `name` / `id` so AgentOS registers it (`/knowledge/config` Available IDs must include it). Researcher confirms exactly which attribute Agno reads.
- Reindex CLI signature: `python -m agentos.knowledge --reindex` — already wired in current code (returns file count). Extend to actually call `Knowledge.add_content()` per file with hash dedup. Exit code 0 on success, non-zero on any failure.
- Reindex must be runnable both locally (dev DSN) and on VPS (prod DSN) — no environment-specific branches.
- Initial bootstrapping on VPS: operator runs reindex once after phase 13 deploy. This includes: (a) PgVector auto-migration on first connect (if Agno handles it), or (b) explicit migration step if not. Researcher must determine which.
- InstrumentedKnowledge `search()` wrapper:
  - On entry: capture query, start timer
  - Call `super().search(...)`; capture hit count, latency
  - Emit OBS-01 log line (info on success, error on exception)
  - Log-and-swallow exceptions: return empty list rather than crashing the agent run
- For KNOW-02 surface integration: researcher determines whether OBS-01 log + native agno Knowledge stats are enough, OR whether the wrapper must additionally write a row to a knowledge-access table that the UI reads. Decision deferred to research output.

</code_context>

<decisions>
## Implementation Decisions

### Area 1 — Ingest mechanism (KNOW-01)

- **D-01:** CLI reindex (`python -m agentos.knowledge --reindex`) is the **sole writer** to the knowledge surface. AgentOS startup registers the Knowledge instance but does NOT call `add_content()`. Curator vault writes do NOT trigger auto-indexing in phase 13 (deferred).
- **D-01a:** Reindex walks `VAULT_PATH/**/*.md`, computes `(rel_path, sha256(content))` per file, and calls `Knowledge.add_content(...)` for files whose hash differs from the recorded hash (or files with no recorded hash). Files unchanged since last reindex are skipped.
- **D-01b:** Reindex is synchronous and operator-triggered. No cron, no startup hook, no curator hook in phase 13. The CLI prints a per-file `[indexed|skipped|error]` line and a final summary `Indexed N files (M skipped, K errors) in Xs`.
- **D-01c:** Failure-mode: if any single file errors during `add_content()`, the CLI logs the error, increments `error_count`, and continues with the next file. Exit code is 0 if `error_count == 0`, non-zero otherwise. Whole-vault reindex never aborts on a single bad file.

### Area 2 — Reindex idempotency (KNOW-03)

- **D-02:** Idempotency via **content-hash skip-unchanged**. Per file: `sha256(file_contents)` plus `rel_path_from_vault_root` as a composite key. If the hash matches what was previously stored, skip the embedding.
- **D-02a:** Hash storage location is a **research item**. Preferred order:
  1. Store hash in the `ai.agno_knowledge` row's metadata JSONB column (if Agno exposes such a column).
  2. Otherwise, store in the PgVector `vault` table's metadata column.
  3. Otherwise, a tiny side-table `ai.uab_knowledge_hashes(rel_path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, indexed_at BIGINT)` owned by us.
  Researcher must pick option 1/2/3 based on Agno 2.6.7 surface; planner locks it.
- **D-02b:** A file deleted from the vault between reindexes is NOT auto-removed from the knowledge store in phase 13. Track as backlog ("knowledge-gc on vault delete"). Reindex is additive/upsert-only.
- **D-02c:** KNOW-03 verification = run reindex twice on the same vault; assert `count(*)` of `ai.agno_knowledge` rows for the registered knowledge_id is identical before/after the second run.

### Area 3 — RAG access logging (KNOW-02 + OBS-01 access path)

- **D-03:** **`InstrumentedKnowledge`** subclasses `agno.knowledge.knowledge.Knowledge` and overrides `search()` (researcher confirms the exact method name in agno 2.6.7 — likely `search()` or `asearch()` or both). On each call:
  - Capture `query`, `agent_id` (if passable via context — researcher to determine), `db_id`, start time
  - Forward to `super().search(...)`
  - Capture hit count + latency; emit OBS-01 log line
  - On exception: emit `status='error'` log, return empty list (agent gets a "no hits" response rather than a crash)
- **D-03a:** Wrapper is wired in `agentos/app.py` by replacing `kb = vault.knowledge` with `kb = InstrumentedKnowledge(vault.knowledge)` (composition) OR by having `VaultKnowledge` return an instrumented instance directly. Planner picks based on whether Agno's `Knowledge` is easily subclassable vs. composable.
- **D-03b:** **Research item:** does the os.agno.com Knowledge tab show RAG-hit events natively when `Knowledge.search()` is called, or does it require an explicit `db.upsert_knowledge_content()`-style write per hit? Researcher answers this. If a separate write is needed, the wrapper performs it in addition to logging; if not, log + native agno emission is sufficient.
- **D-03c:** Both sync and async search paths must be instrumented if Agno exposes both. Verify with researcher; default assumption is to wrap both.

### Area 4 — Loud-fail on stub fallback (DIAG-BL-06)

- **D-04:** When `POSTGRES_DSN_KNOWLEDGE` is unset or `PgVector(...)` raises during `make_knowledge()`:
  - Log a structured WARNING line at module import / `VaultKnowledge.__init__` time: `{"level":"warning","path":"knowledge","status":"stub-fallback","reason":"<msg>","db_id":null}`
  - Return an empty `Knowledge(name="ultra-brain-vault")` stub so dev/test imports do not break
- **D-04a:** No `UAB_ENV` toggle, no prod-only raise. The WARNING line is loud enough — `journalctl` greppable, and surfaced in any structured log aggregator.
- **D-04b:** Existing tests that don't set `POSTGRES_DSN_KNOWLEDGE` keep passing. A new unit test asserts the WARNING is emitted on stub fallback.

### Area 5 — OBS-01 schema + plan split

- **D-05:** OBS-01 log schema — mirror phase 11/12 base + knowledge-specific extras:
  ```json
  {"ts":"2026-05-23T...","level":"info","path":"knowledge",
   "agent_id":"chat","db_id":"ultra-brain-main",
   "op":"search","query":"<truncated 200ch>","hit_count":3,"latency_ms":48,
   "status":"ok","row_id":null}
  ```
  For write/ingest events from reindex:
  ```json
  {"ts":"...","level":"info","path":"knowledge",
   "agent_id":null,"db_id":"ultra-brain-main",
   "op":"index","rel_path":"daily/2026-05-23.md","sha256":"...",
   "action":"indexed|skipped","content_bytes":1234,"latency_ms":120,
   "status":"ok","row_id":"<knowledge row id if available>"}
  ```
  On failure: `status:"error","error_type":"...","error_msg":"<truncated>"`, `row_id`/`hit_count` null.
- **D-05a:** Single shared log helper. If phase 11/12 has factored one into `agentos/obs.py`, reuse it; otherwise duplicate the inline emitter from `instrumented_memory.py` for now and note the refactor as a future cleanup (do not block phase 13 on a cross-surface helper).

- **D-06:** **Three plans, mirroring phase 11/12**:
  - **13-01** — Knowledge write path: rewrite `agentos/knowledge.py` reindex (hash dedup, per-file add_content, CLI summary), add WARNING on stub fallback, add unit tests covering hash dedup + WARNING. Resolves KNOW-01 + KNOW-03 + DIAG-BL-05/06 + OBS-01 (write path).
  - **13-02** — `InstrumentedKnowledge` wrapper + RAG-hit OBS-01 + integration test (`@pytest.mark.live`) that runs reindex on a tmp vault then issues a query against the chat agent and asserts a row/event surfaces. Resolves KNOW-02 + OBS-01 (access path).
  - **13-03** — Verification closeout: operator runs reindex on the VPS prod vault, opens os.agno.com Knowledge tab, confirms non-zero content count and a RAG hit. VERIFICATION.md captures evidence (psql counts, API responses, screenshots if needed).

### Claude's Discretion

- Module name for the wrapper: `agentos/instrumented_knowledge.py` (suggest — symmetry with `instrumented_memory.py`).
- Whether to factor a shared `agentos/obs.py` log helper in 13-01 or leave it for a later cleanup phase.
- Exact CLI summary line format (`[indexed]`/`[skipped]`/`[error]` prefix, line length).
- Whether to expose reindex via `agentos.knowledge:reindex()` as a Python entry point in addition to `python -m`.
- Subclass vs composition for `InstrumentedKnowledge` — pick what stays cleanest under Agno 2.6.7's `Knowledge` shape (planner decides after research).

</decisions>

<verification_protocol>
## Verification Protocol (phase-end gate)

After all 3 plans (13-01, 13-02, 13-03) ship + deploy:

1. **Reindex sanity (KNOW-01).** On the VPS, `python -m agentos.knowledge --reindex` exits 0 and reports `Indexed N files (0 errors)` where N matches the vault `.md` file count (`find /srv/second-brain -name '*.md' | wc -l`).
2. **Row count check (KNOW-01).** `psql -d agno_knowledge -c "SELECT count(*) FROM ai.vault"` returns N (or matches PgVector chunk-multiplier × N if Agno chunks). `psql -d agno_sessions -c "SELECT count(*) FROM ai.agno_knowledge"` returns ≥1.
3. **API check (KNOW-01).** `GET /knowledge/config` returns `Available IDs` containing the registered knowledge id (no longer `[]`). `GET /knowledge/content?db_id=ultra-brain-main` returns HTTP 200 with non-empty `data[]`.
4. **Idempotency check (KNOW-03).** Re-run reindex. Output shows `Indexed 0 files (N skipped, 0 errors)`. `count(*)` of `ai.vault` unchanged.
5. **RAG-hit check (KNOW-02).** Send a Telegram message containing a query the vault can answer; agent responds citing vault content. Either:
   - `journalctl -u uab-brain.service | grep '"path":"knowledge".*"op":"search"'` shows a log line with hit_count ≥1, OR
   - the os.agno.com Knowledge tab shows a new access-event row within 5s (depends on research outcome for D-03b).
6. **OBS-01 log check.** `journalctl ... | grep '"path":"knowledge"'` shows both `op="index"` (from reindex) and `op="search"` (from the chat RAG call) well-formed lines with all required fields. At least one `status="error"` line from a fault-injection unit test.
7. **UI check.** Operator opens os.agno.com Knowledge tab. Renders the registered knowledge instance and its content rows.

If any of (1)–(7) fails: open a fix-up plan; do not declare phase 13 done.

</verification_protocol>

<threat_model>
## Threat Model

| Threat | Mitigation |
|---|---|
| `Knowledge.add_content()` failure aborts whole reindex | D-01c — per-file try/except; CLI continues, exits non-zero only if any file errored. |
| Reindex re-embeds every file every run (cost) | D-02 — content-hash skip-unchanged. Researcher verifies hash storage strategy works. |
| Silent stub fallback recurs | D-04 — WARNING structured log on every stub-fallback startup. Unit test asserts WARNING. |
| Wrapper crash breaks all agent RAG queries | D-03 — log-and-swallow; return empty list on exception so agent reply still goes out (without RAG context). |
| KNOW-02 UI surface doesn't actually exist in agno 2.6.7 | D-03b — explicit research item; if no native surface exists, wrapper writes the event row directly. |
| Vault file deleted between reindexes leaves orphan knowledge row | Accepted in phase 13; track as backlog (knowledge-gc on vault delete). KNOW-03 only covers re-add idempotency. |
| Hash side-table drifts from Agno's internal row state | If we use option-3 side-table (D-02a), wrap hash write + add_content() in a transaction. Researcher confirms feasibility; otherwise use option-1/2 metadata. |
| PgVector migration not applied on prod (DIAG-BL-05) | 13-01 includes a one-time migration step (or asserts that first `add_content()` triggers Agno's auto-migration). Researcher confirms which. |
| Reindex CLI doesn't run as `uabrain` user on VPS | Operator-triggered via `sudo -u uabrain` in the verification step; document in 13-03 verification doc. |

</threat_model>

<deferred>
## Deferred Ideas (not phase 13)

- **Knowledge GC on vault delete** — when a file disappears from the vault, drop its row from `ai.agno_knowledge` + `vault` PgVector. Phase 13 is additive-only.
- **Curator-driven incremental indexing** — when curator writes a vault file via vault tools, also call `Knowledge.add_content()` for that file (avoids needing a manual reindex). Track for v2.1+.
- **Startup auto-ingest** — call reindex once at AgentOS boot. Decided against in phase 13 (explicit CLI is simpler/testable); revisit if operator finds the manual step painful.
- **Cron-scheduled reindex** — systemd timer runs reindex every N hours. Track once we have evidence the vault edits frequently enough to need it.
- **Embedder swap** — `all-MiniLM-L6-v2` is locked from v1.5; evaluate a stronger embedder only if RAG quality complaints arise.
- **Async background re-embedding** — current reindex is synchronous. Async with a queue is a feature, not phase 13 territory.
- **Knowledge content PII redaction** — same backlog candidate as phase 11/12.
- **Per-agent knowledge scoping** — currently every agent shares one Knowledge instance. Per-agent scopes (chat vs research) would need different knowledge_ids — explicitly deferred.

</deferred>

<rollback>
## Rollback Strategy

- 13-01 is additive — rewrites `agentos/knowledge.py` (rollback = `git revert`; the prior `load()`-only behavior is restored). PgVector rows already written are harmless (still queryable by future versions); a clean-slate rollback drops `ai.vault` table.
- 13-02 is additive — new `agentos/instrumented_knowledge.py` + one-line wrapper application in `app.py`. Rollback = revert the `app.py` line and the agents fall back to plain `Knowledge.search()`. Log lines stop, but data path is unaffected.
- 13-03 is documentation — VERIFICATION.md only. No rollback needed.
- DB rollback (if PgVector schema turns out to be wrong): `DROP TABLE ai.vault CASCADE; DELETE FROM ai.agno_knowledge WHERE name='ultra-brain-vault';` then re-run reindex with corrected schema. No application-level data loss because vault `.md` files are the source of truth.

</rollback>
