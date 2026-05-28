# VPS Knowledge Query — Keep pgvector, Fix Gaps

## Context

The user is evaluating whether Agno KnowledgeSurface over pgvector is the right approach for VPS knowledge queries, vs. alternatives like running `qmd` headless. Decision (after research): **keep pgvector** — Postgres is already running for sessions, Agno integrates natively, 41-doc corpus is trivial load, and swapping the store buys nothing.

The research, however, surfaced two genuine gaps worth closing before declaring the architecture sound:

1. **Dual query paths on the VPS that don't share results.** `ultra_brain/query.py:121` (`query_vault`) is purely file-based (`qmd` CLI subprocess → ripgrep fallback). `agentos/knowledge.py:92` (`make_knowledge`) builds a pgvector hybrid+rerank index. Per obs #20013, Agno 2.6.7 agents call `query_vault` directly, **bypassing** the pgvector KnowledgeSurface. That means the index is built but unused by the runtime — a silent waste.
2. **Embedding-model divergence Mac vs VPS.** Local `qmd` uses `embeddinggemma-300M` + Qwen3-Reranker-0.6B. VPS pgvector uses `all-MiniLM-L6-v2` + SentenceTransformerReranker. Same query, different rankings. Not catastrophic at 41 docs, but it makes "did the agent see the same thing I did locally?" a non-trivial question.

This plan closes both gaps while keeping the pgvector + Agno KnowledgeSurface architecture.

## Recommended approach

**Route the agent's retrieval through the pgvector KnowledgeSurface** (the thing we're already building), and **align the VPS embedding model with qmd's** so Mac and VPS rank results similarly.

### Change 1 — Wire agents to KnowledgeSurface instead of `query_vault`

The Agno 2.6.7 quirk (obs #20013) where agents bypass `agentos/tools/vault.py` and hit `ultra_brain.query.query_vault` directly is the root cause. The fix is to make the path the agents *do* take go through pgvector.

Two options, in order of preference:

- **(a)** Replace `query_vault`'s internals so it queries the Agno `Knowledge` instance instead of qmd-CLI/ripgrep. Keep the same function signature (`query_vault(query, *, k, vault_root, ...) -> QueryResult`) so callers don't change. The function becomes a thin wrapper around `knowledge.search(query, num_documents=k)` (or whatever Agno 2.6.7 exposes — verify with Context7 before coding). Fall back to ripgrep only if `POSTGRES_DSN_KNOWLEDGE` is unset.
- **(b)** If Agno 2.6.7 makes (a) awkward, fix the tool-registration so agents actually pick up `agentos/tools/vault.py` and remove the direct `query_vault` shortcut. Then `vault.py` does the KnowledgeSurface call.

Either way, the file-based path becomes the fallback (unset DSN, dev mode, tests), and the pgvector index stops being dead weight.

Files to touch:
- `ultra_brain/query.py` — replace `QmdClient` primary path with a `KnowledgeClient` that calls Agno's `Knowledge.search()`. Keep `RipgrepRetriever` as the fallback when no DSN is configured.
- `agentos/tools/vault.py` — confirm/repair tool registration so agents route here (or drop it if option (a) makes it redundant).
- Any agent definition that hard-codes `from ultra_brain.query import query_vault` — leave the import alone if signature is preserved.

Reuse existing utilities:
- `agentos.knowledge.make_knowledge()` at `agentos/knowledge.py:92` already returns the wired-up `Knowledge` instance. The new client should accept that as a constructor arg, not rebuild it.
- `synthesize_answer()` at `ultra_brain/query.py:75` already handles LiteLLM completion + citation formatting — keep it; only the retrieval step changes.

### Change 2 — Align embedding model with `qmd`

Swap `sentence-transformers/all-MiniLM-L6-v2` for an embedder that matches what `qmd` uses locally (`embeddinggemma-300M`, GGUF). Agno's `SentenceTransformerEmbedder` won't load GGUF directly, so verify via Context7 whether Agno 2.6.7 ships an embedder compatible with the HuggingFace `google/embeddinggemma-300m` weights (non-GGUF form), or whether we wrap it ourselves.

Files to touch:
- `agentos/knowledge.py:92` — change the `embedder=` arg in `make_knowledge`. Bump the pgvector table name (or drop+recreate) since the vector dimension will change; mixing dimensions in one table is fatal.
- `scripts/reindex-vault.sh` — no logic change, but trigger a full reindex after the swap. The SHA-256 skip in `agentos/knowledge.reindex()` (line 184) will NOT detect an embedder change, so we need a one-shot `--force` reindex or a table drop.

Caveat: if Agno 2.6.7 can't load embeddinggemma cleanly, fall back to a closer-match SentenceTransformer (e.g. `BAAI/bge-small-en-v1.5`, 384-dim, generally better than MiniLM-L6 on retrieval benchmarks) instead of forcing the qmd model. Mac↔VPS parity becomes "close enough" rather than identical.

### Change 3 — Document the architecture decision

Add a short ADR (`.planning/adr/NNN-vps-knowledge-query.md` or wherever ADRs live in this repo — check existing pattern) recording: pgvector chosen, why, what was considered (qmd headless, Meilisearch, BM25-only), and the two gaps closed above. This stops the next person (or future-you) from re-litigating it.

## Verification

End-to-end, against the VPS:

1. **Index parity** — run `python -m agentos.knowledge --reindex --force` (or equivalent), confirm row count in `ai.vault` matches `find /srv/second-brain -name '*.md' | wc -l`.
2. **Retrieval path** — query the AgentOS endpoint with a known prompt (the SC5 verification query from phase 18 is a good one: something that should hit `repos/ultra-agents-brain.md`). Confirm in logs that pgvector was hit (look for `_emit` instrumentation from `agentos/knowledge.py`), NOT the ripgrep fallback.
3. **Mac↔VPS comparison** — run the same query through `qmd search` locally and through the VPS agent. Top-3 results should overlap substantially. They won't be identical (different rerankers), but the *files* returned should match for unambiguous queries.
4. **Fallback still works** — unset `POSTGRES_DSN_KNOWLEDGE` in a dev shell, run the agent, confirm ripgrep path activates and returns results.
5. **No dead code** — `grep -rn 'QmdClient\|RipgrepRetriever' ultra_brain/ agentos/` should show the ripgrep retriever only on the fallback path; `QmdClient` should be removable.

## Out of scope

- Switching off pgvector (decided against).
- Chunking strategy changes — Agno's internal chunking is fine at 41 docs. Revisit when the vault crosses ~500 files.
- Running `qmd` on the VPS at all — the local MCP stays, but the VPS does not get qmd installed.
- Rsync / git-sync / reindex trigger plumbing — already verified working in phase 18.
