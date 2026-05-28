# Code → Graph → Brain: Tooling Benchmark 2025–2026

> Research-only. No code changes. Goal: feed accurate per-repo context into spec generation via AI agents.

---

## 1. Tool Inventory

### codebase-memory-mcp *(your current tool)*
**What it does:** Tree-Sitter AST → SQLite knowledge graph. 14 MCP tools: call-path tracing, impact analysis, hub detection, community detection (Louvain), get_code_snippet, search_graph, trace_path, get_architecture.  
**MCP:** Yes (the reference implementation)  
**Freshness:** XXH3 file watcher → incremental re-index of changed files only (~4x faster than full rebuild). Background polling, no commit hook required.  
**License/Cost:** MIT, free  
**Maturity:** v0.5.5, arXiv paper (March 2026), 1.8K GitHub stars  
**Benchmark:** 83% answer quality vs 92% for file-explorer agents — at 10x fewer tokens and 2.1x fewer tool calls. Sub-ms query latency. Indexes Django (49K nodes) in 6s, Linux kernel (2.1M nodes) in 3 min.  
**Verdict:** Best-in-class token efficiency; the zero-dependency binary is production-ready for solo devs and CI pipelines. 7-point quality gap vs file-exploration is the only real weakness.

---

### GitNexus
**What it does:** Pre-computes dependency graph, call chains, functional clusters (Leiden community detection), and execution flows at index time. 16 MCP tools including blast-radius analysis, 360° symbol view, multi-file rename impact, git-diff change detection. Global registry for multi-repo.  
**MCP:** Yes (16 tools, native)  
**Freshness:** Incremental reindex on changed files. PostToolUse hooks detect stale index after git commit/merge/rebase and prompt agent to reindex.  
**License/Cost:** MIT, open-source  
**Maturity:** 28.9K GitHub stars (April 2026) — category leader by adoption  
**Verdict:** Most production-ready feature set; blast-radius and multi-repo registry make it the best choice for microservice architectures. Heavier than codebase-memory-mcp but more complete.

---

### Nuanced MCP
**What it does:** Call-graph analysis via Python static analysis + LSP, 8 languages including TypeScript. Hyper-focused on execution flow ("what calls what"). JSON-structured output optimized for LLM consumption.  
**MCP:** Yes  
**Freshness:** Re-run on demand; no built-in watch mode  
**License/Cost:** Open-source  
**Maturity:** Actively maintained, smaller community (~hundreds of stars)  
**Verdict:** Best for focused call-flow debugging. Not a full knowledge graph — no impact analysis, no community detection. Good complement, weak standalone.

---

### CodeGraphContext (CGC)
**What it does:** Full Code Property Graph (CPG) in a pluggable graph DB (FalkorDB, KuzuDB, Neo4j). 20 languages. CLI + MCP. Interactive graph visualization.  
**MCP:** Yes  
**Freshness:** Manual re-index; no watch mode documented  
**License/Cost:** Open-source  
**Maturity:** 3K stars, active development  
**Verdict:** Most flexible backend choice; requires running a graph DB (adds ops burden). Best for teams already on Neo4j or wanting interactive visualization.

---

### code-review-graph
**What it does:** Persistent incremental knowledge graph for token-efficient code review. Tree-sitter, SHA-256 file diffs, git post-commit hook. Watch mode re-indexes on every save.  
**MCP:** Yes  
**Freshness:** `watch` command (file save), post-commit hook, `update` for manual incremental sync. Re-indexes 2,900-file project in <2s.  
**License/Cost:** Open-source (PyPI)  
**Maturity:** 13K stars — review-workflow focused  
**Verdict:** Excellent freshness story; narrower scope than codebase-memory-mcp. Shines specifically for PR review workflows in Cursor/Claude Code.

---

### repowise
**What it does:** 5 intelligence layers: dependency graph, git history, auto-generated docs, architectural decisions (ADR), code health scores. 9 MCP tools.  
**MCP:** Yes  
**Freshness:** `watch` mode, post-commit hook (`repowise hook install`), `update` in <30s. Freshness score per documentation page.  
**License/Cost:** Open-source  
**Maturity:** Early-stage  
**Verdict:** Only tool that combines code graph + git history + ADR tracking in one MCP server. Promising for "second brain" use case but pre-1.0.

---

### blarify (blarApp/blarify)
**What it does:** Builds a Neo4j-based graph from a codebase. Supports SCIP (330x faster reference resolution vs LSP). Incremental updates on file add/delete/modify.  
**MCP:** No (outputs to Neo4j; query via Cypher directly)  
**Freshness:** Incremental file-level updates  
**License/Cost:** Open-source  
**Maturity:** Active but niche; no MCP wrapper published  
**Verdict:** Powerful if you're already running Neo4j; no MCP interface means extra integration work. Best as an indexing backend for a custom MCP layer.

---

### Potpie AI
**What it does:** Neo4j-based knowledge graph + AI agent platform. PR-triggered context updates, blast radius, cross-service debugging. Built for 1M+ LOC codebases.  
**MCP:** Via API (not native MCP tools)  
**Freshness:** PR-triggered graph updates; cloud-managed  
**License/Cost:** Commercial SaaS; $2.2M funded  
**Maturity:** Production, enterprise-focused  
**Verdict:** Overkill for a personal second-brain setup. Worth revisiting if the project scales to enterprise multi-repo. Not open-source.

---

### Sourcegraph Cody / SCIP
**What it does:** Compiler-accurate code navigation (go-to-definition, find-references) via SCIP format. Cross-repo, multi-language.  
**MCP:** Cody has MCP integration (experimental)  
**Freshness:** CI-driven SCIP upload; stale between uploads  
**License/Cost:** OSS core; hosted product is commercial  
**Maturity:** Production, battle-tested at scale  
**Verdict:** Gold standard for precision navigation, not for agent-native graph queries. Heavy infrastructure. Not the right fit for a local second-brain workflow.

---

## 2. Embedding/RAG vs. Structural Graph — Tradeoffs

| Approach | Accuracy on multi-hop queries | Token cost | Hallucination risk | Setup |
|---|---|---|---|---|
| Vector RAG only | Weak (topical, not structural) | Medium | High (misses call chains) | Simple |
| LLM-extracted KG | Incomplete (68.8% file coverage) | High (200s+ to build) | Moderate | Complex |
| AST/Tree-sitter graph (deterministic) | Strong | Low (10x vs file-explorer) | Low | Simple |
| SCIP-based (compiler-grade) | Highest | Low | Lowest | Heavy (build tools required) |

**Key finding (arXiv 2601.08773):** Deterministic AST-derived graphs process in seconds vs 200+ seconds for LLM-extracted graphs, with 90.2% file coverage vs 64.1% for LLM-based KG. For spec generation where hallucinated APIs are a failure mode, deterministic structural graphs are the correct choice.

**Hybrid recommendation:** Structural graph for call chains + impact analysis; embeddings for cross-file semantic search when exact graph edges aren't pre-computed. codebase-memory-mcp already does both (SQLite + optional embedding).

---

## 3. Freshness — Mechanisms Ranked

Staleness is the #1 failure mode when an agent generates specs against an outdated graph.

| Tool | Watch mode | Commit hook | Incremental speed | Stale detection |
|---|---|---|---|---|
| code-review-graph | ✅ | ✅ post-commit | <2s / 2,900 files | SHA-256 |
| repowise | ✅ | ✅ post-commit | <30s | Freshness score |
| GitNexus | ✅ | ✅ PostToolUse | Fast | Stale-index prompt |
| codebase-memory-mcp | ✅ (polling) | ❌ no hook | 4x faster than full | XXH3 hash |
| codegraph | ✅ (OS events) | ❌ | Debounced 2s | OS inotify |
| Nuanced | ❌ | ❌ | Manual | None |

**Gap in codebase-memory-mcp:** No git post-commit hook out of the box. The adaptive file watcher catches saves but has latency on rapid commits. A one-line post-commit hook (`codebase-memory-mcp reindex`) would close this gap completely.

---

## 4. Integration with Obsidian / Markdown Brain

The code graph → notes vault bridge is an **emerging but thin** integration layer in 2026:

- **obra/knowledge-graph** (Claude Code plugin): Parses an Obsidian vault into SQLite + vector embeddings, exposes 10 MCP operations (semantic search, path-finding, community detection, subgraph extraction). Treats `[[wiki links]]` as graph edges. This is the cleanest code-side implementation of a notes knowledge graph — but it's for the **notes vault**, not code.
- **repowise**: Generates auto-docs and ADR entries that could be written to a vault directory. Not wired to Obsidian natively but ADR outputs are markdown-compatible.
- **graphify skill** (in your current setup): Converts any input (code, docs, papers) → knowledge graph → HTML + JSON. Can bridge code graph outputs into the vault.
- **No tool currently exposes unified code-graph + docs-graph to a single MCP endpoint.** The closest pattern is: run codebase-memory-mcp + obra/knowledge-graph simultaneously; agents query both via separate MCP tools in the same session.

**Practical bridge today:** Export codebase-memory-mcp architecture summaries → write to `vault/repos/<repo-name>/ARCHITECTURE.md` → obra/knowledge-graph indexes them alongside your notes. The vault becomes the integration layer.

---

## 5. Multi-Repo / Monorepo / Cross-Service

| Capability | codebase-memory-mcp | GitNexus | CGC | Potpie |
|---|---|---|---|---|
| Multi-repo federation | ❌ (per-repo) | ✅ (global registry) | ❌ | ✅ (cloud) |
| Monorepo (single large index) | ✅ (Linux kernel tested) | ✅ | ✅ | ✅ |
| Cross-service call tracing | ❌ | ✅ | Partial | ✅ |
| HTTP route → handler tracing | ❌ | ❌ | ❌ | ❌ |

`code-graph-mcp` (sdsrss) is the **only** tool with HTTP route tracing (`GET /api/users` → route handler → service → DB call in one query). Critical for microservice spec generation.

---

## Recommendation

### Keep codebase-memory-mcp as the primary engine

It's the correct architectural choice: zero-dependency, MIT, 10x token efficiency, deterministic AST graph, sub-ms queries, 66 languages. The arXiv paper validates it as the most rigorously benchmarked tool in this space. Nothing else matches its binary simplicity.

### Augment — do not replace — with three targeted additions:

**1. Add a post-commit git hook** (10-minute fix)
```bash
# .git/hooks/post-commit
codebase-memory-mcp reindex
```
Eliminates the one real freshness gap.

**2. Add `code-graph-mcp` (sdsrss) for HTTP route tracing**
If any repo has REST/GraphQL APIs, this is the only tool that traces from route definition to DB call in a single query. Run it alongside codebase-memory-mcp on API repos.

**3. Add `repowise` for ADR + git history layer**
repowise is the only tool that combines code graph + git history + architectural decisions in one MCP server. Its ADR outputs feed naturally into the Obsidian vault as markdown. Watch mode + post-commit hook keeps it fresh. Early-stage but the feature set directly serves the "second brain" goal.

### For the Obsidian bridge specifically:
Install **obra/knowledge-graph** as a Claude Code plugin pointed at your vault. Write codebase-memory-mcp architecture outputs to `vault/repos/<name>/` on each reindex (a small post-hook script). Now both code structure and notes are queryable graph surfaces in the same agent session.

### Skip for now:
- **GitNexus**: Better feature set than codebase-memory-mcp for multi-repo, but 28.9K stars vs 1.8K means it's newer and less battle-tested as a binary. Revisit in 6 months.
- **Potpie / Sourcegraph**: Cloud-first, enterprise pricing, overkill for personal second-brain.
- **blarify**: Powerful but requires Neo4j infra and no MCP interface.
- **CGC**: Requires graph DB server; adds ops overhead without clear quality gain over codebase-memory-mcp for this use case.

---

## Sources

- [Codebase-Memory arXiv paper (2603.27277)](https://arxiv.org/html/2603.27277v1)
- [Code Intelligence Tools Compared — Ry Walker](https://rywalker.com/research/code-intelligence-tools)
- [GitNexus — MarkTechPost](https://www.marktechpost.com/2026/04/24/meet-gitnexus-an-open-source-mcp-native-knowledge-graph-engine-that-gives-claude-code-and-cursor-full-codebase-structural-awareness/)
- [codebase-memory-mcp GitHub](https://github.com/DeusData/codebase-memory-mcp)
- [Nuanced MCP — nuanced.dev](https://www.nuanced.dev/blog/nuanced-lsp-in-mcp)
- [CodeGraphContext GitHub](https://github.com/CodeGraphContext/CodeGraphContext)
- [code-graph-mcp (sdsrss) GitHub](https://github.com/sdsrss/code-graph-mcp)
- [Potpie AI](https://potpie.ai/)
- [blarify GitHub](https://github.com/blarApp/blarify)
- [Reliable Graph-RAG for Codebases: AST vs LLM (arXiv 2601.08773)](https://arxiv.org/pdf/2601.08773)
- [obra/knowledge-graph GitHub](https://github.com/obra/knowledge-graph)
- [repowise GitHub](https://github.com/repowise-dev/repowise)
- [ChatForest: Code Intelligence MCP Servers Compared](https://chatforest.com/reviews/code-intelligence-codebase-graph-mcp-servers/)
- [LogicLens: Multi-Repo Semantic Graphs (arXiv 2601.10773)](https://arxiv.org/pdf/2601.10773)
- [SCIP — Sourcegraph](https://sourcegraph.com/blog/announcing-scip)
- [code-review-graph PyPI](https://pypi.org/project/code-review-graph/2.2.3.1/)
- [GitNexus README — incremental indexing](https://github.com/abhigyanpatwari/GitNexus/blob/main/README.md)
