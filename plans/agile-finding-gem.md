# Impact Assessment: Adopting `obsidian-second-brain` (d.1) on ultra-agents-brain

## Context

You're choosing how to integrate your canonical Obsidian vault (`~/Documents/second-brain`) into Claude Code workflows. Three decisions are already locked:

- **D1 — Scope: global** (user-scope MCP, accessible from every CC project)
- **D2 — Write semantics: manual** (Claude only writes on explicit invocation; no autonomous/scheduled writes)
- **D3 — Architecture: filesystem MCP via `@bitbonsai/mcpvault`** (registered, connected)
- **D4 — Canonical path: `~/Documents/second-brain`** (project's drifted `vault/` deleted, replaced with symlink)

The remaining decision (D8/D7) is workflow surface. You indicated interest in option **(d.1) Full adoption of `eugeniughelbur/obsidian-second-brain` skill**, which would replace your PARA convention with the skill's wiki-style schema (`Daily/`, `People/`, `Projects/`, `Tasks/`, `Ideas/`, `wiki/`, `raw/`, etc.) and adopt its philosophy (atomic notes, mandatory `## For future Claude` preamble, `ai-first: true` frontmatter, `timeline:` arrays, recency markers).

You asked: **if d.1 is chosen, how does it affect the existing agents in this project?** This document answers that question precisely.

## Verdict (TL;DR)

**d.1 requires a major refactor of ultra-agents-brain.** Roughly 9 source files in `ultra_brain/`, 4 agent factories in `agentos/`, 2 test files, 2 eval datasets, 2 shell scripts, and the vault schema-as-config file all need to be rewritten. The current code has ~30 hardcoded PARA path literals and ~16 frontmatter fields it produces or consumes. The skill's schema is incompatible with all of them.

I estimate **1–2 weeks of focused work**, with material risk of regressing the v1.5 milestone that was just verified. The Phase 7 eval baselines (freshly frozen) would all need to be re-baselined.

**Strong recommendation: do not pick d.1.** Pick **d.4** (keep MCP + your PARA vault + the existing `obsidian-vault` skill). Detailed reasoning below.

## Impact Inventory — exactly what breaks

### 1. `ultra_brain/` core capability layer (9 modules touched)

| Module | Coupling | Refactor scope |
|---|---|---|
| `vault.py` | `VAULT_DIRS` constant encodes entire PARA tree; `ensure_vault()` creates it | Rewrite `VAULT_DIRS` for new schema (Daily/, People/, Projects/, Tasks/, Ideas/, Boards/, Dev Logs/, Reviews/, Knowledge/, wiki/, raw/, Research/); rewrite `SYSTEM_FILES` |
| `ingest.py` | `_VALID_TIERS = {"00-Projects", "01-Areas", "02-Resources", "Inbox"}`; tier-resolution routing; hardcodes `02-Resources/articles/`, `00-Projects/ad-hoc-research/`, `01-Areas/ai-tooling-landscape/entities/` | Rewrite routing logic; remap to skill-compatible destinations (`Research/Web/`, `Knowledge/`, `People/`); rewrite the 16-field frontmatter producer to add `ai-first: true`, `## For future Claude` preamble, `timeline:` arrays |
| `research.py` | Creates `00-Projects/<slug>/{sources,entities,concepts}/`, `synthesis.md`, `_briefing.md`, `_meta.yaml` | Remap to `Projects/<slug>/` or `Research/Deep/<slug>/`; preserve subagent fan-out |
| `review.py` | Reads `00-Projects/*`, `01-Areas/*`; writes `_system/weekly-review.md` | Remap to `Projects/*`, no clear equivalent for `01-Areas/*`; possibly drop area reviews; rewrite output path to `Reviews/YYYY-MM-DD — Weekly Review.md` |
| `monitor.py` | Writes to `Inbox/`; dedup store at `_system/monitor-seen.json` | Remap to skill's RSS destination (likely `Inbox/` survives, but `_system/` may need to move to vault root) |
| `lint.py` | Validates frontmatter `type`, `source_url`, `distill_layer` | Rewrite to validate skill's mandatory fields (`ai-first`, `date`, `tags`, preamble presence, `timeline:` shape on people notes) |
| `express.py` | Reads `_system/log.md`, `_system/cost-ledger.md`; reads `{project}/_briefing.md` | Remap project briefing path |
| `telos.py` | Reads `_system/telos.md`, `_system/telos/{mission,quarter-goals,dont-do}.md` | Skill has no telos concept; either keep `_system/` carve-out OR migrate telos to skill's `Knowledge/Telos/` and rewrite all references |
| `trust.py` | Path-prefix classifier for `01-Areas/`, `_system/`, `03-Archives/` | Rewrite classifier with new prefixes |

### 2. `agentos/` agent layer (4 agents code-affected, 6 prompts affected)

| Agent | Code change | Prompt change |
|---|---|---|
| `ingest` | New routing destinations via rewritten `Filer` | Update agent instructions to reference new paths |
| `query` | None (rglob is schema-agnostic) | Update citations format if changed |
| `chat` | None (delegates to query) | Update example queries |
| `research` | New project directory layout via rewritten `aggregate_research` | Update instructions |
| `curator` | New `_system/*` paths if migrated; reads/writes `weekly-review`, `lint-report`, `monitor-seen.json` | Update digest format |
| `supervisor` | None (delegates) | None |

Plus: `agentos/cost.py` hardcodes `_system/cost-ledger.md`. `agentos/tools/vault.py` has a known bug calling `monitor.run_poll(vault_root=VAULT_ROOT)` without `feeds_yaml` — that bug would need to be fixed during migration anyway.

### 3. Tests, evals, scripts

**`tests/test_core.py`** — 5 explicit path assertions break:
- `vault / "_system" / "cost-ledger.md"` (line 24)
- `vault / "_system" / "log.md"` (line 39)
- `vault / "02-Resources" / "articles" / "bad.md"` (line 80)
- `_system / "telos" / {sessions.json, mission.md}` (lines 91–97)
- `vault / "00-Projects" / "demo"` (line 115)

**`evals/datasets/ingest_cases.py`** — 2 cases break:
- `ingest-1`: `expected_note_path_prefix: "vault/02-Resources/articles/"`
- `ingest-3`: `expected_note_path_prefix: "vault/Inbox/"`

Phase 7 baselines (just frozen on commit `5ee8bef`) would need to be re-baselined for everything that touches placement.

**`scripts/lint-check.sh`** — hardcodes `$SECOND_BRAIN_DIR/_system/lint-report.md`
**`scripts/cost-check.sh`** — hardcodes `$SECOND_BRAIN_DIR/_system/cost-ledger.md`

### 4. Vault content migration

44 existing notes in `~/Documents/second-brain` need to be:
- Moved to new folder homes (most PARA-tier content doesn't have a clean 1:1 mapping to skill schema)
- Rewritten to add mandatory frontmatter (`ai-first: true`, `date`, mandatory preamble)
- People notes need fabricated `timeline:` arrays
- External claims need recency markers `(as of YYYY-MM, source-url)`
- The existing `vault/CLAUDE.md` schema-as-config must be retired or merged with the skill's `_CLAUDE.md` convention

### 5. Schema-as-config collision

This is the deepest structural conflict. `vault/CLAUDE.md` is **already** ultra-agents-brain's schema-as-config — it declares the frontmatter contract that ingest produces and lint validates. The skill expects `_CLAUDE.md` at vault root with its own conventions. You'd be running two schema authorities at once. Resolution requires either:
- Retiring ultra-agents-brain's schema (effectively rewriting every reference to it in agent code), OR
- Forking the skill to use your schema (defeating most of its value)

### 6. Drift between skill semantics and your existing code

Even if you adopt the schema, the skill has habits your code doesn't share:
- Skill propagates ingest across 5–15 pages (subagent fan-out updates People/, Projects/, Ideas/, Knowledge/). Your `ingest` only writes the source note + entity stubs + log line.
- Skill writes `## For future Claude` preambles on every note. Your code doesn't, and the lint rule would need to be added (and existing notes backfilled).
- Skill uses `Knowledge/ADR-YYYY-MM-DD — Title.md` for ADRs. You have no ADR concept in agent code.

## Recommendation: pick d.4

`obsidian-second-brain` is genuinely impressive, but it is **a complete, opinionated system** designed to be the only vault tooling in play. ultra-agents-brain is **also** a complete, opinionated system with its own schema, its own agents, and its own tests. Running both means rewriting one to match the other — a strictly negative-sum trade given v1.5 just shipped verified.

The narrower path that respects what you've already built:

### d.4 in concrete terms

1. **Keep mcpvault MCP** (already registered, ✓ Connected). It's the read+write surface for casual Claude-Code-anywhere queries against the brain.
2. **Keep `obsidian-vault` skill** (mattpocock — already installed). Lightweight slash commands; doesn't impose a schema.
3. **Keep ultra-agents-brain's existing 6 agents and PARA schema** intact. They are tested, eval'd, and verified.
4. **Borrow good ideas from `obsidian-second-brain` selectively** as future enhancements to your existing agents, without adopting the skill:
   - **Recency markers** `(as of YYYY-MM, source-url)` — add to your lint rules as an `info` finding for `type: article|paper` notes.
   - **Bi-temporal `timeline:` frontmatter** — add for entity notes under `01-Areas/*/entities/` when you have person notes (low value until you actually track people in the vault).
   - **`## For future Claude` preamble** — add as an optional template for ingest output, gated by a CLI flag (`--ai-first-preamble`).
   - These are individually small changes, can be added one at a time, and don't require migration.
5. **Address the known anomalies discovered during this analysis** as separate fixes:
   - `agentos/tools/vault.py:107` `poll_feeds` calls `monitor.run_poll(vault_root=...)` missing required `feeds_yaml` arg — fix.
   - `telos.interview` path split between `_system/telos-sessions.json` (CLI) and `_system/telos/sessions.json` (skill script) — reconcile.
   - `ingested_at` written as date-only by ingest but declared as datetime+Z in `vault/CLAUDE.md` — reconcile (probably fix the code to write ISO datetime).
   - `02-Resources/papers/`, `books/`, `prompts/` created by `ensure_vault` but never written to by ingest — either route to them or drop them.

## Files referenced

**ultra_brain core** (any change to schema touches all of these):
- `ultra_brain/vault.py` (`VAULT_DIRS`, `ensure_vault`)
- `ultra_brain/ingest.py` (`Filer`, `_VALID_TIERS`, tier routing)
- `ultra_brain/research.py` (`aggregate_research`)
- `ultra_brain/review.py` (`write_weekly_review`)
- `ultra_brain/monitor.py` (`run_poll`)
- `ultra_brain/lint.py` (`write_lint_report`)
- `ultra_brain/express.py`
- `ultra_brain/telos.py` (`score_alignment`, `TelosSessionStore`)
- `ultra_brain/trust.py`
- `ultra_brain/__main__.py` (CLI dispatch)

**agentos agent layer**:
- `agentos/agents/{ingest,query,chat,research,curator,supervisor}.py`
- `agentos/cost.py`
- `agentos/tools/vault.py`
- `agentos/schemas.py` (Pydantic output schemas — would need new fields under d.1)

**vault schema-as-config**:
- `~/Documents/second-brain/CLAUDE.md` (symlinked from `vault/CLAUDE.md`)

**tests/evals/scripts that assert paths**:
- `tests/test_core.py` (5 path assertions)
- `evals/datasets/ingest_cases.py` (2 cases with `expected_note_path_prefix`)
- `scripts/lint-check.sh`, `scripts/cost-check.sh`

## Verification — how to know this assessment is correct

If you want to validate the impact map yourself before deciding:

1. **Confirm the hardcoded-path inventory** — run `grep -rn -E '(00-Projects|01-Areas|02-Resources|03-Archives|Inbox|_system)' ultra_brain/ agentos/ tests/ evals/ scripts/ --include='*.py' --include='*.sh' --include='*.md'`. You should see roughly 30+ matches across the files listed above.
2. **Confirm the frontmatter-field inventory** — `grep -rn -E '(distill_layer|telos_relevance|para_tier|ingested_at|ingested_via|content_hash|source_url|canonical_url)' ultra_brain/ agentos/ --include='*.py'`. Each of these fields is produced by code; adopting the skill would either drop them (and lose lint coverage) or require dual-schema notes.
3. **Run the existing test suite** — `PYTHONPATH=. python -m pytest tests/test_core.py -v`. Should pass on current schema. Under d.1 these 5 path assertions would need rewrites and the baselines re-frozen.
4. **Skim `~/Documents/second-brain/CLAUDE.md`** — note that it is *already* a schema-as-config file (not just docs). The skill's `_CLAUDE.md` convention would replace or compete with it.

## Direction locked: d.4

User selected **d.4 — keep PARA + MCP** after seeing the impact assessment. d.1 deferred indefinitely (not even scoped as v2.0 unless interest returns). d.1-lite borrowings can be filed as individual feature tickets later but are not in this scope.

## Remaining decisions (resumed grilling, outside plan mode)

Three small decisions left to lock. None require code changes to ultra-agents-brain — they're configuration and habit decisions.

### D5 — Write safety guardrails

mcpvault already ships safety primitives (symlink-escape blocking, YAML-frontmatter-corruption prevention, soft-delete to `.trash/`). The remaining question is whether to add ANY additional guardrails on top:

- **Option α (recommended)**: rely on mcpvault's built-ins + canonical vault's git auto-sync as rollback. No extra guardrails. Every vault commit is auto-synced to `github.com:caiobellizzi/second-brain`, so any accidental write is recoverable via `git revert` or hand-edit.
- **Option β**: add a pre-write git snapshot via a Claude Code hook (PreToolUse on `mcp__obsidian__write_note|patch_note|delete_note`). Heavier; mostly redundant with auto-sync; not worth it unless we want point-in-time rollback granularity finer than the 4-hour sync cadence.

### D6 — Search strategy

- mcpvault ships BM25-style search with relevance ranking — covered.
- Claude Code's built-in Read/Grep/Glob also work transparently through the symlink — covered.
- The open question: do we add **semantic search** (e.g., Nooscope sidecar with local Ollama embeddings)?

Recommended: **defer**. BM25 + grep covers ~90% of "where did I write about X" queries. Local embedding sidecar adds operational complexity (Ollama daemon, embedding refresh cadence, vector DB at `nooscope.db`) for diminishing returns until the vault grows past ~500 notes. Revisit at that scale.

### D7 — Workflow surface

Three small additions to consider on top of the existing surface (`obsidian-vault` skill + MCP):

1. **`/save-session --to-vault` enhancement** — extend the existing `/save-session` skill to optionally write a curated session summary into `~/Documents/second-brain/02-Resources/sessions/YYYY-MM-DD-slug.md` when invoked with that flag. Out of scope for tonight; file as feature ticket.
2. **A new vault-aware `/capture` shortcut** — already mostly covered by `obsidian-vault` skill's existing commands. No new tooling needed.
3. **claude-mem ↔ vault bridge** — leave alone. Claude-mem and vault stay separate per the (b) coexistence model: claude-mem for ambient session capture, vault for curated knowledge.

Recommended: **no new tooling tonight**. File the `/save-session --to-vault` enhancement as a single feature ticket. Habituate using the new MCP for a week before adding any extra surface.

## Verification — how to confirm the implementation is correct

End-to-end verification of the work already executed (D1–D4 + symlink + MCP):

1. **Symlink resolution** — `readlink /Users/caiobellizzi/Documents/Projects/ultra-agents-brain/vault` should print `/Users/caiobellizzi/Documents/second-brain`.
2. **Code reads through symlink** — `head -3 /Users/caiobellizzi/Documents/Projects/ultra-agents-brain/vault/CLAUDE.md` should match the canonical's CLAUDE.md.
3. **git-sync neutrality** — `bash scripts/git-sync.sh pull` (with `VAULT_VPS_PATH=~/Documents/second-brain`) should run cleanly.
4. **MCP connectivity** — `claude mcp list | grep obsidian` should show `✓ Connected`.
5. **Cross-project smoke test (D8/Step 8)** — `cd ~ && claude` (fresh CC session in any directory). In that session, ask Claude to "use the obsidian MCP to read the title from 02-Resources/MOC.md". Should resolve and return the canonical vault's MOC content.
6. **Tests still green** — `PYTHONPATH=. python -m pytest tests/test_core.py -v` should pass (PARA paths intact through the symlink).
7. **Evals still green** — `PYTHONPATH=. python -m pytest evals/ -v` should match frozen baselines.

If all 7 pass, the second-brain integration is complete under d.4.
