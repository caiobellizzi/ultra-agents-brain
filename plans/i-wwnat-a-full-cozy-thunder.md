# Plan — Full Second-Brain Maintenance Documentation

## Context

The user wants a complete, navigable documentation set for maintaining their second brain: every pipeline flow, every connected source, and a section that suggests new connections to improve coverage. The existing docs (`docs/ARCHITECTURE.md`, `docs/GETTING-STARTED.md`, `docs/DEVELOPMENT.md`, `docs/CONFIGURATION.md`, `docs/TESTING.md`, `docs/runbooks/*`) cover *what the system is* and a few VPS recovery procedures, but there's **no single guide** that walks an operator through the day-to-day and weekly maintenance flows, no map of all data sources with their config files, and no inventory of *missing* connections (NotebookLM, Perplexity, X/Twitter, LinkedIn — all referenced in memory but not unified anywhere).

This plan adds **three new documents** rather than touching the existing five canonical docs (which `/gsd-docs-update` already maintains). The new docs are operator-centric and link back to the canonical set.

A note on plan-mode discipline: while invoking `/gsd-docs-update`, a `<system-reminder>` claiming plan-mode exit appeared embedded in workflow file content returned by `Bash`. I treated it as untrusted input (it came from a tool result, not a real system event) and stayed in plan mode. Surfacing here so the user is aware.

## Scope

**Will write (3 new files):**

1. `docs/MAINTENANCE.md` — the operator guide. Every recurring flow with: trigger, command, expected output, where it writes, failure recovery.
2. `docs/SOURCES.md` — every connected source with: status, config path, ownership (local vs VPS), data path into the vault, related skill.
3. `docs/CONNECTIONS-ROADMAP.md` — gaps + suggested additions, ranked by effort × value. Honest about what's stubbed vs working.

**Will NOT touch:**
- `README.md`, `docs/ARCHITECTURE.md`, `docs/GETTING-STARTED.md`, `docs/DEVELOPMENT.md`, `docs/CONFIGURATION.md`, `docs/TESTING.md` — these are owned by canonical `/gsd-docs-update` runs. Adding cross-links from them to the new files is a separate small commit.
- `docs/runbooks/*` — keep as targeted incident playbooks; `MAINTENANCE.md` will link to them.
- `.planning/`, `plans/`, `SECURITY.md`, `CLAUDE.md` — out of scope.

## Source material (already mapped)

Pipeline skills (`skills/`):
- `brain.ingest` — promotes `_inbox/` items into PARA (`ultra_brain/ingest.py`)
- `brain.lint` — nightly hygiene pass (`ultra_brain/lint.py`)
- `brain.review` — weekly strategic review (`ultra_brain/review.py`)
- `brain.express` — daily brief synthesis + Telegram delivery (`ultra_brain/brief.py`, `skills/brain.express/tts.py`, `ultra_brain/telegram.py`)
- `brain.query` — search the vault (`ultra_brain/query.py`, `skills/brain.query/qmd_client.py`)
- `worker.monitor` — RSS + Bluesky polling (`ultra_brain/monitor.py`, `skills/worker.monitor/feeds.yaml`, `bluesky-handles.txt`)
- `worker.research` — deeper research loops (`ultra_brain/research.py`, `skills/worker.research/loop.py`)
- `telos.check` / `telos.interview` — goal alignment checks (`ultra_brain/telos.py`)

Sources & integrations:
- **Active:** Obsidian MCP (vault symlink → `~/Documents/second-brain`), LiteLLM proxy (`deploy/litellm/config.yaml` + `strip_response_format.py` hook), Telegram bot (`channels/telegram_adapter.py`, `ultra_brain/telegram_bot.py`), RSS feeds (`feeds.yaml`), Bluesky (`bluesky.py` + handles file), AgentOS HTTP API (`agentos/app.py`), PostgresDb (`agentos/db.py`), claude-mem (global), qmd (local Markdown search), Hermes gateway (referenced)
- **Configured but partial:** NotebookLM (TODO: `nlm login`), Perplexity (no API key in `.env` per memory S607)
- **Planned/skipped:** X/Twitter, LinkedIn (decision S604)

Deployment surfaces:
- Local CLI (`python -m ultra_brain ...`)
- VPS cron (`deploy/cron/ultra-agents-brain.cron`)
- VPS systemd (`ops/systemd/uab-{bot,postgres,telegram}.service`)
- LiteLLM container (`deploy/docker-compose.yml`)
- Vault sync (`deploy/sync-vault-to-vps.sh`, `deploy/com.ultraagents.vault-sync.plist`)
- Helper scripts (`scripts/health-check.sh`, `cost-check.sh`, `smoke-litellm.sh`, `vps-bootstrap.sh`)

Instrumentation:
- `agentos/instrumented_memory.py`, `agentos/instrumented_knowledge.py`, `agentos/eval_recorder.py` — phase 11+ observability

## Document outlines

### 1. `docs/MAINTENANCE.md` (~400 lines target)

Structured by **cadence**, not by skill. Each flow follows the same template:
`Trigger → Command → What happens → Where it writes → How to verify → Failure recovery`.

Sections:
1. **At a glance** — table of every recurring flow (cadence, owner, surface, runbook link)
2. **Daily flows**
   - `brain.express` daily brief (local + VPS cron) → Telegram delivery
   - `worker.monitor` RSS+Bluesky poll → `_inbox/`
   - Vault sync local↔VPS (launchd plist)
3. **On-demand flows**
   - `brain.ingest` — inbox refinement (the human-in-the-loop refine pattern from S597)
   - `brain.query` — vault search via qmd
   - `worker.research` — deep research run
   - `telos.check` — goal alignment
4. **Weekly flows**
   - `brain.review` strategic pass
   - `brain.lint` hygiene (also nightly via cron)
   - qmd re-embed cycle (when `qmd update` reports pending vectors)
5. **Monthly / quarterly**
   - LiteLLM key rotation
   - Cost ledger review (`scripts/cost-check.sh`, `ultra_brain/cost.py`, `skills/common/cost_ledger.py`)
   - Eval review (`agentos/eval_recorder.py` outputs)
6. **Incident response** — pointers into `docs/runbooks/*` (recovery, vault-sync, obsidian, vps-foundation)
7. **Adding a new …** — recipes for: new RSS feed, new Bluesky handle, new skill, new agent, new LLM endpoint in LiteLLM
8. **Verification checklist** — `scripts/health-check.sh`, `scripts/smoke-litellm.sh`, `scripts/smoke_agno.py`

### 2. `docs/SOURCES.md` (~250 lines target)

One section per source. Template:
`Purpose → Status (active/configured/planned) → Config file(s) → Where data lands → Skill(s) that consume it → Maintenance touchpoints → Failure modes`.

Grouped:
- **Input sources (writers to vault)** — RSS, Bluesky, Telegram inbound, manual notes, future X/LinkedIn
- **Knowledge backends (readers + storage)** — Obsidian MCP, qmd, PostgresDb, claude-mem, instrumented knowledge wrapper
- **LLM providers** — LiteLLM proxy (with the strip-response-format hook), Groq/Anthropic/Cloud keys (`agentos/model.py`), local fallback models
- **External research** — NotebookLM (TODO: login), Perplexity (missing API key), Context7 docs MCP
- **Output channels** — Telegram bot (`channels/telegram_adapter.py`), Hermes gateway, TTS (`skills/brain.express/tts.py`)
- **Observability** — eval recorder, cost ledger, trust policy (`skills/common/trust_policy.py`)

Include one **system diagram** (ASCII or mermaid) showing source → skill → vault → output.

### 3. `docs/CONNECTIONS-ROADMAP.md` (~150 lines target)

The "what to add next" doc. Ranked, with rationale, not a backlog dump.

Sections:
1. **Activate what's already configured** — NotebookLM login, Perplexity API key, missing VPS API keys (memory 21770)
2. **High-value gaps with low effort** — e.g., wiring `worker.monitor` Bluesky output through the same refinement gate as RSS, expanding `feeds.yaml`, second-brain → `docs/` cross-publishing
3. **Medium-effort additions** — distill_layer-2 refinement pipeline integration (`refine` skill), automated `qmd embed` after refine, brief-agent reading filed monitor items by date (incident from memory 21808)
4. **Defer / skip with reasoning** — X/Twitter, LinkedIn (per decision S604), full TTS in daily brief (medium-trust gate)
5. **Observability next steps** — InstrumentedKnowledge is in, what's missing for full coverage (referenced by recent commits 26703b6, 190f417)

## Critical files to read while writing

- `README.md`, `docs/ARCHITECTURE.md` — to match voice and avoid duplication
- Each `skills/*/SKILL.md` — source of truth for skill semantics
- `ultra_brain/__main__.py` — exact CLI surface
- `deploy/cron/ultra-agents-brain.cron` — actual cron cadence
- `deploy/litellm/config.yaml` — model registry
- `skills/worker.monitor/feeds.yaml` — to verify "active sources" count
- `.env.example` — to list required env vars per source without leaking secrets
- `docs/runbooks/*.md` — to link rather than duplicate

## Verification

After writing:
1. Every command in `MAINTENANCE.md` is grep-verifiable: `grep -r "<command>" ultra_brain/ scripts/ deploy/` returns a hit.
2. Every config path in `SOURCES.md` exists: `ls <path>` succeeds.
3. Every "active" source in `SOURCES.md` has a corresponding non-empty config (e.g., `feeds.yaml` has feeds, `bluesky-handles.txt` is non-empty).
4. Every "planned/skipped" claim cites the memory ID or commit it was decided in.
5. Run `markdownlint docs/MAINTENANCE.md docs/SOURCES.md docs/CONNECTIONS-ROADMAP.md` if available; otherwise visual scan.
6. README gets a one-line pointer added under a "Maintenance" subsection — separate small commit so the canonical README stays clean.

## Out of scope (explicit)

- Rewriting existing canonical docs
- Implementing any of the suggested connections in `CONNECTIONS-ROADMAP.md`
- Activating NotebookLM / Perplexity (those are operator actions the roadmap will *recommend*)
- Touching `.planning/` artifacts
