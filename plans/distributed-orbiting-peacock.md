# Second Brain Overhaul: TELOS → Hygiene → Spec-Driven Shipping

## Context

The `ultra-agents-brain` vault is structurally mature (PARA layout, a `CLAUDE.md`
schema-as-config with frontmatter contracts, `distill_layer`/`telos_relevance` fields,
MOC files) but operationally hollow:

- **TELOS is empty.** `_system/telos.md` and all four sub-docs (`mission`, `quarter-goals`,
  `values`, `dont-do`) are draft skeletons. The `telos_relevance` field exists on every note
  schema but is `null` everywhere because there is nothing to score against.
- **The Inbox is rotting.** ~140 auto-ingested RSS/HN items (2026-05-22 → 05-25) sit unfiled
  and unscored. With no TELOS, "garbage" is undefined, so the monitor firehose just piles up.
- **The brain holds inputs, not outputs.** `00-Projects/` is empty except `daily-briefs/`.
  Your real work (`ultra-agents-brain`, `ultra-workshop`) lives in code repos, disconnected
  from the brain. A "leverage multiplier" brain with zero projects in it is a read-it-later pile.
- **The spec bridge does not exist.** `agentos/workshop_registry.py` is just a GitHub repo
  list (one test repo). There is no brain→spec→ship pipeline.

This plan fixes the dependency chain at its root (TELOS), cleans current state (inbox sweep),
codifies the steady state (operating manual + automation loops), and builds the brain→workshop
spec bridge — turning the brain into the leverage multiplier it's meant to be.

**This is large and sequenced, not parallel.** Phases build on each other. Phase 1 (TELOS)
unblocks everything.

## Decisions Locked (from grilling)

| Branch | Decision |
|---|---|
| Mission | **Leverage multiplier** — brain → spec-driven shippable software output |
| Q2 Goals | (1) Ship ultra-agents-brain v2.0; (2) Make ultra-workshop spec-driven; (3) Brain hygiene + automation. **Public presence is NOT a Q2 goal.** |
| Don't-do | CS esoterica, general news/politics, off-thesis tech = **negative priors**, not deletion rules |
| Ingestion model | **Ingest everything → score `telos_relevance` → surface only high → keep rest searchable** |
| Values | signal>volume · shippable>interesting · compounding>disposable · automate-boring/gate-risky |
| Existing inbox | **Score + sweep**: promote high-relevance, bulk-archive rest to `03-Archives` (no deletion) |
| Email/Calendar/LinkedIn | **Deferred to v2.1.** Design documented only — they serve public presence (not a Q2 goal) |
| Spec bridge | **Both**: persistent per-repo graph (codebase-memory-mcp) + a Brief→SPEC.md generator |
| Automation loops | Daily auto-triage · Weekly gated review · Monthly TELOS recheck · Project-mirror sync |
| Briefing home | `_system/operating-manual.md` (playbook) alongside existing `CLAUDE.md` (data contract) |

---

## Phase 1 — Fill TELOS (the keystone)

Everything downstream scores against this. Write real content into the existing skeletons.

**Files (vault, via obsidian write tools):**
- `_system/telos/mission.md` — Mission: *"Build a centralized source of truth that turns
  everything I read and learn into spec-driven, shippable AI products and features — so I ship
  faster and better than a team."* Refine wording with the user before committing.
- `_system/telos/quarter-goals.md` — Q2 2026, made **measurable**:
  - G1: Ship ultra-agents-brain v2.0 (approvals, evals, memory, knowledge surfaces complete + on VPS).
  - G2: ultra-workshop spec-driven — brain→SPEC→ship working end-to-end on ≥1 real feature.
  - G3: Brain hygiene — inbox ≤10 at weekly close; ≥80% of new items auto-scored.
- `_system/telos/values.md` — the four values above, each with a one-line "in practice" rule.
- `_system/telos/dont-do.md` — esoterica / general-news / off-thesis lists as **negative
  scoring priors** (not auto-delete). Note the ingest-everything-filter-later model explicitly.
- `_system/telos.md` — flip `status: draft` → `active`; keep `privacy: personal`.

**Reuse:** `ultra_brain/telos.py` + `skills/telos.interview/` already implement a guided
interview (`python3 -m ultra_brain --vault <vault> telos-interview`). Option A: run that
interactively to populate. Option B: write the agreed content directly (faster, we already
grilled the answers). **Recommend B** — we have the answers; reserve the interview tool for
future quarterly refreshes.

**Verify:** `telos.check` skill / `ultra_brain telos` reports TELOS as `active` with all four
sub-docs non-empty. Confirm `telos_relevance` scoring has a target to read.

---

## Phase 2 — Score + sweep the existing inbox

One-time batch over the ~140 items, then the inbox is clean.

**Mechanic:**
1. Score every `Inbox/*.md` for `telos_relevance` (0.0–1.0) against the now-filled TELOS,
   applying don't-do negative priors.
2. **Promote** high-relevance (≥ threshold, e.g. 0.6) to `02-Resources/<kind>/` (articles,
   papers) with `status: ingested` and `para_tier` updated; set `distill_layer: 0`.
3. **Sweep** the rest to `03-Archives/inbox-sweep-2026-05/` untouched (searchable, reversible).
4. Log the batch in `_system/log.md` (append-only format already defined in CLAUDE.md).

**Reuse:** `ultra_brain/ingest.py` (filing logic, frontmatter), `ultra_brain/lint.py`
(schema validation), the filing decision tree in vault `CLAUDE.md`. Add a `score`/`sweep`
subcommand or a one-shot script under `scripts/` rather than new long-lived modules.

**Verify:** `Inbox/` contains only `MOC.md` + `README.md` after the sweep; archived count +
promoted count = original count (no data lost); `_system/log.md` has the batch entry.

---

## Phase 3 — Write `_system/operating-manual.md` (the briefing)

The durable playbook. Human- and agent-readable. Complements `CLAUDE.md` (which stays the
machine data contract). Sections, each backed by the research:

1. **Purpose & TELOS** — mission, goals, how `telos_relevance` gates everything. *(Miessler
   TELOS: load as first context; every project traces to a goal; archive un-traced items.)*
2. **The ingestion pipeline** — ingest-everything → score → surface-high → keep-searchable.
   Don't-do negative priors. *(Forte CODE: capture by relevance, distill before filing.)*
3. **Distillation ladder** — activate the existing `distill_layer` 0→3 (raw→highlighted→
   summarized→executive). *(Progressive Summarization — keep ~10–20% per layer, non-destructive.)*
4. **Navigation** — keep MOC.md files current per area so agents grasp a topic fast.
   *(LYT/MOC beats raw Zettelkasten for AI navigability; write Statements, not just Things.)*
5. **Operating cadence** — the four loops (Phase 5), what's autonomous vs HITL-gated.
6. **Brain↔code bridge** — how repos enter the brain and how specs come out (Phase 4).
7. **Decision memory** — adopt ADRs in `docs/adr/` per repo; mirror decisions into the brain;
   "one PR = one code change + one knowledge update." *(Stale decision log is worse than none.)*
8. **Spec discipline** — every shippable unit starts as a SPEC.md (typed interfaces, EARS
   acceptance criteria, a code-style example, explicit Always/Ask-First/Never rails).
   *(GitHub Spec Kit, AWS Kiro, Amazon PRFAQ; Addy Osmani spec guidance.)*
9. **Hygiene rules** — `CLAUDE.md` stays <200 lines; prune monthly; weekly vault-health check
   (orphans, projects w/o next action, ADRs w/o matching code).
10. **Deferred (v2.1)** — email/calendar (read-only daily pull via `google-workspace` MCP),
    LinkedIn (no clean API; revisit only when public presence becomes a goal).

**Verify:** Manual exists, links to TELOS and CLAUDE.md, scannable in <5 min, contains the
cadence table and the spec checklist.

---

## Phase 4 — Brain → ultra-workshop spec bridge

Two layers (decision: build both).

### 4a. Persistent per-repo graph (context layer)
- **Keep `codebase-memory-mcp`** as the primary engine — deterministic AST graph, 90% file
  coverage, ~10x token savings vs file-exploration; LLM-extracted graphs miss ~36% of files
  and hallucinate APIs. This is the correct architecture for accurate spec context.
- **Close its one gap:** add a `.git/hooks/post-commit` that triggers reindex (polling watcher
  misses the commit boundary). 10-minute fix, per registered repo.
- **Bridge to vault:** post-reindex script writes the graph's `get_architecture` summary to
  `vault/repos/<repo-name>/ARCHITECTURE.md` so both code-structure and notes are queryable in
  one agent session.
- **Evaluate (not commit) augmenting tools:** `code-graph-mcp` (sdsrss) — only OSS tool with
  HTTP route→handler→service→DB tracing, valuable for the agentos API repo; `repowise` —
  combines code graph + git history + ADR tracking, markdown output feeds the vault.

### 4b. Brief → SPEC.md generator (handoff artifact)
- New brain skill / `ultra_brain` subcommand: input = a goal + linked concepts/entities/sources
  + the target repo's `ARCHITECTURE.md`; output = a structured `SPEC.md` that ultra-workshop's
  `/build` consumes directly.
- SPEC.md shape (research-backed): problem & context · in-scope/out-of-scope · typed interfaces
  · EARS-style acceptance criteria · references (wikilinks + repo paths) · Always/Ask-First/Never
  rails · a code-style example snippet.
- **Reuse:** existing `type: briefing` frontmatter schema and the `00-Projects/<slug>/_briefing.md`
  shape already defined in `CLAUDE.md`. The generator produces a briefing that hardens into a SPEC.

**Reuse:** `agentos/workshop_registry.py` (repo registry — extend, don't replace),
`agentos/knowledge.py` (PgVector retrieval for pulling linked sources).

**Verify:** Pick one real feature on `test-workshop-sandbox` or a v2.0 task → generate SPEC.md
from brain → confirm ultra-workshop `/build` can consume it → graph stays fresh after commit
(post-commit hook fires, ARCHITECTURE.md updates).

---

## Phase 5 — Automation loops

Codify the four loops; align with existing crons/skills (`worker.monitor`, `brain.express`,
daily-briefs, `weekly-review.md`).

1. **Daily auto-triage** *(extend `worker.monitor` + `brief.py`)* — ingest → TELOS-score →
   auto-file high-relevance to Resources, leave low flagged in Inbox; daily brief surfaces only
   top-N. Zero manual touch on the firehose.
2. **Weekly review (gated)** *(populate `_system/weekly-review.md` + Telegram HITL)* — agent
   drafts: what came in, inbox count, stale projects, suggested promotions/archives → you
   approve the sweep via Telegram. Boring work automated, decisions gated.
3. **Monthly TELOS recheck** — re-score open projects vs TELOS, flag drift ("goal X untouched"),
   propose goal updates. Keeps the relevance filter honest.
4. **Project-mirror sync** — when a repo enters `workshop_registry`, auto-create
   `00-Projects/<repo>/` with `_briefing.md` / `_log.md` / `_meta.yaml` (shapes already in
   `CLAUDE.md`) so the brain holds outputs, not just inputs.

**Reuse:** `ultra_brain/monitor.py`, `brief.py`, `review.py`, `express.py`; the gated-approval
HITL path already exists (Phase 14 approvals surface). Loops are cron + existing modules, not
new infra.

**Verify:** Each loop runnable on demand; daily brief shows only high-relevance; weekly review
produces a Telegram-approvable draft; adding a repo to the registry creates its `00-Projects/`
mirror.

---

## Sequencing & dependencies

```
Phase 1 (TELOS) ──┬── Phase 2 (inbox sweep)   ← needs TELOS to score
                  ├── Phase 3 (operating manual) ← documents the rest
                  └── Phase 5 (loops)           ← needs TELOS + manual
Phase 4 (spec bridge) ── independent of 1–3; gated by codebase-memory-mcp post-commit hook
```

Phase 1 first. Phases 2/3 next. Phase 4 can run in parallel with 2/3. Phase 5 last (it wires
everything into cadence).

## Out of scope (explicit)

- Email / Calendar / LinkedIn ingestion or drafting — **v2.1** (design captured in manual §10).
- Migrating off `codebase-memory-mcp` — research says keep it; only augment.
- GitNexus / Potpie / Sourcegraph adoption — revisit later; wrong fit / too early now.
- Hard-deleting any inbox content — always archive, never delete.

## Verification (end-to-end)

1. `ultra_brain telos` → TELOS `active`, four sub-docs filled.
2. `Inbox/` reduced to MOC + README; archive+promote counts reconcile; log entry present.
3. `_system/operating-manual.md` exists, links TELOS + CLAUDE.md, has cadence table + spec checklist.
4. codebase-memory-mcp reindexes on commit; `vault/repos/<repo>/ARCHITECTURE.md` written.
5. One SPEC.md generated from brain and consumed by ultra-workshop `/build` on a real feature.
6. Daily/weekly/monthly loops each produce their artifact; new repo auto-mirrors to `00-Projects/`.

## Research appendix

Full sourced briefs saved by research agents:
- Second-brain shipping practices: `plans/distributed-orbiting-peacock-agent-a01d96540a27477f5.md`
- Code→graph tooling benchmark: returned inline (codebase-memory-mcp arXiv 2603.27277; SDD via
  GitHub Spec Kit / Kiro; TELOS via Miessler PAI; Progressive Summarization / LYT-MOC; ADRs).
