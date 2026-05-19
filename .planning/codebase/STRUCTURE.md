# Codebase Structure

**Analysis Date:** 2026-05-19

## Directory Layout

```
ultra-agents-brain/
├── ultra_brain/          # Core Python package — all business logic
│   ├── __init__.py       # Version only (0.1.0)
│   ├── __main__.py       # CLI entry; 11 subcommands via argparse
│   ├── llm.py            # Stdlib HTTP client against LiteLLM proxy
│   ├── vault.py          # Vault bootstrap helpers
│   ├── markdown.py       # Frontmatter, wikilinks, slugify, log append
│   ├── cost.py           # CostLedger, CostGate, budget gates
│   ├── trust.py          # TrustDecision, risk classification, approval prompts
│   ├── ingest.py         # Extractor + Filer (PARA routing, entity pages)
│   ├── query.py          # RipgrepRetriever, QmdClient, synthesize_answer
│   ├── lint.py           # run_lint, run_llm_lint, write_lint_report
│   ├── express.py        # daily_digest, project_briefing, tts_placeholder
│   ├── research.py       # plan_research, worker_summary, aggregate_research
│   ├── monitor.py        # RSS fetch, dedup, Inbox filing
│   ├── review.py         # weekly_review, write_weekly_review
│   └── telos.py          # TelosSessionStore, score_alignment
│
├── skills/               # Hermes skill adapters (thin wrappers over ultra_brain)
│   ├── brain.ingest/     # SKILL.md + extractor.py + filer.py + prompts/
│   ├── brain.query/      # SKILL.md + qmd_client.py + prompts/
│   ├── brain.lint/       # SKILL.md + lint_passes.py + prompts/
│   ├── brain.express/    # SKILL.md + tts.py + prompts/
│   ├── brain.review/     # SKILL.md + review.py + prompts/
│   ├── telos.check/      # SKILL.md + check.py + prompts/
│   ├── telos.interview/  # SKILL.md + sessions.py + prompts/
│   ├── worker.research/  # SKILL.md + loop.py + prompts/
│   ├── worker.monitor/   # SKILL.md + monitor.py + feeds.yaml + prompts/
│   └── common/           # Shared skill helpers (cost_ledger.py, trust_policy.py)
│
├── vault/                # Markdown second-brain (PARA layout)
│   ├── CLAUDE.md         # Schema-as-config: frontmatter schemas, filing rules
│   ├── README.md         # PARA layout description
│   ├── Inbox/            # Unprocessed captures (RSS, Telegram, Web Clipper)
│   ├── 00-Projects/      # Active efforts with outcomes
│   ├── 01-Areas/         # Ongoing domains (ai-tooling-landscape, engineering-knowledge, ...)
│   ├── 02-Resources/     # Reference material (articles/, papers/, books/, prompts/)
│   ├── 03-Archives/      # Completed or inactive material
│   └── _system/          # Operational files (logs, cost-ledger, lint, telos)
│       └── telos/        # TELOS goal docs (mission.md, quarter-goals.md, dont-do.md)
│
├── deploy/               # Infrastructure config and process lifecycle
│   ├── docker-compose.yml  # litellm + hermes services
│   ├── litellm/
│   │   └── config.yaml   # 4-tier model list + fallback chains
│   ├── hermes/
│   │   └── config.yaml   # Telegram gateway, skill load list, path bindings, cron refs
│   ├── systemd/
│   │   └── ultra-agents-brain.service  # Systemd oneshot wrapping docker compose
│   └── cron/
│       └── ultra-agents-brain.cron     # 6 scheduled jobs (digest, review, monitor, lint, health)
│
├── taks/                 # Implementation phase plans (15 numbered markdown files)
│   ├── README.md         # Wave execution order and parallelization rules
│   ├── 00-prerequisites-and-decisions.md
│   ├── 01-vps-foundation.md
│   ├── ...
│   └── 14-production-validation.md
│
├── plans/                # High-level agent planning session outputs
├── scripts/              # Ops shell scripts (health-check, cost-check, lint-check, git-sync, vps-bootstrap)
├── ops/                  # Locked architectural decisions (decisions.md)
├── tests/                # Test suite
│   └── test_core.py      # Single unittest.TestCase with integration-style tests
├── docs/
│   └── runbooks/         # Operational runbooks
├── .planning/
│   └── codebase/         # GSD codebase map documents (STACK.md, this file, ...)
├── .env.example          # All env var names with no real values
└── CLAUDE.md             # RTK token-killer instructions for Claude sessions
```

## Directory Purposes

**`ultra_brain/`:**
- Purpose: All Python business logic; no framework, no third-party deps
- Contains: One module per concern; pure functions preferred; dataclasses for results
- Key files: `ingest.py` (entry path), `llm.py` (only external HTTP), `trust.py`+`cost.py` (governance)

**`skills/`:**
- Purpose: Hermes Agent adapter layer; each subdirectory is one loadable skill
- Contains: `SKILL.md` (trigger/IO/cost specification), thin Python scripts, `prompts/` with LLM prompt templates
- Key convention: scripts in a skill must import from `ultra_brain`, not duplicate logic

**`skills/common/`:**
- Purpose: Shared helper scripts usable by multiple skills (not loaded as a skill itself)
- Contains: `cost_ledger.py`, `trust_policy.py` (CLI wrappers that call `ultra_brain.cost` and `ultra_brain.trust`)

**`vault/`:**
- Purpose: Living Markdown second-brain; all agent outputs land here
- Contains: PARA-organized `.md` files with YAML frontmatter; `_system/` for operational state
- Key convention: `vault/CLAUDE.md` is the authoritative schema contract — it overrides any other convention

**`vault/_system/`:**
- Purpose: Append-only operational state; never delete entries
- Key files: `log.md` (global ops log), `cost-ledger.md` (Markdown table), `lint-report.md`, `monitor-seen.json`, `telos-sessions.json`

**`deploy/`:**
- Purpose: All infrastructure configuration; nothing here contains secrets
- Contains: Docker Compose stack (litellm + hermes), systemd service, cron schedule, YAML configs
- Key convention: secrets come in via `.env` (on VPS only) or env vars; `.env` is never committed

**`taks/`:**
- Purpose: Numbered implementation phase documents (15 phases in 6 waves); consumed by GSD and agents
- Key file: `taks/README.md` — defines parallel tracks and wave execution order

**`scripts/`:**
- Purpose: Bash ops scripts invoked by cron and manually on the VPS
- Key files: `health-check.sh`, `cost-check.sh`, `lint-check.sh`, `git-sync.sh`, `vps-bootstrap.sh`

## Key File Locations

**Entry Points:**
- `ultra_brain/__main__.py`: CLI dispatcher; all 11 subcommands defined here
- `deploy/hermes/config.yaml`: Hermes runtime config; skill load list and Telegram webhook
- `deploy/cron/ultra-agents-brain.cron`: Scheduled automation jobs

**Configuration:**
- `.env.example`: All required env var names (copy to `.env` on VPS with real values)
- `deploy/litellm/config.yaml`: Model tiers and fallback chains
- `vault/CLAUDE.md`: Vault schema-as-config (frontmatter schemas, filing rules, privacy rules)

**Core Logic:**
- `ultra_brain/ingest.py`: `Extractor` + `Filer` — primary write path to vault
- `ultra_brain/llm.py`: Single `complete()` function — sole LLM call surface
- `ultra_brain/trust.py`: `classify_action()` — must be called before any vault write
- `ultra_brain/cost.py`: `CostLedger` — tracks daily spend, enforces $20/day cap

**Testing:**
- `tests/test_core.py`: 8 integration-style tests covering ingest→query, cost gates, trust, research, lint, telos, monitor, review

## Naming Conventions

**Files:**
- Python modules: `snake_case.py`
- Skill directories: `<namespace>.<name>` with dot separator (e.g., `brain.ingest`, `worker.research`)
- Vault notes: `YYYY-MM-DD-kebab-slug.md` for dated notes, `kebab-slug.md` for evergreen pages
- Project control files: prefixed with `_` (e.g., `_briefing.md`, `_log.md`, `_meta.yaml`)
- Source notes within projects: stored in `sources/` subdirectory

**Directories:**
- Vault PARA tiers: numeric prefix + kebab-case (`00-Projects/`, `01-Areas/`, etc.)
- System files: underscore prefix (`_system/`)
- Skill namespaces: `brain.*` (vault operations), `worker.*` (autonomous tasks), `telos.*` (goal alignment)

**Classes/Functions:**
- Classes: `PascalCase` (e.g., `CostLedger`, `Extractor`, `Filer`, `RipgrepRetriever`)
- Functions: `snake_case` (e.g., `query_vault`, `score_alignment`, `write_lint_report`)
- Frozen dataclasses for all result types (e.g., `ExtractionResult`, `IngestResult`, `CostGate`, `TrustDecision`)

## Where to Add New Code

**New vault skill (Hermes-callable):**
1. Create `skills/<namespace>.<name>/` directory
2. Add `SKILL.md` with frontmatter (`name:`, `description:`), triggers, inputs, outputs, cost/trust constraints
3. Add a thin Python script that imports from `ultra_brain` and exposes a CLI interface
4. Add `prompts/` subdirectory for LLM prompt templates
5. Register the skill name in `deploy/hermes/config.yaml` under `skills.load`

**New business logic module:**
1. Add `ultra_brain/<module>.py` with stdlib-only imports
2. Every public function that calls `llm.complete()` must wrap in `try/except Exception` with a heuristic fallback
3. Add result types as frozen dataclasses
4. Wire into `ultra_brain/__main__.py` as a new subcommand
5. Add tests in `tests/test_core.py`

**New cron job:**
1. Add entry to `deploy/cron/ultra-agents-brain.cron` using `python3 -m ultra_brain` or a script under `scripts/`
2. Document the schedule in `deploy/hermes/config.yaml` under `cron.jobs` (reference only; actual scheduling is via the cron file)

**New vault note type (frontmatter schema):**
1. Add the schema to `vault/CLAUDE.md` under "Frontmatter Schemas"
2. Add the `type` value to the allowed `type` list in the Field Conventions section
3. Update `ultra_brain/ingest.py` `Filer.file()` if the new type needs special filing logic
4. Update `ultra_brain/lint.py` `run_lint()` if the new type needs lint rules

**New TELOS goal document:**
- Location: `vault/_system/telos/` (e.g., `mission.md`, `quarter-goals.md`, `dont-do.md`)
- Read by: `telos.score_alignment()` at `ultra_brain/telos.py:71–77`

**Utilities:**
- Shared Markdown helpers: `ultra_brain/markdown.py`
- Shared CLI wrappers for skills: `skills/common/`

## Special Directories

**`vault/_system/`:**
- Purpose: All operational state files for the agent system
- Generated: Partially (log, cost-ledger initialized by `vault.ensure_vault()`; others written at runtime)
- Committed: Yes (append-only; part of the Git-synced vault)

**`graphify-out/`:**
- Purpose: Output from `/graphify` knowledge-graph generation sessions
- Generated: Yes (by graphify skill)
- Committed: Yes (cached graph data and report)

**`.planning/codebase/`:**
- Purpose: GSD codebase map documents consumed by `/gsd:plan-phase` and `/gsd:execute-phase`
- Generated: Yes (by `/gsd:map-codebase` agents)
- Committed: Yes

**`plans/`:**
- Purpose: Agent planning session outputs (high-level feature plans)
- Generated: Yes
- Committed: Yes

---

*Structure analysis: 2026-05-19*
