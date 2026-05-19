# ultra-agents-brain — Personal Multi-Agent Orchestration with Second Brain

**Status:** Plan (awaiting approval via ExitPlanMode)
**Date:** 2026-05-18
**Plan owner:** Caio Bellizzi
**Working directory:** `~/Documents/Projects/ultra-agents-brain/`

---

## Context

Build a **personal AI assistant** accessible via Telegram chat that:
1. Acts as an **always-on orchestrator** running on a Hostinger VPS — receives messages, plans, dispatches ephemeral worker subagents for research, integrates results into a persistent second brain
2. Maintains a **second brain** combining Tiago Forte's PARA structure (actionability) with Andrej Karpathy's LLM-maintained wiki operations (Ingest/Query/Lint)
3. Is **model-agnostic** via LiteLLM proxy — swap Claude/GPT/Ollama/Groq via config, no code changes
4. **Wakes you up to finished briefings** for the common case (async research delivery), gates medium-risk actions for approval, hard-caps cost at $20/day

The system fills a gap in Caio's existing ecosystem: he has Claude Code + claude-mem + claudeclaw for *interactive* work, but no *autonomous* agent layer that can chew through research for hours while he's away, accessible from his phone via Telegram, with results landing in an Obsidian-readable vault.

After comprehensive research (3 sub-agents, 12 GitHub repos verified, primary sources for Karpathy + Forte + Miessler + Zettelkasten + Evergreen Notes + HTML ingestion landscape), the architecture below was chosen via grilling-driven decision tree. Every decision has a documented "why" and rejected alternatives.

---

## Architecture — locked decisions

| # | Decision | Choice | Rejected alternatives |
|---|----------|--------|----------------------|
| 1 | Primary value | Async research delivery (planner-executor, fire-and-forget) | Conversational companion / Task delegation / Knowledge capture only |
| 2 | Chat interface | Telegram (built-in via Hermes Agent gateway) | Discord, Slack, iMessage, custom PWA |
| 3 | Agent topology | 1 orchestrator + ephemeral workers (single coherent second brain) | Strict single-agent (no fan-out), Multi-agent with persistent roles (CrewAI-style) |
| 4 | Runtime | Hostinger VPS (always-on, public Telegram webhook) + git-synced Markdown to Mac/Obsidian | Local Mac only, hybrid VPS+Mac, Coolify PaaS |
| 5 | Platform | Hermes Agent (NousResearch, 154k★, MIT) — pin a specific release | Build from scratch with LiteLLM, Pydantic AI, LangGraph, AionUi meta-shell, OpenHuman (GPL-3.0), PAI (Claude Code coupled) |
| 6 | Model layer | LiteLLM proxy on same VPS — Hermes points at it via "your own endpoint" | Anthropic SDK direct, OpenAI base_url override per-provider |
| 7 | Second brain shape | **Synthesis**: PARA directory layout + Karpathy three operations (Ingest/Query/Lint) + Forte Progressive Summarization as Lint pass | Pure Karpathy flat wiki, pure Forte (no LLM ops), OpenHuman Memory Tree, mem.ai self-organizing |
| 8 | Trust model | Tiered autonomy + $20/day hard cap (low-risk auto, medium-risk Telegram-approve, high-risk forbidden) | Approval-gated everything, mostly-autonomous post-hoc, TELOS-bound (deferred) |
| 9 | Ingestion rollout | Phased + TELOS-derived: Telegram-only day 0, TELOS draft week 7, RSS week 10 | Heavy monitoring upfront, TELOS-first blocking, skip TELOS |
| 10 | HTML ingestion | Crawl4AI MCP (primary, already installed) + Jina Reader fallback + Obsidian Web Clipper (one-click) + Docling for PDF/DOCX | Mozilla Readability only, Firecrawl paid, Readwise Reader paid |
| 11 | Mac role | Obsidian client (vault edit) + optional Ollama host (via Tailscale tunnel from VPS) | Mac as orchestrator host, Mac-only no VPS |
| 12 | Operation cadence | 24/7 system uptime; max-effort dev cadence (5-9 week timeline at 20+ hr/week) | 10hr/week 3-month timeline, 5hr/week 6-month timeline |

---

## Tech stack

### On the Hostinger VPS

| Component | Version pin | Purpose |
|-----------|------------|---------|
| Ubuntu 24.04 LTS | (Hostinger default) | OS |
| Docker + Docker Compose | latest | Container runtime |
| **Hermes Agent** | **pin to specific release** (TBD — check latest stable before install) | Orchestrator runtime, Telegram bot, multi-provider, cron, MCP host |
| **LiteLLM proxy** | latest stable | Model-agnostic gateway (Anthropic, OpenAI, Groq, Ollama, OpenRouter) |
| **Crawl4AI** | 0.8.6 (matches user's existing) | HTML extraction with JS rendering |
| systemd | (built-in) | Service management |
| Tailscale | latest | Secure VPS↔Mac tunnel for Ollama access |
| Git + GitHub CLI | latest | Vault sync to private GitHub repo |
| SQLite | (built-in) | Hermes session memory + cost ledger |
| ripgrep | latest | Fast Markdown search (Karpathy "filesystem as index") |
| qmd (Karpathy's tool) | latest | Hybrid BM25+vector+LLM-rerank search on vault |
| python-telegram-bot | (bundled in Hermes) | Telegram integration |

### On the Mac

| Component | Purpose |
|-----------|---------|
| **Obsidian** | Primary vault edit surface; git-synced from VPS |
| Obsidian Git plugin | Auto-pull from GitHub on launch + periodic |
| Obsidian Web Clipper extension | One-click capture from any browser → Inbox |
| **Ollama** | Optional local LLM host (Qwen3:32b for private/cheap workers) |
| Tailscale | Same tailnet as VPS for secure tunnel |
| Existing Claude Code + claude-mem ecosystem | Untouched — this is a NEW parallel system, not a replacement |

### Model providers (LiteLLM-routed)

| Provider | Model | Tier | Use |
|----------|-------|------|-----|
| Anthropic | claude-opus-4-7 | **A** (high quality) | Orchestrator brain, weekly review, TELOS interview |
| Anthropic | claude-sonnet-4-6 | **B** (default) | Workers, brain.query, brain.lint, daily digest |
| Anthropic | claude-haiku-4-5 | **C** (cheap routine) | TELOS check, RSS ingest, simple summary |
| Groq | llama-3.3-70b-versatile | **C** (fast cheap) | High-throughput workers, mechanical extraction |
| OpenAI | gpt-5 (fallback) | A fallback | If Anthropic rate-limited |
| Ollama (Mac) | qwen3:32b or llama3.3:70b | **D** (free private) | Privacy-flagged content, batch cost-sensitive work |

---

## Second brain layout

```
~/second-brain/                                  # git repo on VPS, GitHub remote, Mac pulls into Obsidian
├── CLAUDE.md                                    # Karpathy schema-as-config: tells Hermes how brain is organized
├── README.md                                    # for humans browsing the vault
├── 00-Projects/                                 # Forte PARA: active research with end-state
│   └── 2026-05-research-agent-observability/
│       ├── _briefing.md                         # Express output — what gets pushed to Telegram
│       ├── _log.md                              # Karpathy timestamped operations log
│       ├── _meta.yaml                           # Project metadata (TELOS-tags, budget, status)
│       ├── sources/                             # Karpathy raw layer (immutable ingested sources)
│       │   ├── arxiv-2406-12345.md
│       │   ├── hn-discussion-39812345.md
│       │   └── ...
│       ├── entities/                            # Karpathy entity pages (tools, people, companies)
│       │   ├── langfuse.md
│       │   └── ...
│       ├── concepts/                            # Karpathy concept pages
│       │   ├── observability-vs-tracing.md
│       │   └── ...
│       └── synthesis.md                         # The wiki's "opinion" on the topic
├── 01-Areas/                                    # Forte PARA: ongoing concerns (no end date)
│   ├── engineering-knowledge/
│   │   ├── MOC.md                               # Nick Milo Map of Content
│   │   ├── _log.md
│   │   ├── concepts/
│   │   └── entities/
│   ├── ai-tooling-landscape/
│   ├── personal-finance/
│   └── relationships/
├── 02-Resources/                                # Forte PARA: reference material
│   ├── papers/
│   ├── books/
│   ├── articles/
│   └── prompts/                                 # reusable prompt library
├── 03-Archives/                                 # Forte PARA: completed/dormant
│   └── 2026-Q1/
├── Inbox/                                       # Unfiled captures (Obsidian Web Clipper drops here)
└── _system/
    ├── telos.md                                 # PAI-style identity layer (written week 7+)
    ├── telos/
    │   ├── mission.md
    │   ├── quarter-goals.md
    │   ├── values.md
    │   └── dont-do.md
    ├── people.md                                # Global entity index
    ├── companies.md
    ├── log.md                                   # Karpathy global operations log
    ├── cost-ledger.md                           # Per-day API spend log
    ├── index.md                                 # qmd hybrid search index target
    └── lint-report.md                           # Latest brain.lint findings
```

### Frontmatter schema for ingested docs

```yaml
---
id: 2026-05-18-anthropic-blog-prompt-caching
type: article                                   # article | paper | book | concept | entity | log
title: "Prompt Caching with Claude"
author: "Anthropic"
source_url: https://anthropic.com/...
canonical_url: https://anthropic.com/...
published_at: 2026-05-15
ingested_at: 2026-05-18T14:23:00Z
ingested_via: telegram                          # telegram | clipper | rss | manual
para_tier: 02-Resources
tags: [anthropic, prompt-caching, llm-cost]
entities: [[Anthropic]], [[Claude]]
concepts: [[prompt-caching]], [[token-economics]]
distill_layer: 0                                # 0=raw, 1=highlighted, 2=summarized, 3=executive
telos_relevance: 0.8                            # if TELOS exists; 0-1 score
status: ingested                                # ingested | distilled | linted
ingest_cost: 0.023                              # USD spent on LLM during ingest
---
```

### CLAUDE.md schema (the Karpathy schema-as-config)

A single Markdown file at vault root that tells every Hermes skill:
- Directory layout and meaning
- Naming conventions
- Frontmatter schema (above)
- Cross-link conventions (`[[entity-name]]`)
- Tag taxonomy
- When to write where (decision tree for `brain.ingest` filing logic)
- Audit log format (`## [YYYY-MM-DD] operation | description`)
- Privacy markers (`<private>...</private>` wrappers strip before LLM calls)

---

## Hermes skills (the actual code)

Skills are written using the **agentskills.io open standard** (Hermes-native, portable if you ever migrate). Each is a directory under `~/hermes-config/skills/<skill-name>/` with `SKILL.md` + supporting Python.

| Skill | Lines (est) | Tier | Purpose | Critical files |
|-------|------------|------|---------|----------------|
| `brain.ingest` | ~150 | B (planning) + C (extraction) | URL/file/text → Crawl4AI/Jina/local extraction → LLM summarize → file into PARA tier → update entities → log | `skills/brain.ingest/SKILL.md`, `skills/brain.ingest/extractor.py`, `skills/brain.ingest/filer.py` |
| `brain.query` | ~80 | A (planning) + B (synthesis) | Question → qmd hybrid retrieval → LLM synthesize w/ citations → optionally file answer as wiki page | `skills/brain.query/SKILL.md`, `skills/brain.query/qmd_client.py` |
| `brain.lint` | ~120 | B + heavy prompt caching | Nightly cron: contradictions, orphans, stale claims, progressive summarization (Forte Distill); reports to `_system/lint-report.md` | `skills/brain.lint/SKILL.md`, `skills/brain.lint/lint_passes.py` |
| `brain.express` | ~60 | B (daily) + C (TTS) | Synthesize Project briefing → push to Telegram; weekly optional TTS podcast via OpenAI/ElevenLabs | `skills/brain.express/SKILL.md`, `skills/brain.express/tts.py` |
| `brain.review` | ~80 | A (high-stakes) | Weekly: stale Projects, dormant Areas, TELOS-alignment flags, propose archives | `skills/brain.review/SKILL.md` |
| `telos.interview` | ~100 | A | Multi-session /interview pattern: Hermes asks 5-10 questions per session, drafts/refines TELOS over weeks | `skills/telos.interview/SKILL.md`, `skills/telos.interview/sessions.py` |
| `telos.check` | ~40 | C | Pre-action TELOS-alignment scoring for medium-risk gating | `skills/telos.check/SKILL.md` |
| `worker.research` | ~80 | B | Ephemeral research worker: web_search + scrape + summarize loop, returns Markdown summary | `skills/worker.research/SKILL.md`, `skills/worker.research/loop.py` |
| `worker.monitor` | ~60 | C/D | RSS poll + dedup + auto-file new items into Inbox; runs every 4h cron | `skills/worker.monitor/SKILL.md`, `skills/worker.monitor/feeds.yaml` |
| **TOTAL** | **~770 LOC** | | All skills + Hermes config + LiteLLM YAML | |

### Skill dispatch flow (Hermes orchestrator)

```
Telegram message arrives
   │
   ▼
Hermes orchestrator (Tier A: claude-opus-4-7, prompt-cached)
   │ Intent classification:
   │   - "ingest this URL"           → brain.ingest
   │   - "research X"                 → worker.research (potentially fan-out N workers)
   │   - "what do we know about Y?"   → brain.query
   │   - "summarize my week"          → brain.review (on-demand)
   │   - "<conversational>"           → direct response, no skill
   │
   ▼
Skill execution (Tier B/C/D depending on skill)
   │
   ▼
Result: file written to vault + Telegram response + git commit
   │
   ▼
Cost ledger updated; cap checked
```

### Worker fan-out pattern (for "research X" tasks)

```
Orchestrator: "research X"
   │
   ▼
Planning call (Tier A, cached system prompt)
   → outputs: 5 subtask plan
   │
   ├─→ worker.research #1 (Tier B)  ─┐
   ├─→ worker.research #2 (Tier B)  ─┤
   ├─→ worker.research #3 (Tier B)  ─┤  asyncio.gather()
   ├─→ worker.research #4 (Tier C)  ─┤
   └─→ worker.research #5 (Tier C)  ─┘
   │
   ▼
Aggregation call (Tier A, cached project context)
   → produces: synthesis.md + _briefing.md
   │
   ▼
brain.express → Telegram push
```

---

## Cost model

### Per-operation pricing (verified May 2026)

| Operation | Tier | Per-call typical | Per-day budget |
|-----------|------|------------------|----------------|
| Orchestrator brain (intent + plan) | A | $0.04-0.10 | ≤$2 |
| Default worker | B | $0.025-0.10 | ≤$8 (across 50-100 calls) |
| Cheap worker / RSS ingest | C | $0.005-0.025 | ≤$3 |
| Private worker (Ollama) | D | $0 | $0 |
| brain.lint nightly | B + cache | $0.50-2 | ≤$3 |
| brain.express daily | B | $0.05-0.15 | ≤$1 |
| brain.review weekly | A | $0.20-0.70 | ≤$1 (amortized) |
| TELOS check (medium-risk gate) | C | $0.003-0.008 | ≤$1 |

### Cost limits (enforced in orchestrator)

```python
COST_LIMITS = {
    "per_subtask":         1.00,    # one worker call max
    "per_research_task":   5.00,    # one user "research X" request
    "per_deep_research":  10.00,    # user-flagged deep research
    "per_lint_run":        3.00,    # nightly lint
    "per_day_total":      20.00,    # HARD CAP — refuses new tasks
    "warn_at_pct":         0.80,    # Telegram warning at 80%
    "monthly_target":      300,     # for tracking; not enforced
}
```

### Prompt caching (the biggest cost lever — 70-90% savings)

Cache via Anthropic's `cache_control` (LiteLLM auto-translates):
1. **Orchestrator system prompt** (TELOS + schema + agent_prompt): ~10-20K tokens, cached for whole session
2. **PARA structure index** (`_system/index.md`): ~2-5K tokens, slow-changing
3. **Recent log.md** (last 30 entries): ~5K tokens
4. **Per-Project context** (cached when working a Project): ~5-10K tokens

### Realistic projection

| Scenario | Daily | Monthly |
|----------|-------|---------|
| Light use (3-5 tasks/day) | $1.50-3.50 | $45-105 |
| Medium use (5-10 tasks/day) | $3-8 | $90-240 |
| Heavy use (10+ tasks, all crons + RSS) | $8-15 | $240-450 |
| Cap-hitting | $20 | $600 (absolute max) |

**Ollama-mode** (Mac always-on + Tailscale): subtract Tier C/D = ~30-50% savings.

---

## Roadmap (5-9 weeks, max-effort cadence)

### Week 1 — Foundation + MVP (20-40 hrs)

| Day | Deliverable | Skill | Validates |
|-----|------------|-------|-----------|
| 1 | Hostinger VPS provisioned, Ubuntu 24.04, Docker, Tailscale | — | SSH + tailnet works |
| 1 | LiteLLM proxy running, YAML with 5 providers tested | — | `curl localhost:4000/v1/chat/completions` works for each provider |
| 1 | Hermes installed (pinned release), Telegram bot configured | — | "Hi" → reply works |
| 2 | Crawl4AI MCP wired into Hermes | — | Hermes can call `mcp__crawl4ai__md` |
| 2 | Vault git repo initialized on VPS, GitHub remote, cron commits | — | Test commit visible on GitHub |
| 3 | CLAUDE.md schema doc written | — | Doc readable; covers all conventions |
| 3 | PARA initial structure scaffolded | — | All 4 folders exist with READMEs |
| 4-5 | `brain.ingest` skill v1 (Crawl4AI → LLM filing) | brain.ingest | Send 5 URLs via Telegram, verify clean Markdown in PARA |
| 6-7 | Cost ledger + per-call logging + hard cap enforcement | — | Verify $20 cap triggers refusal |

**Week 1 exit criteria:** Telegram URL → Crawl4AI → filed in correct PARA tier → ledger logs cost → can browse vault on Mac via git pull.

### Week 2 — First end-to-end research task

| Day | Deliverable | Skill |
|-----|------------|-------|
| 8-9 | `worker.research` skill v1 (search + scrape + summarize) | worker.research |
| 10-11 | Orchestrator fan-out logic (planning → spawn N workers → aggregate) | (orchestrator config) |
| 12 | First end-to-end "research X" task tested | — |
| 13 | `brain.query` skill v1 (qmd + LLM synthesis with citations) | brain.query |
| 14 | Obsidian Git plugin on Mac; auto-pull working | — |

**Week 2 exit criteria:** "Research X" via Telegram → orchestrator plans → workers fan out → synthesis written → briefing pushed to Telegram → readable in Obsidian on Mac.

### Week 3 — Daily/weekly rhythm

| Day | Deliverable | Skill |
|-----|------------|-------|
| 15-16 | `brain.lint` skill v1 (multi-pass, prompt-cached) | brain.lint |
| 17 | Nightly lint cron at 02:00 UTC | — |
| 18-19 | `brain.express` skill v1 (daily digest, Telegram push) | brain.express |
| 20 | Daily digest cron at 20:00 local time | — |
| 21 | `brain.review` skill v1 (weekly Sunday 18:00) | brain.review |

**Week 3 exit criteria:** Wake up to lint report + daily digest in Telegram; first weekly review delivered.

### Week 4 — TELOS layer

| Day | Deliverable | Skill |
|-----|------------|-------|
| 22-24 | `telos.interview` skill (multi-session state) | telos.interview |
| 25-26 | First TELOS draft via interview (3-5 sessions over the week) | (content) |
| 27 | `telos.check` skill (medium-risk gating) | telos.check |
| 28 | Wire `telos.check` into orchestrator's medium-risk action flow | — |

**Week 4 exit criteria:** TELOS v0.1 exists; medium-risk actions now show TELOS-alignment reasoning in approval prompts.

### Week 5 — Autonomous monitoring

| Day | Deliverable | Skill |
|-----|------------|-------|
| 29-30 | `worker.monitor` skill (RSS poll + dedup + file) | worker.monitor |
| 31 | Configure 3-5 TELOS-derived RSS feeds | (content) |
| 32 | 4-hourly RSS cron | — |
| 33-34 | Obsidian Web Clipper configured to drop into Inbox | — |
| 35 | Test full Inbox → ingest → file flow | — |

**Week 5 exit criteria:** RSS feeds auto-ingest; Obsidian Web Clipper one-click works.

### Week 6-7 — Polish

| Day | Deliverable | Skill |
|-----|------------|-------|
| 36-37 | `brain.express` weekly podcast via TTS (OpenAI/ElevenLabs) | brain.express |
| 38-39 | TELOS-aware filtering in daily digest + RSS scoring | (orchestrator) |
| 40-42 | Edge-case handling: vault sync conflicts, Hermes restart, Crawl4AI failures | — |
| 43-44 | Cost optimization pass: tune which skills to Tier C, verify caching hits | — |
| 45-49 | Bugfix buffer, ergonomics, documentation in CLAUDE.md | — |

**Week 6-7 exit criteria:** Stable 24/7 operation; weekly podcast; documented ops runbook.

### Week 8-9 — Scale + hardening

| Day | Deliverable |
|-----|------------|
| 50-56 | Real-world usage: ingest 100+ items, run 20+ research tasks, refine prompts based on failures |
| 57-60 | Add MOCs (Maps of Content) for cross-Area concepts as they emerge |
| 61-63 | First archival pass (move completed Projects to `03-Archives/`) |

**Week 8-9 exit criteria:** Production-grade. Used daily. Iterating on what's broken, not what's missing.

---

## Verification (end-to-end tests)

### Manual smoke tests (after each week)

1. **Telegram → ingest**: Send a URL to Hermes bot → check vault for new file in correct PARA tier within 60s
2. **Telegram → research task**: Send "research X" → check that workers spawned (visible in cost ledger), briefing arrives in Telegram, files written to `00-Projects/`
3. **brain.query**: Ask "what do we know about [topic from ingested content]?" → verify cited answer with file links
4. **brain.lint**: Manually trigger lint → verify `_system/lint-report.md` updated with findings
5. **Daily digest**: Wait for 20:00 → verify Telegram message with day summary
6. **Cost cap**: Trigger 10 expensive tasks in sequence → verify cap kicks in around 80% with warning, hard refusal at 100%
7. **Vault sync**: Edit a note in Obsidian on Mac → push → verify VPS pulls on next cron tick (or vice versa)
8. **Ollama fallback**: Disable Anthropic key temporarily → verify orchestrator routes to Ollama via LiteLLM
9. **TELOS check**: Trigger a medium-risk action (e.g. write to `01-Areas/`) → verify Telegram approval prompt with TELOS-alignment reasoning

### Automated checks

- `health-check.sh` on cron: pings Telegram bot, hits LiteLLM proxy, verifies Hermes process, checks vault git status. Reports failures to Telegram.
- `cost-check.sh` daily 23:55: rolls up `_system/cost-ledger.md` and posts daily summary.
- `lint-check.sh` weekly Sunday: runs full lint pass + reports to Telegram.

---

## Critical risks + mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Hermes ships breaking change | Medium (5k PRs/10mo) | High | **Pin specific release**; review changelogs before bumping; backup config |
| Brain becomes garbage (auto-ingest noise) | Medium | High | `brain.lint` aggressive pruning; weekly review surfaces issues; quarantine folder for low-confidence ingests |
| TELOS becomes procrastination tool | Medium | Medium | Hard cap: 30 min/week on TELOS work; ship v0.1 fast; refine via use |
| Cost surprise | Low (with caps) | High | Daily cap + 80% warning + per-task logs; manual review of weekly spend |
| Vault sync conflicts (Mac + VPS concurrent writes) | Medium | Medium | Hermes always `git pull` before writing; commit-before-write discipline; Obsidian Git auto-resolve |
| Privacy leak (Claude API sees all brain) | High (by design) | Medium | `<private>...</private>` wrappers strip before LLM calls; route private content to Tier D Ollama only |
| Hermes' opinions fight chosen topology | Medium | Medium | Document override points; fallback Option G (Hermes plumbing + custom MCP) if friction unbearable |
| Mac sleeps when Ollama needed | High | Low | `caffeinate -i` while desired; LiteLLM auto-fallback to cloud if Ollama unreachable |
| VPS goes down | Low | High | Daily snapshot via Hostinger MCP; restore playbook documented; vault is git-backed (recoverable) |
| API key leak | Low | High | All keys in `~/.env` (gitignored); rotation playbook; only Hermes process reads keys |

---

## Existing assets to reuse

| Asset | Where | How it's used |
|-------|-------|---------------|
| **Crawl4AI MCP** | `~/.agents/crawl4ai/` (Docker on localhost:11235) | Primary HTML extractor for `brain.ingest` — REUSE AS-IS |
| **claude-mem MCP** | Already installed globally | Read-only consult during `brain.query` to check "did I research this before in a Claude Code session?" |
| **claudeclaw plugin** | Already installed | Independent — do NOT integrate; this is for interactive Claude Code, the new system is the autonomous layer |
| **Context7 MCP** | Already installed | `worker.research` can call for library docs lookups |
| **Hostinger MCP** | Already installed (rule: read before write) | VPS provisioning, snapshots, DNS for Telegram webhook subdomain |
| **GitHub MCP** | Already installed | Vault repo creation, PR comments if needed |
| **Telegram MCP (`claudeclaw:telegram`)** | Already installed | Optional: development-time message testing (separate from production bot) |

---

## Memory layer — evaluated alternatives

Researched: `agentmemory` (rohitg00, 11.5k★, TypeScript, 3 months old), `mem0` (56k★, Python, 3 years), `Letta` (23k★, Python, 3 years), `Chroma` (28k★, Rust), `Qdrant` (31k★, Rust).

**Decision: Keep current plan (Markdown vault + qmd + LLM retrieval) for v1. Defer agentmemory to Phase 4. Reject mem0 and Letta.**

| Option | Verdict | Reasoning |
|--------|---------|-----------|
| **agentmemory** | **Phase 4 optional** | Killer feature (Claude Code hooks) doesn't apply to Hermes. 4-tier consolidation pattern is worth stealing. Retrieval quality may justify integration IF qmd proves insufficient. 3-month-old → risk on critical path. |
| **mem0** | **Rejected** | Requires Qdrant/pgvector (heavy deps). No auto-capture. Adds Python framework dependency without clear win over Markdown approach. |
| **Letta** | **Rejected** | Full agent runtime — would replace Hermes. Reverses our orchestrator decision. Heavy deps. |
| **Chroma / Qdrant** | **Rejected (standalone)** | Pure vector DBs. Overkill — qmd's hybrid search covers our needs. Revisit only if we need standalone vector search at scale. |

### Patterns stolen from agentmemory (applied NOW)

1. **4-tier memory consolidation taxonomy** — apply to our PARA structure as semantic tiers:

   | agentmemory tier | Our equivalent | Where it lives |
   |------------------|----------------|----------------|
   | **Working** (raw observations) | Inbox + raw sources | `Inbox/` + `00-Projects/*/sources/` |
   | **Episodic** (session summaries — "what happened") | Project briefings + logs | `00-Projects/*/_briefing.md` + `_log.md` |
   | **Semantic** (extracted facts — "what I know") | Entity + concept pages in Areas | `01-Areas/*/entities/` + `01-Areas/*/concepts/` |
   | **Procedural** (workflows — "how to do it") | Prompt library + skill snippets | `02-Resources/prompts/` |

   This gives `brain.lint` a clear consolidation pipeline: Working → Episodic (weekly), Episodic → Semantic (monthly), Semantic → Procedural (quarterly).

2. **Decay logic** — TTL-based stale claim detection in `brain.lint`:
   - Raw sources (Working tier) → no decay (immutable)
   - Briefings (Episodic) → decay-flag after 6 months
   - Entity/concept pages (Semantic) → re-validate quarterly, flag if cited sources are stale
   - Prompts (Procedural) → flag unused-in-90-days for archival review

3. **Audit trail discipline** — every memory operation logs to `_log.md` with operation type + provenance, matching agentmemory's governance pattern.

### Phase 4 trigger conditions (when to revisit agentmemory)

Add agentmemory as a Phase 4 optional component IF any of these surface during weeks 1-12:

- qmd retrieval R@5 measurably below 80% (test with 20 ground-truth queries)
- You find yourself wanting auto-capture from other tools beyond Telegram/RSS/Clipper
- Cross-session memory becomes a friction point (e.g. "I already researched this 3 weeks ago, why doesn't the system remember?")
- Vault grows past 5,000 files (qmd may slow down)

**Integration pattern (if Phase 4 triggers):** Run agentmemory as a separate service on the VPS, MCP-exposed to Hermes. agentmemory indexes the Markdown vault (via REST `memory_save` calls in `brain.ingest`), provides `memory_smart_search` to Hermes via MCP. Markdown remains source of truth; agentmemory is a retrieval+consolidation cache.

---

## Open questions deferred to implementation

These were discussed in grilling but don't block plan approval. Decide in-flight:

1. **Specific Hermes release to pin** — check latest stable when starting Week 1 Day 1
2. **Exact RSS feeds** — derived from TELOS in Week 5
3. **TTS provider for podcast** — OpenAI vs ElevenLabs comparison at Week 6
4. **qmd vs alternative search tool** — evaluate qmd maturity in Week 2; fallback to plain ripgrep + LLM rerank if qmd not ready; agentmemory as Phase 4 escalation
5. **Whether to add Discord as second channel** — only if heavy Telegram usage hits limits (unlikely at personal scale)
6. **Whether `brain.express` podcast should be daily or weekly** — default weekly; reassess after first 2-3 podcasts
7. **PAI architectural patterns to steal beyond TELOS** — 6-tier memory layout (WORK/KNOWLEDGE/LEARNING/RELATIONSHIP/OBSERVABILITY/STATE) is interesting; revisit at Week 8 once base system is stable
8. **agentmemory integration** — defer to Phase 4; trigger conditions documented above

---

## What this plan explicitly does NOT do

- **Does not replace Claude Code** — Claude Code remains the interactive dev tool; this is the autonomous agent layer
- **Does not migrate claude-mem** — claude-mem stays for interactive sessions; this system has its own memory in the vault
- **Does not build a custom Telegram bot from scratch** — Hermes provides this turnkey
- **Does not require LangChain/LangGraph/CrewAI** — explicitly rejected for topology fit
- **Does not include code execution agents** — explicitly forbidden in Trust model (high-risk)
- **Does not include email/calendar/social ingestion** — deferred indefinitely unless TELOS justifies
- **Does not include a UI dashboard** — Telegram + Obsidian are the surfaces; no web frontend
- **Does not replicate PAI's full architecture** — steals patterns (TELOS, /interview), doesn't adopt the runtime

---

## Decision audit trail

Research artifacts feeding this plan (all in `plans/`):
- `ultra-research-about-mult-generic-cocke-agent-a9a83d6cf8cf3e353.md` — framework comparison (LangGraph, CrewAI, MetaGPT, OpenHuman, Hermes, OpenClaw, AionUi)
- `ultra-research-about-mult-generic-cocke-agent-a1ee2b31dfec86466.md` — second-brain methodology synthesis (Karpathy + Forte + Miessler + GuruSup critique)
- `ultra-research-about-mult-generic-cocke-agent-a17a34226bba4561b.md` — model-agnostic verification (LiteLLM, Pydantic AI, Ollama, GitHub repo ground-truth)

Grilling decisions captured in conversation (8 questions answered):
1. Primary value → Async research delivery
2. Chat tool → Telegram
3. Topology → 1 orchestrator + ephemeral workers
4. Runtime → VPS + git-sync to Mac/Obsidian
5. Stack (after model-agnostic pushback) → Hermes Agent turnkey
6. Second brain shape → PARA + Karpathy synthesis
7. Trust → Tiered autonomy + $20/day cap
8. Surfaces/cron → Phased + TELOS-derived (with Mac-OK adjustments)

---

## Ready to execute when

1. This plan is approved via ExitPlanMode
2. Hostinger VPS purchased / confirmed (2 vCPU, 4GB RAM minimum recommended)
3. Telegram bot token created via @BotFather
4. Anthropic API key + at least one fallback provider key (Groq recommended; free tier exists)
5. Private GitHub repo created for vault
6. Tailscale account active (free for personal)
7. Mac has Obsidian installed with Git plugin
