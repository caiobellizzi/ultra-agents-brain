<!-- refreshed: 2026-05-19 -->
# Architecture

**Analysis Date:** 2026-05-19

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                          User Interface Layer                            │
│          Telegram (via Hermes Agent)  /  CLI (python -m ultra_brain)    │
└──────────────┬──────────────────────────────────────┬───────────────────┘
               │                                      │
               ▼                                      ▼
┌──────────────────────────┐            ┌─────────────────────────────────┐
│   Hermes Agent Runtime   │            │  ultra_brain.__main__ (CLI)     │
│  `deploy/hermes/`        │            │  `ultra_brain/__main__.py`      │
│  Dispatches to skills    │            │  11 subcommands                  │
└──────────────┬───────────┘            └────────────────┬────────────────┘
               │                                         │
               ▼ (calls)                                 ▼ (imports)
┌─────────────────────────────────────────────────────────────────────────┐
│                         Skills Layer                                     │
│  `skills/<name>/`  — thin CLI/dispatch wrappers that import ultra_brain │
│  brain.ingest  brain.query  brain.lint  brain.express  brain.review     │
│  telos.check   telos.interview   worker.research   worker.monitor       │
└──────────────────────────────┬──────────────────────────────────────────┘
                               │ (imports)
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       ultra_brain Package (Core)                         │
│  ingest.py  query.py  lint.py  express.py  review.py  research.py      │
│  monitor.py  telos.py  trust.py  cost.py  vault.py  markdown.py  llm.py│
└──────────────┬──────────────────────────────┬──────────────────────────┘
               │                              │
               ▼ (reads/writes)               ▼ (HTTP POST)
┌──────────────────────────┐    ┌─────────────────────────────────────────┐
│  Vault (Markdown files)  │    │    LiteLLM Proxy (model gateway)        │
│  `vault/`                │    │    `deploy/litellm/config.yaml`         │
│  PARA layout + _system   │    │    http://127.0.0.1:4000/v1             │
└──────────────────────────┘    └─────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File(s) |
|-----------|----------------|---------|
| `__main__` | CLI entry; dispatches 11 subcommands | `ultra_brain/__main__.py` |
| `llm` | Stdlib-only HTTP client against LiteLLM proxy; 4 model tiers | `ultra_brain/llm.py` |
| `vault` | Vault directory bootstrap; `VAULT_DIRS`, `SYSTEM_FILES`, `unique_path` | `ultra_brain/vault.py` |
| `markdown` | Frontmatter parse/dump, slugify, wikilink extract, log append, private-block strip | `ultra_brain/markdown.py` |
| `cost` | Ledger I/O, budget gates (warn at 80%, refuse at 100%) | `ultra_brain/cost.py` |
| `trust` | Risk classification (low/medium/high), private-block routing, approval prompts | `ultra_brain/trust.py` |
| `ingest` | `Extractor` (crawl4ai → jina → text fallback) + `Filer` (PARA routing, frontmatter, entity pages, log) | `ultra_brain/ingest.py` |
| `query` | `RipgrepRetriever` (pure Python BM25-like) + `QmdClient` (qmd binary fallback) + `synthesize_answer` | `ultra_brain/query.py` |
| `lint` | `run_lint` (deterministic passes) + `run_llm_lint` (STALE/CONTRADICTION via LLM) + report writer | `ultra_brain/lint.py` |
| `express` | `daily_digest`, `project_briefing`, TTS placeholder | `ultra_brain/express.py` |
| `research` | `plan_research` (fixed 5-angle decomposition) + `worker_summary` + `aggregate_research` (project scaffold) | `ultra_brain/research.py` |
| `monitor` | RSS fetch, URL canonicalization, SHA-256 dedup, TELOS scoring, Inbox filing | `ultra_brain/monitor.py` |
| `review` | Stale project / dormant area detection + TELOS alignment scores | `ultra_brain/review.py` |
| `telos` | `TelosSessionStore` (JSON interview state), `score_alignment` (LLM or keyword heuristic) | `ultra_brain/telos.py` |
| Skills | Thin CLI wrappers + Hermes SKILL.md descriptor; import `ultra_brain.*` | `skills/<name>/*.py`, `skills/<name>/SKILL.md` |
| Hermes config | Skill load list, Telegram webhook, LiteLLM reference, cron references | `deploy/hermes/config.yaml` |
| LiteLLM config | 4 local tiers + 2 cloud fallbacks; fallback chains | `deploy/litellm/config.yaml` |

## Pattern Overview

**Overall:** Layered Python monolith with a Hermes agent frontend

**Key Characteristics:**
- No third-party Python dependencies in `ultra_brain` — all stdlib (`urllib.request`, `json`, `hashlib`, `xml.etree`, `argparse`, `pathlib`)
- The vault is the primary data store: all state written as Markdown files with YAML frontmatter
- LLM calls are always optional: every function that calls `llm.complete()` has a deterministic heuristic or stub fallback
- Skills are adapters: `skills/<name>/` files are thin wrappers that import and re-expose `ultra_brain.*` functions for Hermes dispatch
- Trust/cost gates are cross-cutting: `trust.py` and `cost.py` are called by Hermes skills before any write operation

## Layers

**LLM Gateway (external):**
- Purpose: Normalize model access, apply fallback chains, enforce a single auth surface
- Location: `deploy/litellm/config.yaml`, running at `http://127.0.0.1:4000/v1`
- Tiers: `orchestrator` (A), `default-worker` (B), `cheap-worker` (C), `private-worker` (D); cloud fallbacks `cloud-sonnet`, `cloud-groq`
- Depends on: LM Studio (local) or cloud provider API keys via env vars

**Core Package (`ultra_brain`):**
- Purpose: All business logic — ingestion, retrieval, synthesis, scheduling, governance
- Location: `ultra_brain/`
- Depends on: LiteLLM proxy (HTTP), vault filesystem
- Used by: `__main__` CLI, skills layer

**Skills Layer:**
- Purpose: Hermes-callable adapters; each skill wraps one or more `ultra_brain` functions
- Location: `skills/<name>/`
- Contains: `SKILL.md` (trigger/IO/cost spec), thin Python scripts, `prompts/` directory
- Depends on: `ultra_brain` package
- Used by: Hermes Agent runtime

**Infrastructure Layer:**
- Purpose: Process lifecycle, cron scheduling, secrets plumbing
- Location: `deploy/`, `scripts/`
- Contains: `docker-compose.yml` (litellm + hermes services), `systemd/` unit, `cron/` schedule

## Data Flow

### Primary Ingest Path (Telegram URL → Vault Note)

1. User sends URL to Telegram → Hermes receives webhook (`deploy/hermes/config.yaml:27`)
2. Hermes routes to `brain.ingest` skill → `skills/brain.ingest/filer.py`
3. `Extractor.extract()` fetches via crawl4ai → jina → text fallback (`ultra_brain/ingest.py:48`)
4. `trust.classify_action()` evaluates risk; medium risk sends Telegram approval request (`ultra_brain/trust.py:32`)
5. `CostLedger.gate()` checks daily budget; refuses if projected > $20/day (`ultra_brain/cost.py:81`)
6. `Filer.file()` determines PARA tier (LLM or heuristic), writes frontmatter note to vault (`ultra_brain/ingest.py:115`)
7. `append_log()` appends operation to `vault/_system/log.md` (`ultra_brain/markdown.py:85`)
8. `CostLedger.record()` appends row to `vault/_system/cost-ledger.md` (`ultra_brain/cost.py:92`)
9. Hermes sends Telegram confirmation with path and cost

### Research Fan-Out Path

1. Telegram research request → Hermes → `worker.research` skill → `skills/worker.research/loop.py`
2. `plan_research(topic)` decomposes into up to 5 fixed-angle `ResearchSubtask` objects (`ultra_brain/research.py:23`)
3. Each `worker_summary(topic, angle, sources)` fetches up to 3 URLs and summarizes via LLM (`ultra_brain/research.py:45`)
4. `aggregate_research()` scaffolds `00-Projects/<slug>/` with `sources/worker-N.md`, `synthesis.md`, `_briefing.md`, `_log.md` (`ultra_brain/research.py:83`)
5. Global log updated; Telegram receives project directory path

### Query Path

1. `query_vault(question, vault, ...)` → `QmdClient.search()` or `RipgrepRetriever.search()` (`ultra_brain/query.py:121`)
2. Retriever scans `vault/**/*.md` for term overlap; returns top-N `SearchHit` objects
3. `synthesize_answer()` builds evidence block; optionally calls `llm.complete()` for cited prose (`ultra_brain/query.py:75`)
4. Falls back to evidence list if LLM unavailable

### Scheduled Path (Cron)

- Every 4 hours: `monitor` subcommand → `run_poll()` fetches RSS feeds, deduplicates, files to `vault/Inbox/` (`ultra_brain/monitor.py:85`)
- Daily 20:00: `digest` subcommand → `daily_digest()` summarizes `_system/log.md` + cost rollup (`ultra_brain/express.py:12`)
- Weekly Sunday 18:00: `review` subcommand → `write_weekly_review()` checks stale projects + TELOS alignment
- Nightly 02:00: `lint` subcommand → `write_lint_report()` writes `vault/_system/lint-report.md`
- Health check every 15 min: `scripts/health-check.sh`

**State Management:**
- All durable state is Markdown files in `vault/`; no database
- Monitor dedup state in `vault/_system/monitor-seen.json`
- TELOS interview sessions in `vault/_system/telos-sessions.json`
- Cost ledger is an append-only Markdown table in `vault/_system/cost-ledger.md`

## Key Abstractions

**`ExtractionResult` (frozen dataclass):**
- Purpose: Normalized content from any source (URL/file/text); carries content hash for dedup
- Defined: `ultra_brain/ingest.py:25`

**`IngestResult` (frozen dataclass):**
- Purpose: Outcome of a filing operation; carries `note_path`, `log_path`, `cost_warning`, `message`
- Defined: `ultra_brain/ingest.py:34`

**`CostGate` (frozen dataclass):**
- Purpose: Budget decision with `allowed`, `warning`, `spent_before`, `projected`, `limit`, `reason`
- Defined: `ultra_brain/cost.py:35`

**`TrustDecision` (frozen dataclass):**
- Purpose: Risk classification with routing decision (`auto`, `approval`, `private-worker`, `refuse`)
- Defined: `ultra_brain/trust.py:22`

**`TelosCheck` (frozen dataclass):**
- Purpose: Alignment score (0.0–1.0) with rationale string; produced by keyword overlap or LLM call
- Defined: `ultra_brain/telos.py:62`

**`SKILL.md` descriptor:**
- Purpose: Schema-as-config for Hermes skill dispatch; defines triggers, inputs, outputs, cost/trust constraints
- Pattern: every skill directory contains one; `deploy/hermes/config.yaml` lists which to load

## Entry Points

**CLI:**
- Location: `ultra_brain/__main__.py`
- Invoke: `python -m ultra_brain --vault <path> <subcommand>`
- Subcommands: `ensure-vault`, `ingest`, `query`, `lint`, `digest`, `cost-summary`, `research-plan`, `research-aggregate`, `telos-check`, `monitor`, `review`, `telos-interview`

**Hermes Agent (Telegram):**
- Location: `deploy/hermes/config.yaml` + skill scripts in `skills/`
- Triggers: Telegram messages routed to named skills by Hermes runtime
- Skills loaded: `brain.ingest`, `brain.query`, `brain.lint`, `brain.express`, `brain.review`, `telos.interview`, `telos.check`, `worker.research`, `worker.monitor`

**Cron:**
- Location: `deploy/cron/ultra-agents-brain.cron`
- Schedules: digest (daily), review (weekly), monitor (4-hourly), lint (nightly), health-check (15-min)

## Architectural Constraints

- **No external Python deps:** `ultra_brain` uses stdlib only; pip-installable packages must not be added without decision
- **LLM calls are always optional:** every `llm.complete()` call is wrapped in `try/except` with a heuristic fallback; the system must work without a LiteLLM endpoint
- **Private content routing:** text containing `<private>...</private>` must be stripped (`markdown.strip_private_blocks`) before any cloud LLM call; notes with `privacy: secret` must not leave the local machine
- **Append-only logs:** `_system/log.md` and `_system/cost-ledger.md` are append-only; existing entries must never be rewritten
- **Trust gate ordering:** cost check then trust check must precede any vault write in skills; never write first and check later
- **Global state:** none — `CostLedger`, `TelosSessionStore`, `DedupStore` all take `Path` arguments; no module-level singletons
- **Threading:** single-threaded; no async or thread pools in `ultra_brain`; Hermes handles concurrency externally

## Anti-Patterns

### Bypassing the trust gate in skills

**What happens:** A skill writes to the vault directly without calling `trust.classify_action()` first.
**Why it's wrong:** Medium-risk writes to `01-Areas/`, `_system/`, or `03-Archives/` bypass the Telegram approval flow, creating unreviewed mutations.
**Do this instead:** Call `classify_action(description, target_path=rel_path)` and check `decision.allowed` and `decision.needs_approval` before any `Filer.file()` or direct `Path.write_text()` call. See `skills/common/trust_policy.py`.

### Calling `llm.complete()` without a fallback

**What happens:** A module raises an unhandled exception when LiteLLM is unreachable.
**Why it's wrong:** The system must degrade gracefully; a downed LM Studio session should not block ingest.
**Do this instead:** Wrap every `llm.complete()` in `try/except Exception` and return a heuristic result. See the pattern in `ultra_brain/ingest.py:181–194` (`Filer._choose_tier`).

### Writing raw secrets or credentials to the vault

**What happens:** An ingest source contains API keys or tokens and they are written verbatim to a note.
**Why it's wrong:** The vault is Git-synced to a private GitHub repo; secrets in notes become secrets in Git history.
**Do this instead:** Strip credential text before writing and add a redacted operational log entry. `trust.py` blocks `api key`, `private key`, and `credential` patterns as high-risk; skills must enforce this before extraction too.

## Error Handling

**Strategy:** Graceful degradation with heuristic fallbacks; errors surfaced via log append and return message, not exceptions

**Patterns:**
- LLM unavailable: every `llm.complete()` call is in `try/except Exception`; caller returns heuristic or stub result
- URL fetch failure: `Extractor._extract_url` tries crawl4ai → jina → writes a placeholder note (`ultra_brain/ingest.py:71`)
- RSS feed failure: `run_poll` catches per-feed exceptions and prints to stderr; other feeds continue (`ultra_brain/monitor.py:117`)
- Cost gate refused: `CostLedger.record()` returns a `CostGate(allowed=False)` without writing; caller must check and surface refusal
- File collision: `vault.unique_path()` appends `-2`, `-3`, etc. rather than overwriting (`ultra_brain/vault.py:43`)

## Cross-Cutting Concerns

**Logging:** `markdown.append_log()` writes structured Markdown entries to `vault/_system/log.md`; all operations must call it
**Cost tracking:** `CostLedger.record()` appends to `vault/_system/cost-ledger.md`; skill layer responsible for passing accurate `cost_usd`
**Privacy:** `markdown.strip_private_blocks()` strips `<private>…</private>` before cloud LLM calls; `lint.run_lint()` flags any note that still contains a private block
**TELOS alignment:** `telos.score_alignment()` is called by `monitor.score_items()` and `review.write_weekly_review()` to rank/annotate content by personal goal alignment

---

*Architecture analysis: 2026-05-19*
