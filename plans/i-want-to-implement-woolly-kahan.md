# Self-Evolving Agents — MVP Plan (Phases 1-3)

## Context

Ultra Agents Brain runs 5 Agno specialists (`ingest`, `query`, `research`, `chat`, `curator`) + a supervisor `Team`. Today the agents are static: their prompts, tools, and routing are fixed at code-commit time. The system has no feedback loop — runs succeed or fail but nothing learns from the outcome.

The goal is to add **autonomous self-improvement** without rewriting the stack, without introducing a foreign agent DSL, and without violating the existing HITL trust model. The pattern adopted is **inference-time only**, mapped onto existing infrastructure:

```
Run → AgentAsJudge scores → record_experience tool (HITL) → vault/_system/experiences/*.md
                                                ↓
                                    (a) injected via Agno culture
                                    (b) retrieved before similar tasks
```

**Why this shape:**
- Two `AgentAsJudgeEval` instances already exist in `agentos/agents/query.py` and `chat.py` but are dormant — wiring them is the cheapest first step.
- HITL via `@tool(requires_confirmation=True)` already works through the Telegram adapter (`agentos/channels/telegram_adapter.py`). The same pattern extends naturally to experience recording.
- The vault is the team's natural shared memory. Storing learned "what worked" entries as `vault/_system/experiences/*.md` keeps the second-brain symmetry: agents have a second brain too, and the user can read/edit it.
- Agno's `Culture` system (`update_cultural_knowledge=True`) provides shared-principle persistence natively — no external dependency.

**Frameworks rejected** (with rationale captured here so we don't relitigate):
- **OpenEvolve** — needs numeric ground truth; vault outputs are subjective.
- **EvoAgentX** — requires rewriting all 5 agents into its `Agent` DSL.
- **Letta** — separate server, identity port; too invasive.
- **DSPy/MIPROv2** — kept as deferred Phase 4 (not in MVP); needs ≥50 labeled examples which this plan produces.
- **Sifaka/Reflexion runtime loops** — multiplies inference cost per run without persistent learning.

---

## Phase 1 — Signal Layer (1-2 days)

**Goal:** every agent run is scored and the score is persisted. No improvement yet, just observable quality.

### Changes

**1.1 Wire dormant judges.** Currently defined but unused:
- `agentos/agents/query.py` — `citation_judge` (`AgentAsJudgeEval`) defined inline but never passed to `post_hooks`. Add it.
- `agentos/agents/chat.py` — same situation. Wire it.

**1.2 Add new judges for the remaining agents.** Each judge is a `AgentAsJudgeEval` instance using the `cheap-worker` tier (judges should be cheap and frequent):
- `agentos/agents/curator.py` — `curation_judge` with criteria: "curated note adds value, has correct tags, links to existing notes when relevant."
- `agentos/agents/ingest.py` — `ingest_judge` with criteria: "extracted content faithful to source, frontmatter complete, no dup of existing vault content."
- `agentos/agents/research.py` — `research_judge` with criteria: "report cites sources, conclusions traceable to evidence, no fabrication."

All judges set `threshold=7` (numeric 0-10), `scoring_strategy="numeric"`, `db=db` (writes to existing eval store).

**1.3 Configure `on_fail` to log only.** No automatic mutation in MVP. The callback persists the failure context to the eval store with the full trace; a human can review later.

**1.4 Async judge execution.** Use Agno's background eval mode so judging does not block the user's response.

### Files touched

- `agentos/agents/query.py` — add `post_hooks=[citation_judge]` to `query_agent`
- `agentos/agents/chat.py` — same
- `agentos/agents/curator.py` — define `curation_judge`, add to `post_hooks`
- `agentos/agents/ingest.py` — define `ingest_judge`, add to `post_hooks`
- `agentos/agents/research.py` — define `research_judge`, add to `post_hooks`
- `evals/conftest.py` — verify eval store config still works with hot judges (no code change expected; just smoke test)

### Verification

- Run each agent once via `agentos/main.py` or pytest harness.
- Query the eval store: `SELECT agent_name, score, threshold, passed FROM eval_runs ORDER BY created_at DESC LIMIT 20;`
- Confirm 5 agents × ≥1 run each appear with scores.
- Run `rtk pytest evals/ -m smoke` — must stay green.

---

## Phase 2 — Experience KB in the Vault (3-5 days)

**Goal:** agents record structured "what worked / what failed" entries to the vault as Obsidian notes. Other agents retrieve them before similar tasks. Cross-agent learning realized via the second brain itself.

### Changes

**2.1 Vault directory.** Create `vault/_system/experiences/` (the `_system` namespace is already established in the vault schema per `vault/CLAUDE.md`). Subdirectories per agent: `experiences/{agent_name}/`.

**2.2 Experience note schema.** One `.md` per experience:

```
---
agent: curator
task_type: review_inbox_item
input_summary: "Article on NVIDIA NIM proxy APIs, 8k words"
action_taken: "Promoted to 02-Resources/articles with tags [ai,llm,infra]"
judge_score: 9
judge_notes: "Tags accurate, good link to existing LiteLLM notes"
outcome: success
created: 2026-05-21T20:15:00-03:00
---

## What worked
- Recognizing the LiteLLM connection from existing vault notes
- Choosing the resources/articles destination over inbox-retain

## What failed
- (none)

## Pattern
Long technical articles about infra tooling → resources/articles, tag with vendor + category.
```

**2.3 New tool `record_experience`.** Lives in `agentos/tools/experience.py` (new file). Decorated `@tool(requires_confirmation=True)` — Telegram surfaces approval before the file is written. Uses `mcp__obsidian` write tool internally (via the canonical vault symlink at `vault/`).

**2.4 New tool `retrieve_experiences`.** Same file. Read-only, no confirmation. Queries `vault/_system/experiences/{agent_name}/` via BM25 search (`mcp__obsidian` already configured via `@bitbonsai/mcpvault`). Returns top-K relevant past experiences for the current task. Agents call this in their pre_hook.

**2.5 Wire tools into agents.** Add both tools to the toolsets of the 5 specialists. `record_experience` is called by the agent after each run when the judge score crosses a threshold (either ≥8 = success worth recording, or ≤4 = failure worth recording). `retrieve_experiences` is called at the start of any non-trivial run, top-3 results injected into the agent's context.

**2.6 HITL UX detail.** When `record_experience` triggers, the Telegram adapter renders the proposed experience note (frontmatter + body) with approve/deny buttons. Deny = skip silently; Approve = write to vault.

### Files touched (created/modified)

- `agentos/tools/experience.py` — **NEW**. Two tools: `record_experience` (HITL), `retrieve_experiences` (read-only).
- `agentos/agents/curator.py` — add both tools to `tools=[...]`.
- `agentos/agents/ingest.py` — same.
- `agentos/agents/research.py` — same.
- `agentos/agents/query.py` — `retrieve_experiences` only (query is read-only, no useful experiences to record).
- `agentos/agents/chat.py` — `retrieve_experiences` only.
- `agentos/channels/telegram_adapter.py` — confirm rendering of multi-line frontmatter approval payload (likely already works via existing confirmation pipeline; verify only).
- `vault/_system/experiences/.gitkeep` — placeholder. `experiences/` itself should NOT be gitignored — these notes are part of the second brain.

### Verification

- Run an `ingest` task on a real inbox article. Confirm the agent proposes an experience note via Telegram. Approve. Verify the file exists at `vault/_system/experiences/ingest/`.
- Run a second `ingest` task on a related article. Inspect the agent's reasoning trace to confirm `retrieve_experiences` was called and a prior experience was included in context.
- Run `rtk pytest evals/test_ingest.py -m integration` — must stay green (the experience tool should not break existing tests).

---

## Phase 3 — Agno Culture on Supervisor + Curator (2-3 days)

**Goal:** distilled principles (one level above raw experiences) shared across the team. Native Agno, no new code beyond config.

### Changes

**3.1 Enable culture on the supervisor team.** In `agentos/agents/supervisor.py`:

```python
supervisor = Team(
    ...,
    update_cultural_knowledge=True,
    enable_agentic_culture=True,
    add_culture_to_context=True,
)
```

**3.2 Enable culture on curator.** Same flags on the `curator_agent` in `agentos/agents/curator.py`. (Curator is the most refinement-heavy specialist; cultural drift here pays back fastest.)

**3.3 Culture DB.** Defaults to the existing `SqliteDb` (`agentos/db.py`) — no separate DB needed. Agno's `CulturalKnowledge` table is auto-created.

**3.4 Culture export to vault for human review.** Add a scheduled task or manual CLI in `agentos/cli/cultivate.py` (new file) that snapshots the current `CulturalKnowledge` table contents to `vault/_system/culture/{YYYY-MM-DD}.md` — daily snapshot, frontmatter + bulleted principles. Human-readable, diffable in git, editable.

**3.5 No HITL on culture writes themselves.** Rationale: culture updates are slow-moving (few per week) and snapshotting to the vault gives human-readable visibility. If a bad principle emerges, the user can delete the row in SQLite or wipe `update_cultural_knowledge` temporarily and re-seed.

**3.6 Safety net — `revert_culture` tool.** A simple admin tool in `agentos/tools/admin.py` (new file or add to existing) that deletes a culture entry by ID. Available to the supervisor only.

### Files touched

- `agentos/agents/supervisor.py` — 3 flags added to the `Team(...)` call.
- `agentos/agents/curator.py` — same 3 flags on the agent.
- `agentos/cli/cultivate.py` — **NEW**. CLI: `python -m agentos.cli.cultivate snapshot` writes today's culture to the vault.
- `agentos/tools/admin.py` — **NEW** or extend. `revert_culture(culture_id)` tool.
- `vault/_system/culture/.gitkeep` — placeholder.

### Verification

- Run several supervisor/curator interactions over a session. Query the culture table: `SELECT * FROM cultural_knowledge ORDER BY updated_at DESC LIMIT 10;`
- Confirm principles are being written (e.g., "Long-form technical articles route to resources/articles, not inbox-retain.")
- Run `python -m agentos.cli.cultivate snapshot`. Confirm `vault/_system/culture/2026-05-22.md` exists with the principles.
- Run a fresh curator task. Inspect the agent's context — culture entries should appear in the system context per `add_culture_to_context=True`.

---

## Critical files (concise inventory)

| File | Phase | Action |
|---|---|---|
| `agentos/agents/query.py` | 1 | Wire `citation_judge` to `post_hooks` |
| `agentos/agents/chat.py` | 1 | Wire `citation_judge` to `post_hooks` |
| `agentos/agents/curator.py` | 1, 2, 3 | Add `curation_judge`, experience tools, culture flags |
| `agentos/agents/ingest.py` | 1, 2 | Add `ingest_judge`, experience tools |
| `agentos/agents/research.py` | 1, 2 | Add `research_judge`, experience tools |
| `agentos/agents/supervisor.py` | 3 | Enable culture flags on the Team |
| `agentos/tools/experience.py` | 2 | **NEW** — `record_experience` (HITL) + `retrieve_experiences` |
| `agentos/tools/admin.py` | 3 | **NEW or extend** — `revert_culture` |
| `agentos/cli/cultivate.py` | 3 | **NEW** — daily culture → vault snapshot CLI |
| `vault/_system/experiences/` | 2 | **NEW directory** in vault |
| `vault/_system/culture/` | 3 | **NEW directory** in vault |
| `evals/test_*.py` | 1 | Verify smoke + integration tests stay green |

## Reused existing infrastructure (no rework needed)

- `agentos/db.py` — `SqliteDb` for sessions, culture, and eval results
- `agentos/channels/telegram_adapter.py` — HITL confirmation flow already handles `@tool(requires_confirmation=True)`
- `mcp__obsidian` (registered globally) — vault read/write/search for experience tools
- `evals/conftest.py` — judge model fixture, baseline I/O
- `vault/` symlink → `~/Documents/second-brain` (canonical) — auto-syncs to GitHub via existing `scripts/git-sync.sh`

## Deferred (not in MVP scope)

- **Phase 4 — DSPy on curator.** Wrap curator's prompt-construction as a DSPy `Signature`, use accumulated Experience entries (≥50) + judge scores as MIPROv2 trainset. Run weekly offline, HITL-approve new instructions before deploy. Defer until Phases 1-3 have produced 50+ scored runs.
- **Phase 5 — AFlow on supervisor routing.** Only if culture system doesn't already converge the routing patterns.
- **Cross-agent skill library beyond experiences.** The Agent KB pattern is realized in Phase 2 as `experiences/`; further skill-library evolution (Voyager-style reusable tool synthesis) is out of scope.

## End-to-end verification

After all 3 phases land:

1. `rtk pytest evals/ -m smoke` — fast structural checks, all green.
2. `rtk pytest evals/ -m integration` — live agent runs against baselines, all green or within tolerance.
3. Manual: run a fresh curator task on a real inbox article via Telegram. Confirm:
   - The agent retrieves past experiences before acting.
   - The agent records a new experience after acting (HITL approved).
   - The judge scores the run; score persists to eval store.
   - After 5+ such runs, culture entries appear in SQLite and snapshot to `vault/_system/culture/`.
4. Inspect `vault/_system/experiences/curator/` — should contain several human-readable notes.
5. No regressions in existing 48 eval baselines (per recent commit `a0bf35c`).

## Risks and mitigations

- **Judge cost** — judges add an LLM call per run. Mitigation: `cheap-worker` tier (already routed via LiteLLM), async (non-blocking).
- **Experience note spam** — HITL gates this. If the user denies frequently, the threshold or the recording criteria need tightening.
- **Culture drift** — daily vault snapshot + `revert_culture` tool give the user visibility and rollback. Worst case: temporarily set `update_cultural_knowledge=False` and curate manually.
- **Vault sync conflicts** — `vault/_system/experiences/*.md` files are vault-owned; the existing `git-sync.sh` handles them. If the VPS vault and the local Mac vault both write simultaneously, normal git conflict resolution applies (rare; mostly the user writes locally).
