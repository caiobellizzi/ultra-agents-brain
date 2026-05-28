# Research Brief: State of the Art for LLM Code Indexing (2025–2026)
## Goal: "Second brain for all my repos" — queryable from Telegram

---

## 1. The Core Debate: Agentic Grep vs. Pre-Built Index

### The Dominant 2025–2026 Trend: Agentic Search Has Won for Single Sessions

The industry moved decisively toward **agentic search** over RAG/embeddings for in-session code understanding. Key evidence:

- **Anthropic (Claude Code)**: Explicitly tried local vector DBs and RAG, abandoned them. Boris Cherny on Latent Space (May 2025): *"We tried early versions that used RAG… Eventually landed on agentic search. It outperformed everything. By a lot."* Claude Code uses a three-tool hierarchy: **Glob** (file path matching, near-zero tokens) → **Grep** (content regex search) → **Read** (full file load), plus an isolated **Explore sub-agent** (Haiku model with its own context window) for deep dives.

- **Why agentic wins for code**: Code identifiers are exact — a function name either exists or it doesn't. Grep outperforms fuzzy semantic retrieval for symbol lookup. The agent can do multi-hop reasoning (follow an import, then its caller, then its caller's caller) in a way a one-shot RAG retrieval cannot.

- **Cursor**: Uses embeddings (stored in Turbopuffer vector DB), claims +12.5% accuracy over keyword search for semantic queries. BUT: Cursor hired Claude Code's leads (Boris Cherny, Cat Wu) in July 2025, and there's credible signal they are evaluating ditching vector search for lexical/agentic approaches.

- **Aider**: Neither pure grep nor embeddings — uses a **repo-map** approach (tree-sitter AST parsing → NetworkX graph with PageRank ranking → token-budget-constrained skeleton). Default: 1,024-token repo-map covering the most structurally central symbols, SQLite-cached. Processes 15B tokens/week. This is the best-known "lightweight structural index."

**Bottom line for sessions**: Agentic grep + Read is the winner for interactive, single-repo work. Pre-built semantic indexes add ~12% accuracy but require infrastructure, have staleness issues, and break the "zero setup" promise.

---

## 2. Where Pre-Built Indexes Still Win: The "Telegram from anywhere" Problem

**Here's the critical nuance that changes the calculus for a personal multi-repo second brain:**

Agentic grep requires a live filesystem access and a large context window per query. When you fire a Telegram message asking "what does the `InboxSweep` class do in ultra-agents-brain?", you need:

1. The repo to be accessible (cloned locally or cloneable on-demand)
2. An agent that can run grep/read on that repo in real time
3. Tolerable latency (agentic exploration = many LLM calls = slow + expensive per query)

For **cross-repo queries** ("which of my repos uses Celery?", "what's the data model pattern I use everywhere?"), pure agentic grep would require exploring all repos in parallel — potentially dozens of LLM calls and 60–120 seconds per query.

**Tools that DO maintain pre-built indexes and why:**

| Tool | Index type | Freshness strategy | Cross-repo? |
|---|---|---|---|
| **Sourcegraph / SCIP** | Full symbol graph (precise go-to-def, find-refs) | Incremental on commit push | Yes — cross-repo navigation |
| **Greptile** | AST graph + recursive docstrings + embeddings | On PR/push events | Yes (multi-repo SaaS) |
| **Sourcebot** | Regex search index + code nav | On push, self-hosted | Yes |
| **Cursor** | Embeddings (Turbopuffer) | Merkle tree diff every 10 min | Single workspace |
| **Aider** | Tree-sitter repo-map (SQLite cache) | mtime-based, per-session | Single repo per session |

**Sourcegraph SCIP** is the only production-grade system doing truly incremental indexing (file-level delta on git push, not full re-index). For large repos, full re-index takes 1–2 hours; incremental takes minutes. The SCIP format uses human-readable symbol IDs (not opaque integers like LSIF), which is what enables partial updates.

---

## 3. Granularity Spectrum

From lightest to heaviest:

### a) Docs/ADR/README layer only
- Tools: `llms.txt` (proposed web standard, analogous `LLMS.md` for repos), Repomix, manual `CONTEXT.md` per repo
- What you get: Architecture intent, decisions, API surface. Zero code details.
- Freshness: Manual. Staleness risk is real but managed by discipline.
- Best for: "What is this repo about? What are the key decisions?" — not "which function handles auth?"

### b) Repo-map / symbol skeleton (Aider-style)
- Tools: Aider's repo-map, RepoMapper MCP, tree-sitter based skeletons
- What you get: All function/class names across the repo, with PageRank-weighted importance. ~1K–4K tokens per repo.
- Freshness: Rebuilt per-session from mtime cache. ~seconds for changed files.
- Best for: "Give me structural context before diving in." Fits 5–10 repos in a single prompt.

### c) Semantic embedding index (Cursor/Greptile style)
- Tools: Cursor, Greptile (SaaS), custom pgvector/Chroma setup
- What you get: Concept-level search ("find all places that handle auth") even when naming is inconsistent
- Freshness: Cursor checks every 10 min via Merkle tree diff; Greptile hooks into push events
- Best for: Large codebases (100K+ LOC) with inconsistent naming, legacy systems

### d) Full SCIP symbol graph (Sourcegraph style)
- Tools: Sourcegraph + SCIP indexers per language
- What you get: Precise go-to-definition, find-all-references, cross-repo call graphs — IDE quality
- Freshness: Incremental on push
- Cost: High infrastructure overhead (Sourcegraph is a full service), heavy per-language indexers
- Best for: Enterprise teams, not personal multi-repo second brain

---

## 4. The Docs Layer Alternative: `llms.txt`, `LLMS.md`, Repomix

### `llms.txt` / `LLMS.md`
- `llms.txt`: Proposed 2024 by Jeremy Howard (Answer.AI). A Markdown file at repo/domain root pointing LLMs to key content with one-line descriptions. Anthropic maintains one for their own docs.
- `LLMS.md`: The repo-level analog (proposed by `llmspec/llms-spec`). Same idea as `README.md` but structured for LLM agents — architecture, key decisions, entry points, important modules.
- **Honest adoption status**: Not yet used by major LLM crawlers for inference. No validation standard. But near-zero cost and forces you to write a clean inventory. IDE agents (Cursor, Continue, Cline) do read it.

### Repomix
- CLI tool (npm: `repomix`) that packs an entire repo into a single AI-friendly file (Markdown/XML/JSON/plain text)
- Respects `.gitignore`, token-counts each file, optional `--compress` flag (tree-sitter-based compression)
- Use case: One-off "dump this repo to ask a question" — not a persistent index
- As a pre-built artifact: Could run `repomix` on each repo post-commit → store the output in a vector DB or directly in a knowledge base
- Nominated for JSNation Open Source Awards 2025

### The Karpathy LLM Wiki Pattern (April 2026)
- Karpathy's own approach: `raw/` inbox → LLM compiles to `wiki/` articles → `index.md` kept small enough to fit in context (~100 articles, 400K words)
- Key insight: **if the index fits in a context window, you don't need retrieval at all**
- Applied to code repos: a per-repo `LLMS.md` or architecture summary + a cross-repo index markdown = queryable from anywhere with zero infrastructure

---

## 5. Recommendation for a Personal Multi-Repo Second Brain

### The Problem with Full SCIP on Every Commit
- Requires running language-specific SCIP indexers (scip-typescript, scip-python, scip-java…) in CI per push
- Requires hosting a Sourcegraph instance or a custom graph store
- Index size: ~100MB+ per medium repo
- **Overkill** for a personal system queried via Telegram a few times per day

### The Problem with Pure Agentic Grep
- Works great when Claude Code is running locally against the filesystem
- Breaks for Telegram-style queries: the agent needs the repos checked out, latency is 30–120 seconds per query (many LLM calls), cross-repo queries are multiplicatively expensive
- Not "from anywhere" — requires a local machine or a persistent cloud VM running the agent

### Recommended Architecture: Two-Tier Docs + On-Demand Agentic

**Tier 1 — Curated docs layer (maintained per commit, cheap)**
- Each repo maintains a `LLMS.md` (or `CONTEXT.md`) with: one-paragraph purpose, key modules, important patterns, recent architectural decisions
- A cross-repo `index.md` (the "second brain index") listing all repos + one-line summaries + links to their `LLMS.md`
- **Tool**: This is essentially what your existing `PROJECT.md` / `.planning/` structure already does — make it LLM-queryable by keeping a flat index
- **Freshness**: Updated when decisions change (not on every commit). ADRs + a `docs/` layer.

**Tier 2 — Repo-map skeleton index (rebuilt on demand or nightly, lightweight)**
- Run Aider's repo-map (or a tree-sitter equivalent) per repo nightly → store as a small Markdown file per repo
- Total size for 10 medium repos: ~10K–40K tokens — fits in a single Claude context window
- Cross-repo skeleton queries ("which repos have a `monitor.py` pattern?") become trivial

**Tier 3 — On-demand agentic grep (for deep dive questions)**
- When a Telegram query needs code-level detail, spawn a Claude agent against the specific repo (via SSH or a cloud VM with repos checked out)
- Use the Tier 1 docs to route ("this question is about ultra-agents-brain") before spinning up the grep agent
- This is exactly what Sourcebot does: reasoning model uses search/nav tools to answer, anchored by a pre-built search index

**What to skip**: Full SCIP/Sourcegraph graph, per-commit re-embedding pipelines, pgvector infra — all engineering overhead that exceeds the value for a personal system.

### Concrete Implementation Path
1. Add `LLMS.md` to each repo (one-time, ~30 min per repo) — architecture, entry points, key patterns
2. Maintain a `~/repos/index.md` listing all repos + summaries
3. Nightly cron: run `repomix --compress` on each repo → store compressed skeleton in `~/repos/<name>-map.md`
4. Telegram bot: on query, load index.md + relevant repo maps (based on topic detection) + spawn an agentic tool-call session for deep questions
5. Optional later: add Chroma/pgvector embedding of the repo maps for semantic routing (only worth it at 20+ repos)

---

## Sources

- [Why Coding Agents Still Use grep as Their Search Backbone (yage.ai)](https://yage.ai/share/why-coding-agents-still-use-grep-en-20260327.html)
- [Claude Code Doesn't Index Your Codebase — Vadim's blog](https://vadim.blog/claude-code-no-indexing)
- [Why Cursor, Claude Code, and Devin Use grep, Not Vectors — MindStudio](https://www.mindstudio.ai/blog/is-rag-dead-what-ai-agents-use-instead)
- [Cursor Semantic Search: 12.5% Better Accuracy — DigitalApplied](https://www.digitalapplied.com/blog/cursor-semantic-search-coding-ai-guide)
- [How Cursor Actually Indexes Your Codebase — Towards Data Science](https://towardsdatascience.com/how-cursor-actually-indexes-your-codebase/)
- [Aider: Building a better repo-map with tree-sitter](https://aider.chat/2023/10/22/repomap.html)
- [SCIP — a better code indexing format than LSIF — Sourcegraph](https://sourcegraph.com/blog/announcing-scip)
- [Precise code navigation — Sourcegraph docs](https://docs.sourcegraph.com/code_intelligence/explanations/precise_code_intelligence)
- [Codebases are uniquely hard to search semantically — Greptile](https://www.greptile.com/blog/semantic-codebase-search)
- [Greptile v3, agentic code review](https://www.greptile.com/blog/greptile-v3-agentic-code-review)
- [Sourcebot — self-hosted code understanding](https://www.sourcebot.dev/)
- [Sourcebot GitHub](https://github.com/sourcebot-dev/sourcebot)
- [llms.txt Explained (May 2026) — Codersera](https://codersera.com/blog/llms-txt-complete-guide-2026/)
- [LLMS.md — proposed open standard for repos](https://github.com/llmspec/llms-spec)
- [Repomix — GitHub](https://github.com/yamadashy/repomix)
- [Karpathy's LLM Knowledge Base — Codersera](https://codersera.com/blog/karpathy-llm-knowledge-base-second-brain/)
- [knowledge-nexus: GraphRAG for Second Brain](https://github.com/Jallermax/knowledge-nexus)
- [Agentic Search: How Coding Agents Find the Right Code — Morph](https://www.morphllm.com/agentic-search)
- [Milvus Blog: Against Grep-Only Retrieval](https://milvus.io/blog/why-im-against-claude-codes-grep-only-retrieval-it-just-burns-too-many-tokens.md)
