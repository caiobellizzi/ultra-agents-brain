# Plan: ultra-workshop — Phase 1 (sibling repo bootstrap)

**Status:** Draft v3 (post-stress-test), awaiting approval
**Date:** 2026-05-19
**Owner:** Caio Bellizzi
**Working directory (output target):** `~/Documents/Projects/ultra-workshop/` (new sibling repo)
**Source project (this repo):** `~/Documents/Projects/ultra-agents-brain/` (Brain Tier 1, deployed)
**Authority:** Generated from `/gsd-discuss-phase 1 --ultra-workshop` + two `/grill-me` sessions, 2026-05-19

**Revision history:**
- **v1** — Initial plan: Hermes + Claude Code subprocess + minimal vertical slice (single coder, no graph)
- **v2** — Post-first-grill: model-agnostic constraint added → Aider replaces Claude Code; LangGraph adopted for specialist coordination; Phase 1 ships 4-node specialist topology; ~120-skill audit pass added as first task
- **v3** — Post-second-grill: LangGraph **removed** (over-engineering for Phase 1's linear pipeline); Hermes `delegate_task` covers central-orchestrator + specialist communication; **autonomous routines promoted into Phase 1 scope** (daily research, weekly review, nightly tests, bug scan, daily digest via Hermes cron). Phase 2 reserves LangGraph as opt-in upgrade if oscillation/complex-branching failure modes emerge.

---

## Context

Brain (`ultra-agents-brain` v1.0) finished Wave 4 deployment hours ago — AgentOS + Telegram + 3 systemd timers running on Hostinger VPS `srv1381850.hstgr.cloud`. The original plan documented `ultra-workshop` (Tier 2 — autonomous coding/PR/deploy agent team) as deferred to a **separate repo and future session** until Brain had run daily for 2–4 weeks.

The owner has elected to **start workshop now**, before that wait elapses. Rationale (implicit from the decision): the design discussion benefits from being captured while Brain's architecture is fresh in mind; the actual coding work can still wait until Brain has produced meaningful vault content.

This plan captures the **design contract** for the new `~/Documents/Projects/ultra-workshop/` repo. Execution (running this plan to create the sibling repo) is a separate phase that begins after approval.

### Why workshop exists (problem statement)

Brain answers "what do I know?" — workshop answers "do this thing for me." Specifically:

- The owner has a backlog of small coding tasks (bug fixes, refactors, dependency bumps, ADR drafts, infra tweaks) that he can describe in a sentence over Telegram but never finds desk time to execute.
- He has Claude Code + claude-mem + claudeclaw for *interactive* work, but no *autonomous* layer that can chew through a "fix this issue, open a PR, ping me to review" loop while he's away from his Mac.
- Brain holds the knowledge a coder agent needs (project context, prior decisions, vault notes) — workshop calls Brain over HTTP to get that context, then delegates the coding work to a local coding-agent CLI.

### Reframing of a prior decision: Hermes Agent IS real

The Brain pivoted to Agno after concluding Hermes Agent was a "hallucinated dependency" — but that conclusion was based on searching for `ghcr.io/nousresearch/hermes-agent` Docker image (which doesn't exist; Hermes ships via `uv` install). **Hermes Agent is real**, MIT, v0.14.0 (`v2026.5.16` release matches the version string the original plan was reaching for), actively developed at `github.com/nousresearch/hermes-agent`. The Brain pivot to Agno was wrong about the reason but not wrong about the outcome — Brain on Agno is clean and works. Workshop will use Hermes (where it shines: gateway + skills + cron + cross-session memory) and call Brain over HTTP (where Agno shines: typed agent execution + HITL).

---

## Locked decisions (chosen during this discuss-phase session)

| # | Decision | Rationale |
|---|----------|-----------|
| L1 | Workshop ships as a **separate sibling repo** at `~/Documents/Projects/ultra-workshop/` | Honors original architectural decision; isolates coding-agent infra from Brain's knowledge-layer infra; allows independent versioning/deploy |
| L2 | Workshop orchestrator framework: **Hermes Agent (NousResearch)** | Purpose-built for "persistent personal agent with messaging gateways + skill delegation"; already has working `claude-code` skill; ships Telegram/Discord/Slack/etc. gateway, FTS5 search, cron scheduler, MCP support |
| L3 | Brain stays on Agno; workshop talks to it via **HTTP only** | No framework migration on the working Brain. Workshop is a pure HTTP client of Brain's existing `/agents/{id}/runs` endpoints |
| L4 | **Exactly one gateway owns Telegram**: Hermes (workshop side). Brain's `uab-telegram.service` is disabled when workshop ships | Dual HITL surfaces (Brain + workshop both messaging the same chat) create approval-prompt confusion and race conditions. One owner, one surface |
| L5 | Workshop runs on the **same Hostinger VPS** as Brain for Phase 1 | $0 extra infra cost. Acceptable risk because Phase 1 coder is Claude Code subprocess (low RAM), not OpenHands Docker (would OOM Brain) |
| L6 | Budget: shared `$20/day` cap with Brain, tracked in Brain's `_system/cost-ledger.md` | Workshop posts each LLM/coder invocation cost to Brain's existing ledger via `POST /agents/curator/runs` with task=`record-cost` |
| L7 | Bot: **rotate token first** (Brain's REQ-204 still pending), then re-register `@ultra_agents_brain_bot` against Hermes gateway | Token was exposed in a prior session; rotation has been deferred since Wave 4. Workshop is the trigger to rotate |
| L8 | License: **MIT** (matches Brain's effective license and Hermes Agent) | Personal project, permissive default |
| L9 | **Model-agnostic from day 1** — all LLM calls route through Brain's existing LiteLLM proxy at `127.0.0.1:4000` using its 6 aliases (`orchestrator`, `default-worker`, `cheap-worker`, `private-worker`, `cloud-sonnet`, `cloud-groq`) | LM Studio (`private-worker`) for free local edits; cloud models only when warranted |
| L10 | **Coder = Aider** in Phase 1 (NOT Claude Code) | Model-agnostic constraint disqualifies Claude Code (Anthropic-only). Aider routes through LiteLLM natively; architect/editor split gives free internal MoA pattern. OpenHands reserved behind `Coder` adapter for Phase 2. |
| L11 | **Coordination = Hermes `delegate_task` from a Python skill body**, NOT LangGraph (v3 revision; v2 specified LangGraph) | Phase 1 pipeline is linear; LangGraph machinery is over-engineering. Hermes's Level 0 delegation (max depth 2, no shared state between siblings) is sufficient for the linear pipeline. Retry loops live in skill-body Python `for` loops. LangGraph reserved as Phase 2 opt-in upgrade if oscillation or complex branching emerges. |
| L12 | **Phase 1 ships 5-role specialist topology** via Hermes `delegate_task`: triage → planner → coder → reviewer → pr_opener. Each role is a subagent with its own skill subset loaded | Hermes spawns isolated subagents; parent aggregates summaries. Communication = `delegate_task` parent→child, return value child→parent. Matches user's "central orchestrator" mental model natively |
| L13 | **Skill audit first** — Day 1 task is `audit-claude-skills.py` script that tags each of ~120 `~/.claude/skills/` entries as `agent-agnostic`, `claude-specific`, or `requires-translation` | Avoids "copied 50, 40 broken" surprise; informs which Tier 1 skills to port and which to defer |
| L14 | **Tier 1 skill port scope = ~10 skills + 3 new brain-bridge skills** | Curated subset of agent-agnostic skills; full claude ecosystem porting deferred until concrete need emerges |
| L15 | **Hermes cron is IN Phase 1** (v3 revision; v2 deferred to Phase 2) — 5 autonomous routines ship: daily-research, weekly-vault-review, nightly-tests, bug-scan, daily-digest | User explicitly wants autonomous routines as a Phase 1 core capability, not a Phase 2 add. Hermes cron is a built-in feature; the marginal cost is writing 5 small skill bodies (~50 LOC each). |
| L16 | **GitHub repo private** (`gh repo create --private`) | Default for personal infra; flip later if useful for others |
| L17 | **Target repo allowlist Phase 1 = `caiobellizzi/test-workshop-sandbox` ONLY** | Zero blast radius on real projects; expand to allowlist in Phase 2 after 10+ clean PRs |
| L18 | **GitHub auth = fine-grained PAT scoped to allowlist** (`repo:write` on `test-workshop-sandbox` only) | Simpler than GitHub App for Phase 1; PAT compromise can only damage sandbox; upgrade path to App in Phase 2 |
| L19 | **PR description generated by `reviewer` node** from `task_ledger.md` + diff summary; format = BLUF + Changes + Test plan + Co-Authored-By line | Only reviewer has BOTH the goal AND the diff context |
| L20 | **Branch naming = `workshop/<short-id>-<slug>`** (4-char hex ID + lowercased dashed slug, max 30 chars) | Unique by ID, scannable by slug |
| L21 | **Skill audit script = tag + auto-translate** (option C) — rewrites simple `Read`/`Edit`/`Write`/`Bash`/`Grep`/`Glob` tool references to Hermes equivalents and writes outputs to `~/.hermes/skills/translated/`; tags un-translatable skills (`TaskCreate`/`AskUserQuestion`/`Skill`/`ExitPlanMode`) as `requires-manual-port` | User override of plan recommendation; auto-translate broadens portable corpus from ~10 to ~30-50 skills with conservative tool-name substitution; manual review required before promoting any translated skill |
| L22 | **LangGraph removed from Phase 1**; reserved as Phase 2 opt-in upgrade | (v3 stress-test outcome) Hermes `delegate_task` + Python skill-body for-loops cover Phase 1's linear pipeline. LangGraph machinery (StateGraph, conditional edges, SqliteSaver checkpointer) is over-engineering for ONE flow with ~3 retry points. Drop-in upgrade path: when a Phase 2 failure mode appears (e.g., reviewer→coder oscillation), wrap that single skill body in a LangGraph subgraph without changing the Hermes skill/cron/gateway surface. |
| L23 | **3 autonomous cron routines in Phase 1**: `daily-research` (07:00), `nightly-tests` (02:00), `bug-scan` (every 4h). v3's `weekly-vault-review` and `daily-digest` REMOVED — Brain's existing systemd timers cover those | Workshop's autonomous routines complement Brain's existing 3 timers (monitor/digest/review) without duplication. Cron division of labor locked in integration design D3. |
| L24 | **Brain ↔ Workshop integration model = "one system, two tiers, vault as connective tissue"** | The 5 integration principles, 7 connection types, frontmatter signaling vocabulary, and 10 integration decisions are documented in the "Brain ↔ Workshop Integration Design" section above. This reframe was the central outcome of the v3 stress-test: Brain and Workshop are not two services sharing HTTP — they are one personal AI system connected through a shared vault, with file-based signaling as the structured communication channel between them. |
| L25 | **Routing strategy: split by invocation context.** Interactive `/build` `/fix` use `private-worker` (LM Studio); autonomous cron routines (`daily-research`, `nightly-tests`, `bug-scan`) use `cloud-groq` directly | Mac is asleep ~14h/day; autonomous routines hit private-worker → 15-min fallback chain (4 attempts × ~5min timeout). Direct cloud-groq routing for cron avoids the latency catastrophe and stays cheap (~$1.50/M tokens). Interactive uses local because Mac is awake when user triggers. |
| L26 | **Tighten LiteLLM `private-worker` timeout 300s → 30s** (affects Brain too — same proxy) | A 30s ceiling cuts worst-case fallback time from ~15 min to ~60 s. Acceptable for both Brain (interactive chat) and Workshop. Requires updating `deploy/litellm/config.yaml` and rsync'ing to VPS — minor Brain change as part of workshop deploy. |
| L27 | **Vault sync = hosted GitHub remote** (`caiobellizzi/second-brain` private repo). Mac uses Obsidian-Git plugin (auto-pull + auto-push every 5 min); VPS runs `scripts/git-sync.sh push && pull` via cron every 5 min. Activate as Day-1 task BEFORE skill audit, BEFORE Workshop deploy | The script already exists at `scripts/git-sync.sh` but has never been wired. Mac vault has 1 commit (initial scaffold) and no remote. Without sync, Workshop writes on VPS are invisible on Mac Obsidian — integration design breaks. Disjoint write zones (`_system/workshop-*` VPS-only-write, PARA tiers Mac-only-write) make conflicts rare; ff-only merge fails loudly if conflicts occur |
| L28 | **Two-tier signaling vocabulary**: `workshop.suggested_action: <verb>` (set by autonomous sources — Brain's monitor/lint, Workshop's nightly-tests, scheduled discoveries — NOT dispatched) vs `workshop.action: <verb>` + `workshop.confirmed: true` (set by humans OR by Brain for self-confirming verbs like `post-to-telegram` — dispatched by bug-scan) | Eliminates the morning ping-flood failure mode where overnight autonomous routines fire 5+ HITL prompts you wake up to. Autonomous discoveries surface in Brain's daily-digest for human review; only explicit human confirmation triggers dispatch. Self-confirming verb exception: `post-to-telegram` (Brain knows when its own digest is ready) — Brain may write `action: post-to-telegram` + `confirmed: true` directly. `research` actions sourced from `vault/_system/research-queue.md` are implicitly confirmed (user added them to queue deliberately) |
| L29 | **Quiet-hours dispatch deferral**: bug-scan polls normally during 22:00–07:00 local but defers ANY dispatch that would emit a Telegram approval prompt until 07:01 | Belt-and-suspenders safety net on top of L28's vocabulary split. Even if a confirmed action leaks into the queue overnight, no late-night/early-morning Telegram pings. Cheap: one `if` statement in the dispatcher. Time-of-day tracked using VPS local timezone (configured to match user) |
| L30 | **Structured specialist outputs via Pydantic** (multi-agent depth (a)+(b) per Q5). Each role returns a typed object: `Plan` (planner), `Diff` (coder), `Review` (reviewer), `IngestResult` (brain-recorder). Orchestrator validates schema, retries with explicit reminder on parse failure (max 2 retries/role). Deferred: back-questioning (c), persistent sessions (d), parallel execution (e) — Phase 2 enhancements | Real multi-agent depth in the meaningful sense (role-specific tools + model tiers + orchestrator-mediated handoffs + branchable decisions on outputs) with low complexity cost (+0.5 day). Pydantic schemas in `workshop/types.py` become the foundation that Phase 2 enhancements build on without re-parsing prose |

---

## The 10 multi-agent patterns: what to use and what to ignore

A deep research pass (see Appendix A) examined all 10 patterns listed during this discuss-phase session. Summary of findings against workshop's specific needs:

| # | Pattern | Workshop verdict | Where it fits |
|---|---------|-----------------|---------------|
| 1 | Workflow-first + Coordinate Team | **Use as outer skeleton** | Plan → Code → Review → PR pipeline |
| 2 | Tasks mode / Planner-loop (ReAct) | **Use as inner planner** | Inside Plan stage; cap at 3 replans |
| 3 | Broadcast review board | **Defer to Phase 2** | Phase 1 = manual review via Telegram; Phase 2 = N=3 narrow reviewers (security, tests, architecture) |
| 4 | Generator + Critic (Self-Refine) | **Use inside Code stage** | Coder generates diff → critic checks → revise; cap 2 cycles |
| 5 | Router | **Use at entrance** | Hermes classifies `/build`, `/fix`, `/research`, default→chat |
| 6 | Graph / state machine | **Implicit, not implemented yet** | LangGraph if/when complexity warrants; Phase 1 uses Hermes's own loop |
| 7 | Blackboard | **Implicit via Hermes session** | Don't build a separate blackboard; Hermes's FTS5 + task ledger covers it |
| 8 | Mixture-of-Agents | **Defer; Self-MoA only if used** | Single-model Self-MoA (2–3 samples + aggregator) inside Review stage, Phase 2+ |
| 9 | Group chat / debate | **Do not use** | Sycophancy cascades documented (arXiv:2604.02668); quadratic cost; no termination guarantee |
| 10 | Swarm (LLM-routed handoff) | **Phase 2 upgrade** | LangGraph Swarm replaces Hermes's linear flow if specialist topology proves valuable |

**Anti-patterns the plan explicitly avoids:**

- Two systems both managing HITL (dual Telegram surfaces)
- Multiple coders auto-committing to the same repo
- Heavy Docker sandbox (OpenHands V1 with Docker) on the same 4GB VPS as Brain
- Circular agent calls (Hermes → Agno → Hermes via MCP) — no infinite-loop circuit breaker
- Mixing different-capability models in MoA (2025 research: hurts more than it helps)

---

## Architecture

```
                                Hostinger VPS (31.97.130.253)
                                ┌──────────────────────────────────────────────────┐
                                │                                                  │
Telegram ─long-poll─────────────►   Hermes Agent (central orchestrator)            │
                                │    ├─ session FTS5 @ ~/.hermes/state.db          │
                                │    ├─ skills/                                    │
                                │    │   • workshop-build, workshop-fix            │
                                │    │   • workshop-research (autonomous)          │
                                │    │   • brain-query, brain-ingest, brain-research│
                                │    │   • aider (local impl of Hermes #534)       │
                                │    │   • Tier 1 ports + auto-translated skills   │
                                │    ├─ mcps/   (github, context7, crawl4ai, ...)  │
                                │    ├─ cron scheduler (5 autonomous routines)     │
                                │    │   • daily-research      0 7 * * *           │
                                │    │   • weekly-vault-review 0 18 * * 0          │
                                │    │   • nightly-tests       0 2 * * *           │
                                │    │   • bug-scan            */4 * * * *         │
                                │    │   • daily-digest        0 20 * * *          │
                                │    └─ HITL: pause via clarify callback → TG btn  │
                                │                       │                          │
                                │                       │ skill body (Python):     │
                                │                       │   delegate_task(role=    │
                                │                       │     "triage"/"planner"/  │
                                │                       │     "coder"/"reviewer"/  │
                                │                       │     "pr_opener")         │
                                │                       ▼                          │
                                │   Specialist subagents (Hermes-isolated, Level 0):│
                                │    ├─ triage    (cheap-worker, classify intent)  │
                                │    ├─ planner   (cloud-sonnet, plan + ctx fetch) │
                                │    │     └─ HTTP → Brain.query / Brain.research  │
                                │    ├─ coder     (Aider subprocess)               │
                                │    │     ├─ architect: cloud-sonnet              │
                                │    │     └─ editor:    private-worker (LM Studio)│
                                │    ├─ reviewer  (default-worker, lint+checks)    │
                                │    └─ pr_opener (cheap-worker)  ◄── HITL gate    │
                                │                                                  │
                                │   Brain (Agno, :7000) ─read-mostly context─      │
                                │    ├─ query_vault                                │
                                │    ├─ research_topic                             │
                                │    └─ ingest_to_vault (ADRs, learnings, costs)   │
                                │                       │                          │
                                │                       ▼                          │
                                │   /srv/second-brain/ (PARA vault)                │
                                │                                                  │
                                │   LiteLLM (:4000) ── shared model gateway        │
                                │    aliases: orchestrator, default-worker,        │
                                │             cheap-worker, private-worker,        │
                                │             cloud-sonnet, cloud-groq             │
                                │                                                  │
                                └──────────────────────────────────────────────────┘
                                                  │
                                                  │ git push / PR open (HITL-gated)
                                                  ▼
                                            github.com (PR review)
```

**Key invariants:**
- **One orchestrator** (Hermes, central — gateway + skill runtime + MCP host + cron scheduler), **one coder** in Phase 1 (Aider via new `aider` Hermes skill), **one gateway** (Hermes Telegram). **No LangGraph in Phase 1** (deferred to Phase 2 as opt-in upgrade if needed).
- **Model-agnostic by construction.** All LLM calls route through Brain's LiteLLM proxy at `127.0.0.1:4000` using 6 aliases. Local model (`private-worker` = LM Studio gemma-4-e4b via LM Link) handles ≥80% of token volume (editor inside Aider, reviewer subagent); cloud (`cloud-sonnet`) used only for planner and Aider architect.
- **Specialist topology = Hermes `delegate_task` subagents** invoked from a skill body. Parent orchestrator dispatches to specialists sequentially (or in parallel via Hermes's ThreadPoolExecutor for independent sub-investigations); each subagent has its own model alias + skill subset; results return as summaries which the parent aggregates.
- **Retry loops live in Python skill-body `for` loops**, not in declarative graph edges. E.g., `for attempt in range(max_retries): result = delegate_task(role="reviewer", ...); if result.ok: break`. Bounded by hardcoded `max_retries` and the daily-budget circuit breaker.
- **Autonomous routines = Hermes cron + skill body**. 5 routines ship in Phase 1; each is a small skill body invoked by Hermes's built-in cron scheduler. Idempotent (re-running yields same state); budget-circuit-broken; Telegram-notified on completion or non-trivial result.
- **Brain is read-mostly from workshop's perspective.** Workshop reads context (query/research) and writes only ADRs, lessons learned, autonomous-routine results, and cost ledger entries back into the vault via Brain's ingest agent.
- **HITL via Hermes's clarify callback**: when a skill needs approval (git push, PR open, irreversible op), it calls Hermes's clarify callback which surfaces a Telegram inline button; user approval resumes the skill body where it paused.
- **State stores (2)**: Hermes FTS5 at `~/.hermes/state.db` (sessions, skill memory, cron history) + Brain SqliteDb (Agno's session+HITL state). Workshop adds NO third store in Phase 1 (LangGraph's `SqliteSaver` no longer needed). Per-task task ledgers live as files under `~/.ultra-workshop/tasks/<id>/` (Magentic-One two-ledger pattern, file-based not DB-backed).
- **Coder substitution path**: Aider invocation is wrapped in a thin Python function `workshop.coder.run_aider(task)`. Phase 2's OpenHands addition adds `workshop.coder.run_openhands(task)`; the dispatching skill chooses between them by task tag. No adapter class hierarchy needed at this scale — two functions with the same signature is sufficient.

---

## Brain ↔ Workshop Integration Design

**Foundational reframe** (added in v3 stress-test): Brain and Workshop are not two systems sharing HTTP — they are **one personal AI system with two tiers**, connected by the **vault as canonical source of truth**. Every integration decision below derives from that reframe.

### 5 Integration Principles

| # | Principle |
|---|-----------|
| P1 | **Vault is the source of truth.** Both Brain and Workshop orbit the vault at `/srv/second-brain/`. State that must survive lives there. State that's ephemeral lives in Hermes FTS5 or Agno SqliteDb (which both systems treat as caches). |
| P2 | **Knowledge flows in a closed loop.** Brain captures + synthesizes (input). Workshop acts + reports (output). Reports land in vault → next task queries them via Brain → loop closes through filesystem, not APIs. |
| P3 | **File-based signaling, no event bus.** Cross-system requests = vault frontmatter tags + filesystem polling. Simple, debuggable, survives restarts. The entire Brain↔Workshop conversation is `rg`-able from one vault directory. |
| P4 | **Single budget, single trust policy, single LiteLLM gateway.** No duplication of these concerns across systems. |
| P5 | **Cron division of labor, no overlap.** Brain's existing systemd timers (monitor / digest / review) stay as-is. Workshop adds 3 distinct routines (research / tests / bug-scan). Workshop's outputs feed INTO Brain's digest, never parallel. |

### 7 Connection types (in order of coupling tightness)

| # | Connection | Direction | Mechanism | What flows |
|---|------------|-----------|-----------|------------|
| C1 | HTTP RPC | W → B | `POST :7000/agents/{id}/runs` via 3 Hermes skills (`brain-query` / `brain-ingest` / `brain-research`) | Synthesized answers; HITL-gated writes |
| C2 | Shared vault filesystem | W ↔ B | Both processes access `/srv/second-brain/`; Workshop reads everywhere, writes only to `_system/workshop-*/` directly | Task ledgers, ADRs, cost entries, autonomous routine reports |
| C3 | Shared LiteLLM proxy | W & B → `:4000` | Both `base_url=http://127.0.0.1:4000/v1` | All LLM traffic; shared 6 aliases |
| C4 | Shared cost ledger | W & B → `vault/_system/cost-ledger.md` | Both append-only; both read for $20/day circuit breaker | Per-call cost rows with `source: brain` or `source: workshop` |
| C5 | Shared trust policy | Python module import | Workshop's install creates a symlink: `/opt/ultra-workshop/workshop/trust_shared.py → /opt/ultra-agents-brain/ultra_brain/trust.py` | Low/medium/high-risk action classification |
| C6 | Frontmatter signaling vocabulary | W ↔ B | Vault notes carry tags both systems read on filesystem polls | Cross-system requests, status, attribution (see vocabulary table below) |
| C7 | Cron coordination | Independent schedules, shared vault | Brain's 3 systemd timers + Workshop's 3 Hermes cron routines | Each routine writes its own report to a predictable vault path |

### Frontmatter signaling vocabulary (the contract)

This vocabulary IS the structured communication channel between Brain and Workshop. Both systems must respect it.

| Tag | Written by | Read by | Meaning |
|-----|-----------|---------|---------|
| `workshop.suggested_action: <verb>` (e.g., `fix-bug`, `link-orphans`, `fix-test-failure`) | **Autonomous sources only** (Brain's monitor/lint, Workshop's nightly-tests, scheduled discoveries) | Brain's daily-digest aggregator (for human review) | Suggestion — does NOT trigger autonomous dispatch |
| `workshop.action: <verb>` + `workshop.confirmed: true` | **Humans** (via Obsidian edit) OR Brain (only for self-confirming verbs: `post-to-telegram`) OR implicit via `vault/_system/research-queue.md` entries | Workshop's bug-scan cron | Dispatched to corresponding skill — actual execution |
| `workshop.task_id: <id>` | Workshop | Brain, user | Cross-reference to `~/.ultra-workshop/tasks/<id>/` |
| `workshop.status: <state>` (`pending`, `in_progress`, `done`, `blocked`) | Workshop | Brain, user | Task lifecycle |
| `workshop.cost: <usd>` | Workshop | Brain digest | Per-note running cost tally |
| `workshop.pr_url: <url>` | Workshop | Brain digest | Resulting PR link |
| `brain.classified_as: <para-path>` | Brain (filer/curator) | Workshop planner | PARA tier signal — Workshop respects Brain's classification |
| `brain.summarized: <date>` | Brain (curator) | Workshop digest | Note processed; safe to use as planning context |
| `brain.related: [[NoteA]], [[NoteB]]` | Brain (linker) | Workshop planner | Pre-computed related context |
| `system.created_by: workshop \| brain` | Both | Both | Attribution; helps curator decide re-processing |

### 5 Canonical data flows (concrete scenarios)

**Flow A — User-initiated fix (mandatory Phase 1):**
```
User /fix <issue-url> → Hermes
  → workshop-fix skill (Python body)
     → delegate_task(role=planner, skills=[brain-query]) → HTTP → Brain.query
     → delegate_task(role=coder,   skills=[aider])       → Aider subprocess → diff
     → delegate_task(role=reviewer)                       → lint + checks
     → HITL clarify callback → Telegram approval
     → gh pr create
     → delegate_task(role=brain-recorder, skills=[brain-ingest]) → ADR written to vault
            (frontmatter: workshop.task_id, workshop.status: done, workshop.pr_url, system.created_by: workshop)
Brain's next monitor cycle ingests → classifies → marks brain.summarized
```

**Flow B — Brain triggers Workshop (mandatory Phase 1 — closes the loop):**
```
Brain's hourly monitor runs lint_vault → finds orphan notes
  → writes vault/_system/lint-report.md (frontmatter: workshop.action: link-orphans)
Workshop's bug-scan cron (every 4h) polls vault for workshop.action: *
  → matches lint-report.md
  → invokes link-orphans skill body (autonomous; HITL only at write step)
     → reads orphan list, delegate_task(role=linker) for each
     → writes suggestions back to vault with workshop.status: pending
     → Telegram approval prompt
User approves → Workshop applies links, marks workshop.status: done
```

**Flow C — Autonomous research from vault queue (SHOULD Phase 1):**
```
User adds line to vault/_system/research-queue.md
Workshop's daily-research cron (07:00) reads top entry
  → delegate_task(role=researcher, skills=[brain-research]) → Brain.research → synthesis to Inbox/
  → marks research-queue entry workshop.status: done
  → Telegram notification with vault link
Brain's monitor classifies Inbox/ → moves note to 02-Resources/
```

**Flow D — Nightly tests with deferred user review (mandatory Phase 1):**
```
nightly-tests cron (02:00):
  for repo in ALLOWED_REPOS:
    clone, run test command from repo's declared test config
    if failures:
      write vault/_system/workshop-routines/nightly-tests/<date>.md
        (frontmatter: workshop.action: fix-test-failure, workshop.task_id, repo, stack_trace)
Brain's daily digest (20:00) reads workshop-routines/ from the day
  → includes test failure summary in digest narrative
User reads digest → decides which failures to act on → adds workshop.action: fix-bug to selected
Workshop's bug-scan picks them up in next cycle (Flow B closes)
```

**Flow E — Aggregated daily digest from both systems (mandatory Phase 1):**
```
Brain's existing uab-digest.timer (20:00) runs ultra_brain.express.daily_digest
  → reads vault notes from today (Brain ingests + Workshop ADRs + cron reports)
  → reads _system/cost-ledger.md for total spend (both sources)
  → reads workshop task ledgers via filesystem
  → emits ONE digest narrative to vault/_system/daily-digest-<date>.md
  → writes frontmatter: workshop.action: post-to-telegram
Workshop's bug-scan cron picks up workshop.action: post-to-telegram → posts to TG
```

### 10 Integration decisions (locked)

| # | Decision | Resolution |
|---|----------|-----------|
| D1 | Workshop vault filesystem access | **Read everywhere, write only to `_system/workshop-*/`** directly; writes elsewhere via Brain.ingest (HITL-gated) |
| D2 | Cost ledger location | `/srv/second-brain/_system/cost-ledger.md` — both systems append with `source:` field; both circuit-break against this single file |
| D3 | Cron division of labor | **Brain owns**: monitor (hourly), digest (daily 20:00), review (weekly Sun 18:00) — UNCHANGED. **Workshop owns**: daily-research (07:00), nightly-tests (02:00), bug-scan (every 4h). v3's `weekly-vault-review` and `daily-digest` workshop crons are REMOVED — Brain's existing timers cover them. |
| D4 | Trust policy sharing | Workshop install symlinks `/opt/ultra-workshop/workshop/trust_shared.py → /opt/ultra-agents-brain/ultra_brain/trust.py`. One source of truth on a shared VPS filesystem |
| D5 | Skill registry sharing | `vault/_system/skill-registry.md` maintained by Brain's curator (Phase 1.5 enhancement); lists both-system skills with capability tags. Workshop's planner reads it when planning |
| D6 | Cross-system signaling | Frontmatter vocabulary above is the contract; both systems must respect it. Vocabulary documented in `vault/_system/integration-contract.md` (committed by workshop install) |
| D7 | Reverse direction (Brain → Workshop HTTP)? | **NO.** Brain never makes HTTP calls to Workshop. All Brain→Workshop signals go via vault frontmatter + Workshop's polling crons. One-way HTTP = small failure surface |
| D8 | Telegram gateway ownership | **Workshop owns it (post-deploy).** Brain's `uab-telegram.service` stays disabled. Brain's notifications go to vault file → Workshop's bug-scan picks up `workshop.action: post-to-telegram` and posts |
| D9 | Workshop's task ledger location | `~/.ultra-workshop/tasks/<id>/` (filesystem, fast). On task completion, compact ADR written to vault `_system/workshop-adrs/<id>.md` for Brain's curator. Local ledgers archive at 30 days |
| D10 | Phase 1 closes the loop? | **YES.** Flows A, B, D, E mandatory. Flow C is SHOULD. Without B (Brain→Workshop) the loop is open and the two-tier vision is unrealized |

### What Phase 1 explicitly delivers from this design

1. **Both directions wired** — Workshop calls Brain via HTTP (C1); Brain triggers Workshop via vault frontmatter (C6)
2. **Single budget enforced** — both systems append to and circuit-break against `vault/_system/cost-ledger.md` (C4)
3. **Shared trust policy** — symlink at install time (C5)
4. **Vault as canonical task store** — every Workshop action produces a vault ADR (C2 + frontmatter)
5. **Cron timers don't duplicate work** — Brain's existing 3 timers + Workshop's new 3 timers cover the full operational surface without overlap (D3)
6. **Telegram unified** — Workshop owns the gateway; Brain notifications flow through Workshop via vault tags (D8)

---

## Stack (locked for Phase 1)

| Component | Choice | Version / Path | Why |
|-----------|--------|----------------|-----|
| Orchestrator | Hermes Agent (NousResearch) | `v0.14.0` pinned | User choice + research validation; ports ~120 skills + 20 MCPs from `~/.claude/` ecosystem; central orchestrator pattern via `delegate_task` + cron scheduler |
| Coordination | **Hermes `delegate_task` + Python skill-body for-loops** (NO LangGraph in Phase 1) | Built into Hermes | v3 stress-test outcome: LangGraph machinery is over-engineering for Phase 1's linear pipeline. LangGraph reserved as Phase 2 opt-in upgrade |
| Coder | **Aider** (via new Hermes skill, implementing Issue #534 locally) | `aider-chat` latest stable | Model-agnostic via LiteLLM; architect+editor split = free internal MoA; lightest model-agnostic option |
| Knowledge layer | Brain (Agno) over HTTP | Already deployed | No changes to working Brain |
| LLM gateway | LiteLLM | Already deployed at `:4000` | Shared with Brain. **Aliases used by workshop**: `cloud-sonnet` (planner, Aider architect), `private-worker` (Aider editor = LM Studio gemma-4-e4b), `default-worker` (reviewer), `cheap-worker` (triage, pr_open) |
| Local model gateway | LM Link → LM Studio @ Mac | Already configured | Reached via `private-worker` alias; free local inference for editor + reviewer (≥80% of token volume) |
| Messaging | Telegram (long-poll) | python-telegram-bot in Hermes | Same bot, rotated token |
| State (2 stores) | Hermes FTS5 + Brain SqliteDb | `~/.hermes/state.db` + `/var/lib/uab/` | v3 drops the LangGraph SqliteSaver since LangGraph is no longer in Phase 1. Per-task ledgers live as files under `~/.ultra-workshop/tasks/<id>/`, not DB rows |
| Process supervision | systemd | `uws-hermes.service` | Same pattern as Brain's `uab-brain.service`; depends on `uab-brain.service` |
| Repo | git + GitHub | `caiobellizzi/ultra-workshop` (private) | Owner workflow |
| License | MIT | `LICENSE` at repo root | Matches Brain + Hermes |
| Python | 3.11 (matches Hermes requirement) | venv via `uv` | Hermes installer enforces |
| Skill source | `~/.hermes/skills/` populated from repo `skills/` + Tier 1 ports from `~/.claude/skills/` | agentskills.io standard | Compatible disk format; skill audit pass on Day 1 tags which `~/.claude/` skills are portable |

**Deferred (Phase 2+):**

| Component | When to consider |
|-----------|------------------|
| OpenHands V1 SDK (as `OpenHandsAdapter` behind `Coder` interface) | When `/fix <issue>` task volume justifies; Phase 1 abstraction makes Phase 2 wiring drop-in |
| Claude Code subprocess (as `ClaudeCodeAdapter`) | Only if model-agnostic constraint is relaxed; currently disqualified by L9 |
| Broadcast Review Board (P3) | After 10+ successful Phase 1 PRs — you'll know what review categories matter |
| Self-MoA (P8) inside Review node | When single-reviewer false-PASS becomes a real problem |
| Hermes cron scheduler | When workshop has scheduled workflows worth automating (security advisory scans, etc.) |
| Discord / Slack / WhatsApp adapters | When you want multi-platform reach |
| Auto-merge / auto-deploy | Phase 1 stops at PR creation; merge stays manual |
| Separate VPS for OpenHands Docker sandbox | Only if untrusted-code execution becomes a real need |

---

## Phase 1 scope (what ships)

**Specialist topology vertical slice.** End-to-end flow via 5-node LangGraph spine:

```
User → Telegram → /build <task> or /fix <issue-url>
       └─► Hermes router → workshop-build skill
              └─► LangGraph spine starts
                      │
                      ├── triage      (cheap-worker)   ─► classify intent + task type
                      ├── planner     (cloud-sonnet)   ─► HTTP → Brain.query for context
                      │                                  ─► emit task_ledger.md
                      ├── coder       (Aider subprocess)
                      │     ├── architect: cloud-sonnet ─► plans the change
                      │     └── editor:    private-worker (LM Studio) ─► implements diff
                      ├── reviewer    (default-worker)  ─► lint + basic checks
                      │                                  ─► emit progress_log.jsonl
                      └── pr_open     ◄── interrupt_before HITL
                              │
                              └─► Hermes catches interrupt → Telegram inline buttons
                                      │
                                      └─► User taps [Approve] / [Reject]
                                              │
                                              └─► Resume graph → git push + gh pr create
                                                      │
                                                      └─► Hermes ingests ADR + cost via Brain
                                                              ─► PR URL posted to Telegram
```

### MUST ship in Phase 1

| # | Requirement |
|---|-------------|
| WS-001 | Hermes Agent installed under `/opt/ultra-workshop/` on VPS, running as `uws-hermes.service` (systemd, `After=uab-brain.service`) |
| WS-002 | Telegram bot (rotated token) gates on the existing allowed chat ID `7113965359` |
| WS-003 | Skill-audit + auto-translate script: `scripts/audit-claude-skills.py` walks `~/.claude/skills/`, tags each as `agent-agnostic` / `claude-specific` / `requires-translation` / `requires-manual-port`. For `requires-translation` skills, applies the Tool Translation Map (Appendix E) to rewrite tool references and writes translated SKILL.md files to `~/.hermes/skills/translated/<name>/`. Emits `skill-audit.json` with full classification + translation summary. (Day-1 task) |
| WS-004 | Tier 1 skill port: ~10 agent-agnostic skills copied to `~/.hermes/skills/` + smoke-tested in local Hermes |
| WS-005 | 3 new brain-bridge skills: `brain-query`, `brain-ingest`, `brain-research` — thin Hermes skills wrapping HTTP calls to Brain |
| WS-006 | Aider Hermes skill (`skills/aider/SKILL.md` — local impl of Issue #534) invokes Aider with architect=`cloud-sonnet`, editor=`private-worker`, `--yes-always --no-stream --message <task>` |
| WS-007 | `workshop-build` Hermes skill: Python skill body that orchestrates the 5-role specialist pipeline via Hermes `delegate_task` calls (triage → planner → coder → reviewer → pr_opener), with `for attempt in range(max_retries):` loops for reviewer→coder retry (max 2). **Each specialist returns a Pydantic-typed object** (`Plan`, `Diff`, `Review`, `IngestResult` per L30); orchestrator parses + validates schema; retries with explicit "must return valid JSON matching schema" reminder on parse failure (max 2 retries per role). Specialists read predecessors' typed outputs from the in-process task ledger when prompted |
| WS-008 | `workshop-fix` Hermes skill: same body as workshop-build but with `/fix <github-issue-url>` triage path that fetches the issue first via gh CLI/MCP |
| WS-009 | Magentic-One two-ledger pattern: each task writes `task_ledger.md` (goal + plan) + `progress_log.jsonl` (delegate_task events) under `~/.ultra-workshop/tasks/<task-id>/` |
| WS-010 | HITL gate: workshop-build/fix skill bodies pause via Hermes's clarify callback before invoking `gh pr create`; user approval resumes |
| WS-011 | After PR created, workshop writes ADR via Brain.ingest to `_system/workshop-adrs/<task-id>.md` |
| WS-012 | Cost ledger: per-`delegate_task` cost posted to Brain's `_system/cost-ledger.md`; circuit-breaker checked before each LLM call (shared $20/day cap) |
| WS-013 | Brain's `uab-telegram.service` is **disabled** before workshop's Telegram is brought up (no dual gateway) |
| WS-014 | Workshop survives `systemctl restart uws-hermes` mid-flow: Hermes session FTS5 preserves pending approvals; task ledger files preserve flow state |
| WS-015 | MCP re-registration in Hermes config: `github`, `context7`, `crawl4ai`, `hostinger-api`, `google-workspace` (5 servers from `~/.claude.json`) |
| **WS-016** | **`daily-research` autonomous cron** (`0 7 * * *`): skill body reads top entry from `vault/_system/research-queue.md`, invokes Brain.research via HTTP, writes synthesis to vault `Inbox/`, marks queue entry `workshop.status: done`, notifies Telegram with link |
| **WS-017** | **`nightly-tests` autonomous cron** (`0 2 * * *`): for each repo in `ALLOWED_REPOS`, clones to `/tmp/uws-test/<repo>`, runs the repo's declared test command, writes results to `vault/_system/workshop-routines/nightly-tests/<date>.md` with frontmatter **`workshop.suggested_action: fix-test-failure`** (NOT `action`+`confirmed`) on failures. Surfaces in Brain's 20:00 daily digest for human review; user flips `suggested_action → action` + `confirmed: true` to dispatch (or ignores) |
| **WS-018** | **Three-tier polling for Flow B/E signals** (with vocabulary-split + quiet-hours enforcement): (i) **fast-poll** every 30s on `vault/_system/.workshop-queue.jsonl` for urgent Brain→TG digest posts and Brain-confirmed actions; offset at `~/.ultra-workshop/state/queue-offset.txt`. (ii) **standard-poll** every 4h via Hermes cron — full vault scan; **dispatches only when BOTH `workshop.action:` AND `workshop.confirmed: true` are present** (L28); dedup via `workshop.status` tag + mtime comparison. (iii) **nightly-rescan** at 03:00 — full scan + dedup index rebuild. (iv) **Quiet-hours guard** (L29): during 22:00–07:00 local, any dispatch that would emit a Telegram approval prompt is queued and executed at 07:01 local; only zero-HITL verbs (e.g., `post-to-telegram`) dispatch immediately. Verbs: `post-to-telegram`→notify, `fix-bug`/`fix-test-failure`→workshop-fix, `link-orphans`→linker, `research`→workshop-research |
| WS-019 | All cron routines respect the daily budget circuit breaker; if `$daily_spend ≥ $18`, routines self-cancel and emit a single Telegram warning per day. Circuit breaker reads from shared `vault/_system/cost-ledger.md` |
| WS-020 | **Brain → Workshop loop closure (Flow B mandatory)**: Brain's existing hourly `uab-monitor.timer` writes `vault/_system/lint-report.md` with frontmatter **`workshop.suggested_action: link-orphans`** when orphans found. Aggregated into Brain's 20:00 daily-digest; user confirms via Obsidian to dispatch |
| WS-021 | **Brain → Telegram via Workshop (Flow E mandatory)**: Brain's daily-digest (existing `uab-digest.timer` at 20:00) appends one line to `vault/_system/.workshop-queue.jsonl` with `{"action": "post-to-telegram", "ref": "<digest-path>", "urgency": "urgent", "confirmed": true}`. Workshop's fast-poll picks it up within 30s. `post-to-telegram` is one of Brain's self-confirming verbs per L28. Brain's old direct-to-Telegram path stays disabled |
| WS-022 | **Shared trust policy via symlink**: install script creates `/opt/ultra-workshop/workshop/trust_shared.py → /opt/ultra-agents-brain/ultra_brain/trust.py`; Workshop imports from this path |
| WS-023 | **Integration contract document**: install writes `vault/_system/integration-contract.md` with the frontmatter vocabulary spec (D6) so the contract is self-documenting inside the vault |
| **WS-024** | **Vault sync wiring — GitHub remote** (Day 1): `gh repo create caiobellizzi/second-brain --private`; on VPS generate SSH deploy key + add to repo deploy keys (read+write); `cd /srv/second-brain && git remote add origin git@github.com:caiobellizzi/second-brain.git && git push -u origin main` |
| **WS-025** | **Mac side sync** (Day 1): Install Obsidian-Git plugin in `~/Documents/second-brain/.obsidian/plugins/obsidian-git/`; configure auto-pull every 5 min + auto-commit-and-sync every 5 min; `git remote add origin git@github.com:caiobellizzi/second-brain.git && git fetch && git pull --rebase` |
| **WS-026** | **VPS cron sync** (Day 1): add to `/opt/ultra-agents-brain/deploy/cron/ultra-agents-brain.cron`: `*/5 * * * * uabrain /opt/ultra-agents-brain/scripts/git-sync.sh push "vps-auto $(date -u +%H:%M)" && /opt/ultra-agents-brain/scripts/git-sync.sh pull` — uses the existing `scripts/git-sync.sh` |
| **WS-027** | **Vault sync env vars** set in `/etc/uab/env` on VPS and `.env` on Mac: `VAULT_VPS_PATH=/srv/second-brain` (VPS) / `VAULT_VPS_PATH=$HOME/Documents/second-brain` (Mac), `VAULT_DEFAULT_BRANCH=main`, `VAULT_REMOTE=origin` |
| **WS-028** | **`workshop/types.py` Pydantic schemas** for specialist communication (per L30): `Plan`, `PlanStep`, `Diff`, `FileChange`, `Review`, `Issue`, `IngestResult`. Used as both the return-type contract and the JSON-schema injected into each specialist's prompt. Validation + retry logic centralized in `workshop/orchestrator.py`'s `delegate_typed(role, output_type, ...)` helper |

### WON'T ship in Phase 1

- Discord, WhatsApp, Slack adapters (Hermes supports them; not configured Phase 1)
- OpenHands V1 SDK integration (deferred to Phase 2; can be added as a second `run_openhands()` function callable from the same workshop-build skill)
- Claude Code as coder (disqualified by model-agnostic constraint L9; future-revisit only if constraint relaxes)
- **LangGraph orchestration** (v3 removal; reserved as Phase 2 opt-in upgrade if a real failure mode emerges — oscillation, complex branching, replay needs)
- Broadcast review board (P3 — multi-reviewer fan-out); single `reviewer` subagent in Phase 1
- MoA / Self-MoA inside reviewer (P8 deferred)
- Auto-merge / auto-deploy (HITL stops at PR creation; merge stays manual)
- Auto-merge of issues opened by `nightly-tests` cron (HITL required for that PR too)
- Multi-repo support beyond the allowlist (Phase 1 = `caiobellizzi/test-workshop-sandbox` only; multi-repo Phase 2+)
- Plugin skill clusters (`gsd-*`, `superpowers:*`, `dotnet-skills:*`, etc.) — too claude-tool-coupled; Tier 1 port only
- Vault-level structured search endpoint on Brain (workshop calls Brain.query and parses synthesized text in Phase 1; structured `/vault/search` is a Phase 2 Brain enhancement if needed)

### SHOULD reach for in Phase 1 if time permits

- `/research <topic>` interactive command (in addition to autonomous `daily-research` cron) — calls Brain.research synchronously, posts result to Telegram
- Skill-body unit tests for the 5 cron routines (`tests/test_cron_routines.py`) — invest while the surface is small
- `task-ledger.md` auto-pruning: archive ledgers older than 30 days to `~/.ultra-workshop/tasks/_archive/`
- Cron-routine result write-back to Brain vault under `_system/workshop-routines/<routine-name>/<date>.md` for historical audit

---

## Repo bootstrap checklist (Phase 1 execution preview, ~7 dev days)

When this plan is approved and a separate execute-phase begins:

### Day 1 — Foundation + skill audit
```
1. Rotate Telegram bot token via BotFather /revoke; capture new token in 1Password
2. `mkdir -p ~/Documents/Projects/ultra-workshop && cd $_`
3. `git init && gh repo create caiobellizzi/ultra-workshop --private`
4. Install Hermes Agent locally for development:
     curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
5. Scaffold repo (see Repo Tree below)
6. Write scripts/audit-claude-skills.py — walks ~/.claude/skills/, parses each SKILL.md,
   tags as agent-agnostic / claude-specific / requires-translation, writes skill-audit.json
7. Run audit; review report; commit skill-audit.json to repo as canonical record
```

### Day 2 — Tier 1 skill port + Aider skill
```
8.  Copy ~10 agent-agnostic skills from ~/.claude/skills/ to repo skills/ then to ~/.hermes/skills/
9.  Edit frontmatter to match Hermes spec (name, description, version, platforms)
10. Smoke-test each ported skill: `hermes skill run <name> --dry-run`
11. Write skills/aider/SKILL.md — local impl of Hermes Issue #534 (subprocess wrapper, architect+editor flags)
12. Write skills/brain-query/SKILL.md, skills/brain-ingest/SKILL.md, skills/brain-research/SKILL.md
    (thin HTTP wrappers over Brain's /agents/{id}/runs endpoints)
13. Smoke: `hermes skill run aider --message "echo hello"` returns a diff
14. Smoke: `hermes skill run brain-query --question "what do I know about X"` returns a vault answer
```

### Day 3 — LangGraph spine
```
15. pyproject.toml: deps = langgraph>=0.2, httpx, tomli, python-telegram-bot, aider-chat
16. workshop/state.py: TypedDict (task, intent, context, plan, diff, review, cost, ledger_path)
17. workshop/coder.py: Coder ABC + AiderAdapter implementing it
18. workshop/nodes/triage.py: classify message → intent ∈ {build, fix, research, chat}
19. workshop/nodes/planner.py: HTTP → brain-query for context; LLM call (cloud-sonnet) → plan + task_ledger.md
20. workshop/nodes/coder.py: invoke AiderAdapter(architect=cloud-sonnet, editor=private-worker)
21. workshop/nodes/reviewer.py: lint + basic checks; default-worker
22. workshop/nodes/pr_open.py: stub — emit interrupt_before
23. workshop/graph.py: StateGraph wiring + SqliteSaver(~/.ultra-workshop/state/checkpoints.db)
24. tests/test_graph.py: node-level unit tests with mocked HTTP + LLM calls
25. Smoke (CLI): python -m workshop.graph "add a hello.md to test-repo" → graph runs, halts at pr_open
```

### Day 4 — Brain integration + ledger + cost
```
26. workshop/ledger.py: task_ledger.md writer (Magentic-One format) + progress_log.jsonl appender
27. workshop/cost.py: per-call cost recording → POST to Brain.curator via brain-ingest skill
28. Wire nodes to ledger: every state transition appends to progress_log.jsonl
29. Wire cost circuit breaker: planner/coder/reviewer all check daily_spend before LLM call
30. Smoke: complete graph run produces ledger files + ADR via Brain.ingest + cost entry
```

### Day 5 — HITL round-trip
```
31. workshop-build Hermes skill (skills/workshop-build/SKILL.md): wraps `python -m workshop.graph` invocation
32. Wire LangGraph interrupt → Hermes pause → Telegram inline buttons (mirror Brain's adapter pattern)
33. Wire user approval → Hermes resume → LangGraph continue
34. Smoke: full /build flow over Telegram on local Hermes → PR opened on test repo
35. MCP re-registration: github, context7, crawl4ai, hostinger-api, google-workspace into hermes.toml
```

### Day 6 — VPS deploy
```
36. Final pre-deploy checks: cost ledger working, audit log clean, no secrets in commits
37. bash deploy/install.sh root@31.97.130.253
       - rsync repo to /opt/ultra-workshop/
       - install Hermes (uv pip install)
       - install Python deps from pyproject.toml
       - copy systemd unit + reload
38. On VPS: systemctl disable --now uab-telegram   (DUAL GATEWAY ELIMINATED — verify with V15)
39. On VPS: systemctl enable --now uws-hermes
40. End-to-end smoke from Telegram pointing at VPS
```

### Day 7 — Verification + ship
```
41. Run verification matrix V1-V17 (see below)
42. Fix any failures iteratively
43. git tag v0.1.0; git push --tags
44. Write retro to Brain via brain-ingest skill ("Phase 1 shipped; what surprised me")
45. Update Brain's STATE.md with workshop-phase-1-deployed milestone
```

### Repo tree (post-bootstrap)

```
~/Documents/Projects/ultra-workshop/
├── README.md                          (architecture + Brain links)
├── PLAN.md                            (this file, copied + revised)
├── LICENSE                            (MIT)
├── pyproject.toml
├── .env.example                       (TELEGRAM_BOT_TOKEN, ALLOWED_CHAT_IDS, BRAIN_BASE_URL, LITELLM_BASE_URL)
├── .gitignore                         (.env, state/*.db, ~/.hermes/)
├── hermes-config/
│   ├── hermes.toml                    (model: openai/orchestrator base_url=:4000)
│   ├── gateway-telegram.toml          (bot token, allowed chats)
│   └── mcps.toml                      (github, context7, crawl4ai, hostinger, google-workspace)
├── skills/                            (copied to ~/.hermes/skills/ at install)
│   ├── aider/SKILL.md                 (NEW: local impl of Hermes #534)
│   ├── brain-query/SKILL.md           (NEW)
│   ├── brain-ingest/SKILL.md          (NEW)
│   ├── brain-research/SKILL.md        (NEW)
│   ├── workshop-build/SKILL.md        (NEW: wraps workshop.graph)
│   └── ... 10 Tier-1 ports from ~/.claude/skills/ (commit, ubiquitous-language, ...)
├── workshop/                          (Python package)
│   ├── __init__.py
│   ├── graph.py                       (LangGraph StateGraph + SqliteSaver)
│   ├── state.py                       (TypedDict)
│   ├── coder.py                       (Coder ABC + AiderAdapter)
│   ├── nodes/
│   │   ├── triage.py                  (Router P5)
│   │   ├── planner.py                 (Planner-loop P2)
│   │   ├── coder.py                   (Generator+Critic P4)
│   │   ├── reviewer.py
│   │   └── pr_open.py                 (interrupt_before HITL)
│   ├── ledger.py                      (two-ledger writer)
│   └── cost.py                        (cost circuit breaker)
├── scripts/
│   ├── audit-claude-skills.py
│   ├── smoke-build.py
│   └── install.sh
├── deploy/
│   └── systemd/uws-hermes.service
└── tests/
    └── test_graph.py
```

---

## Verification matrix (Phase 1 done-criteria)

| # | Test | How to verify |
|---|------|---------------|
| V1 | Hermes service is alive | `systemctl status uws-hermes` → `active (running)` |
| V2 | Telegram bot reachable (rotated token) | Send `/start` → bot replies within 5s |
| V3 | Triage node classifies | Send `/build foo`, `/fix https://github.com/...`, plain "hi" — each routes to correct branch |
| V4 | Brain HTTP integration | `hermes skill run brain-query --question "what is PARA"` returns a synthesized answer |
| V5 | Aider subprocess + architect/editor split | `hermes skill run aider --task "echo to file"` returns a diff; cost log shows two LLM calls (cloud-sonnet + private-worker) |
| V6 | LangGraph spine runs end-to-end (no HITL pause) | `python -m workshop.graph "trivial task"` reaches `pr_open` node and emits `interrupt_before` event |
| V7 | HITL gate round-trip | `/build` flow pauses at `pr_open`; Telegram inline buttons appear; tapping Approve resumes graph; tapping Reject aborts cleanly with state preserved |
| V8 | PR created end-to-end (`/build`) | `/build "add hello.md to test-repo"` → PR URL posted to Telegram within ~5 minutes |
| V9 | PR created end-to-end (`/fix`) | `/fix https://github.com/caiobellizzi/test-repo/issues/1` → matching PR opened linking the issue |
| V10 | Two-ledger pattern | `ls ~/.ultra-workshop/tasks/<task-id>/` shows `task_ledger.md` + `progress_log.jsonl`; jsonl has one event per node transition |
| V11 | Cost ledger updated | After a `/build`, `cat /srv/second-brain/_system/cost-ledger.md` shows new workshop entry with per-node breakdown |
| V12 | ADR write-back | After PR creation, `ls /srv/second-brain/_system/workshop-adrs/` shows new ADR for the task |
| V13 | Cost cap enforced | Force a synthetic spend ≥ $18; next `/build` refuses with "budget exhausted, try tomorrow" message |
| V14 | LangGraph checkpoint resume | Mid-`/build` (paused at HITL), `systemctl restart uws-hermes`; tapping Approve from Telegram completes the flow without restarting from triage |
| V15 | Brain Telegram is OFF | `systemctl status uab-telegram` → `inactive (dead)`; no dual gateway responses |
| V16 | MCP servers loaded in Hermes | `hermes mcp list` shows github, context7, crawl4ai, hostinger-api, google-workspace |
| V17 | Local model usage | Cost ledger shows ≥80% of tokens routed to `private-worker` (LM Studio) — confirms cost discipline working |
| **V18** | **Flow A end-to-end** (user fix → ADR) | After `/fix` on Telegram, `ls /srv/second-brain/_system/workshop-adrs/` shows new ADR with frontmatter `workshop.task_id`, `workshop.status: done`, `workshop.pr_url`, `system.created_by: workshop` |
| **V19** | **Flow B end-to-end** (Brain triggers Workshop) | Create a synthetic `vault/_system/lint-report.md` with frontmatter `workshop.action: link-orphans` → wait one bug-scan cycle (≤4h, force-run for test) → Workshop logs show it dispatched to link-orphans skill; Telegram approval prompt appears |
| **V20** | **Flow D + E roundtrip** (nightly-tests → digest → user → fix) | Force-run nightly-tests with a known-failing test repo → vault/_system/workshop-routines/nightly-tests/ contains report → force-run Brain's digest → digest mentions the failure → user-tagged `workshop.action: fix-bug` triggers workshop-fix next bug-scan cycle |
| **V21** | **Shared cost ledger working** | After mixed Brain + Workshop activity, `grep "source: workshop" /srv/second-brain/_system/cost-ledger.md` and `grep "source: brain"` both return rows; circuit breaker reads the combined total |
| **V22** | **Trust policy symlink** | `readlink /opt/ultra-workshop/workshop/trust_shared.py` returns `/opt/ultra-agents-brain/ultra_brain/trust.py`; `python -c "from workshop import trust_shared; print(trust_shared.classify_action('git push'))"` returns expected risk tier |
| **V23** | **Integration contract present** | `cat /srv/second-brain/_system/integration-contract.md` exists and matches the vocabulary table in this plan |
| **V24** | **No cron overlap** | `systemctl list-timers uab-*` shows monitor/digest/review only; `hermes cron list` shows daily-research/nightly-tests/bug-scan only; no duplicate purposes |

---

## Risks and mitigations

| Risk | Severity | Mitigation |
|------|----------|------------|
| VPS RAM exhaustion when Hermes + Brain + LiteLLM + Postgres + LangGraph all running | High | Phase 1 coder is Aider subprocess (~200MB), not OpenHands Docker. LangGraph runs in-process inside the workshop-build skill (no extra service). Monitor `free -h` after each `/build`. Add 2GB swap if needed. |
| Dual HITL surface confusion | High | L4 disables Brain's Telegram before workshop's comes up. Verification V15 enforces. |
| Hermes V0→V1 migration drift | Medium | Pin `v0.14.0` exactly in install script. Re-evaluate when v1.0.0 ships. |
| LangGraph API churn (still <1.0) | Medium | Pin `langgraph>=0.2,<0.3`. Re-test on each minor bump. |
| Aider model output drift between cloud-sonnet planner and gemma-4-e4b editor | Medium | The architect/editor mismatch can produce diffs the local model can't realize. Mitigation: log Aider's `tokens used` + `cost` to ledger; fall back to `cloud-sonnet` editor if local model fails N times. Add as Phase 1.5 if observed. |
| Cost runaway from infinite replan loop in planner node | Medium | Hard cap: `max_replans=3` in planner-node code. Daily budget circuit breaker in `workshop/cost.py` checks ledger before every LLM call. |
| LangGraph checkpoint state desync with Hermes session | Medium | Single-source-of-truth: LangGraph checkpoint = canonical task state; Hermes session = canonical user-conversation state. Cross-link via `task_id` field passed through both. |
| Brain HTTP rate limiting / overload | Low | Brain has no rate limiting today, but Phase 1 workshop is single-tenant solo dev. Address if multi-tenant ever happens. |
| Bot token leaked again | Medium | L7 forces rotation before workshop ships. Add `.env` to `.gitignore`, never commit. |
| Workshop tasks corrupt active repo | Medium | All tasks run on feature branches (`workshop/<task-id>`). Never touch `main` directly. Approval gate before push. HITL on `pr_open` node. |
| Skill audit misclassifies skills | Low | Audit is advisory — user reviews `skill-audit.json` before any port. Phase 1 ports only ~10 hand-picked Tier-1 skills regardless of audit findings. |
| Pattern overengineering temptation | Medium | Plan explicitly defers P3 (broadcast review), P8 (MoA), P9 (debate) to Phase 2+. Don't add until evidence demands. |
| LM Studio (Mac) goes offline | Low | Workshop routes via `cloud-sonnet` fallback in Aider config if `private-worker` unreachable. Falls back to all-cloud at ~5x cost; ledger circuit breaker still enforces $20/day cap. |

---

## Cost envelope (per `/build` task)

| Node | Model alias | Underlying model | Tokens (est) | Cost |
|------|-------------|-----------------|--------------|------|
| triage | `cheap-worker` | Haiku-class | 1K | $0.001 |
| planner | `cloud-sonnet` | Sonnet 4.5 | 10K | $0.020 |
| coder (Aider architect) | `cloud-sonnet` | Sonnet 4.5 | 10K | $0.020 |
| coder (Aider editor) | `private-worker` | LM Studio gemma-4-e4b | 30K | $0.000 (local) |
| reviewer | `default-worker` | Haiku-class | 5K | $0.005 |
| pr_open | `cheap-worker` | Haiku-class | 1K | $0.001 |
| Brain query / ingest | `private-worker` | LM Studio gemma-4-e4b | (varies) | $0.000 (local) |
| **Per `/build` total** | — | — | **~57K tokens** | **~$0.047** |

At $20/day cap → **~420 builds/day ceiling**. Realistic usage 3-10/day = $0.14-$0.47/day. Comfortable headroom; the constraint is task throughput, not budget.

`/fix <issue>` runs through the same pipeline; cost is comparable (planner sees issue URL + Brain context; everything else identical).

---

## Decision log from /grill-me session (2026-05-19)

| # | Question | Resolution | When resolved |
|---|----------|------------|---------------|
| Q1 | Why Hermes for Phase 1 specifically? | **Keep Hermes** — user has ~120 skills + 20 MCPs in `~/.claude/` to port; reuse value is real Phase-1 ROI, not Phase 2 vision | Grill #1 |
| Q2a | Skill+MCP port scope? | **Tier 1 (≈10 skills) + 3 new brain-bridge skills** | Grill #2 ("a, b, c") |
| Q2b | Skill-audit pass as a Phase 1 task? | **Yes — Day 1 task, before any skill ports** | Grill #2 |
| Q2c | Multi-agent topology in Phase 1? | **Yes — 5-node specialist topology from day 1** (LangGraph node cost is near-flat in N) | Grill #2 |
| Q3 | Coordination layer? | **Hermes + LangGraph in-process** inside `workshop-build` skill (Option B) | Grill #3 |
| Q4 | Coder substrate under model-agnostic constraint? | **(iv') Aider Phase 1 → OpenHands behind `Coder` adapter in Phase 2** | Grill #4 |
| Q5 | LM Studio integration? | **Already done — `private-worker` LiteLLM alias** routes to LM Link → LM Studio gemma-4-e4b on Mac | Implicit from L9 |
| Q6 | Specialist topology shape? | **5 LangGraph nodes**: triage → planner → coder → reviewer → pr_open, each with own model alias + skill subset | Grill #3+4 |
| Q7 | `/fix <issue>` priority? | **MUST in Phase 1** — same spine, different triage branch; marginal cost ~0 | Grill #4 |
| Q8 | Hermes cron Phase 1? | **Defer to Phase 2** — no scheduled tasks in scope yet | Grill — recommended; awaiting user confirm |
| Q9 | Repo visibility? | **Private** (default) | Grill — recommended; awaiting user confirm |
| Q10 | HITL ownership? | **LangGraph emits `interrupt_before`; Hermes catches → Telegram → callback resumes graph** | Grill #3 |
| Q11 | State store location? | `~/.hermes/state.db` (Hermes session) + `~/.ultra-workshop/state/checkpoints.db` (LangGraph) + `/var/lib/uab/` (Brain Agno, unchanged) | Grill #3 |
| Q12 | Bot token rotation? | **Before any deploy** (carries forward Brain's REQ-204) | Grill — confirmed by L7 |
| Q13 | Two-ledger pattern (Magentic-One)? | **Yes — `task_ledger.md` + `progress_log.jsonl` per task** under `~/.ultra-workshop/tasks/<id>/` | Grill #5 (recommended; carry forward) |
| Q14 | Event-sourcing (OpenHands V1)? | **Yes — every node transition appends to progress_log.jsonl**; replay/recovery free | Grill #5 (recommended; carry forward) |

### All open questions resolved during /grill-me session

All 7 remaining items from v2 Draft are now locked decisions L15–L21. No execute-phase parameters remain unresolved at plan-approval time.

The only operational reminders that carry forward:

- Pre-deploy: rotate Telegram bot token via BotFather `/revoke` (L7)
- Pre-deploy: create `caiobellizzi/test-workshop-sandbox` GitHub repo and generate fine-grained PAT (L17, L18)
- Day 1: run `audit-claude-skills.py` and review `skill-audit.json` + `~/.hermes/skills/translated/` before promoting any translated skill (L21)
- Day 6 (deploy): `systemctl disable --now uab-telegram` BEFORE `systemctl enable --now uws-hermes` (L4)

---

## Appendices

The four research streams that informed this plan are summarized below. Full transcripts (~12,000 words) were preserved in the discuss-phase session and are summarized for posterity here.

### Appendix A — Multi-agent patterns deep dive (10 patterns)

**Patterns 1–5 (research stream 1):**

1. **Workflow-first + Coordinate Team** — Pre-defined pipeline; leader delegates to specialists. Agno `Team(mode=TeamMode.coordinate)`, LangGraph `StateGraph + create_supervisor`, CrewAI `Crew(process=Process.hierarchical)`. Best as outer skeleton; failure mode is leader context overflow.

2. **Tasks mode / Planner loop (ReAct)** — Plan → execute → observe → replan. LangGraph `plan_step → execute_step → replan_step`, Agno `TeamMode.tasks`. Best as inner planner; failure mode is infinite replanning (Claude Code sub-agent consumed 27M tokens in 4.6h without termination in GitHub issue #15909). Cap replans hard.

3. **Broadcast Review Board** — Fan-out to N reviewers, aggregate. Agno `TeamMode.broadcast`. Best at PR review step with N=3 narrowly-scoped reviewers (security / test / architecture). Failure mode: representational collapse — same base model with different role prompts has effective rank ~2.17/3.0 (arXiv:2604.03809). Mitigation: use different instruction sets or model tiers.

4. **Generator + Critic (Self-Refine)** — Generator produces, critic evaluates, generator revises. Anthropic's term: Evaluator-Optimizer. Best inside Execute steps for per-file diffs and commit message quality. Failure mode: same-model critic agreement bias; oscillation. Mitigation: monotonically-improving score requirement; max iterations cap.

5. **Router** — Classifier dispatches to specialist handler. Anthropic's canonical example: simple → Haiku, complex → Sonnet. Agno `TeamMode.route`. Best at entrance + model-tier routing. Failure mode: routing collapse — as cost budget rises, routers default to most expensive model (arXiv:2602.03478). Mitigation: clear thresholds.

**Patterns 6–10 (research stream 2):**

6. **Graph / State Machine** — Explicit DAG with conditional edges. LangGraph is canonical; LangChain Open SWE uses this for issue→PR pipeline. Best as primary orchestration substrate; `interrupt_before=["pr_open"]` gives free HITL. Pairs with Pattern 10 (LangGraph Swarm).

7. **Blackboard** — Shared store all agents read/write. No major framework ships it first-class; LangGraph's typed state IS a blackboard. Best implicit via state graph; don't build standalone — over-engineered for solo dev.

8. **Mixture-of-Agents (MoA)** — N proposers in parallel, aggregator synthesizes. 2025 paper (arXiv:2502.00674): **Self-MoA** (same strong model, N samples) outperforms standard cross-model MoA by 6.6pp on AlpacaEval. Mixing weak models hurts. Use Self-MoA narrowly inside Review node only; 4–10× cost multiplier.

9. **Group Chat / Debate** — Agents share conversation thread. AutoGen `GroupChat`. **Documented sycophancy cascades** (arXiv:2509.05396, 2604.02668): agents flip from correct to incorrect under peer pressure. Identity bias: agents favor own outputs (arXiv:2510.07517). Reputation cooled in 2026 MAD community. Quadratic cost. **Do not use for governed production work.**

10. **Swarm** — LLM-routed handoff between specialists. OpenAI Swarm → OpenAI Agents SDK (`handoff(agent)`). LangGraph Swarm package eliminates 30–40% supervisor overhead. Hermes's `delegate_tool` is a handoff primitive. Best fit for ≤5-agent specialist topology; hard limit `max_handoffs=10` + daily budget circuit breaker mandatory.

**Cross-pattern composition (the actual production stack):**

```
Router (P5) → Workflow (P1)
  ├─ Plan:    Planner Loop (P2), max 3 replans
  ├─ Execute: Generator+Critic (P4), max 2 cycles per file
  ├─ Review:  Broadcast Board (P3), N=3 reviewers     [Phase 2+]
  └─ Publish: create PR / deploy                       [HITL gate]
```

Implemented on Graph (P6) substrate, with Blackboard (P7) implicit in state, Self-MoA (P8) narrow inside Review, and Swarm (P10) handoff semantics replacing supervisor calls. Group Chat (P9) is excluded entirely.

### Appendix B — Tool composability (Hermes + Agno + OpenHands + Claude Code + Aider)

**Composition 1 chosen: Hermes (orchestrator) + Agno Brain via HTTP + Claude Code via existing skill.**

Pairwise analysis of all 5 compositions surfaced these constraints:

- **Hermes + Agno HTTP coupling**: state duplication (Hermes FTS5 vs Agno SqliteDb) is acceptable because they record different scopes (outer orchestration vs inner agent execution). Reconciliation via idempotent tool design, not framework changes.
- **HITL collapse**: dual Telegram surfaces (Brain + Hermes) is the #1 anti-pattern. Hermes owns gateway; Brain becomes pure REST.
- **OpenHands V1 deferred**: 70+ deps, optional Docker, 4GB minimum RAM = risky on shared 4GB VPS. Use only when sandboxed untrusted-code execution becomes a real need; will require separate VPS.
- **Aider deferred**: Hermes Issue #534 (Aider skill) is open and unimplemented. Building it is a weekend's work but unnecessary for Phase 1. Aider's value (model-agnostic via LiteLLM, architect mode) is real but doesn't outweigh Claude Code's zero-friction start.
- **Multi-coder MoA (OpenHands + Aider + Claude Code together)**: operationally brittle. Three subprocess chains, shared git tree races, triply complex error handling. Use Aider architect mode (one process, two LLM calls) instead — that's MoA at minimal cost.
- **Single-stack alternatives considered**: Hermes-only (throws away working Agno Brain), Agno-only with custom Telegram (loses Hermes gateway/skills/cron). Both rejected; the HTTP-coupled composition preserves the strengths of each.

### Appendix C — Real-world coding agent architectures (case studies)

Seven systems studied; recurring primitives extracted:

1. **Cognition Devin 2.0** — Single planner-loop + isolated VM per session. Devin Wiki indexer is a separate background loop (consumed on demand) — Brain follows this pattern.
2. **OpenHands V1** — Event-sourcing + synchronous Conversation + Workspace abstraction (LocalWorkspace / DockerWorkspace / RemoteWorkspace). V0's async pub/sub had intractable ordering bugs.
3. **Manus AI** — Three-agent split (Planner / Execution / Verification) + Skills with progressive disclosure (Level 1 metadata / Level 2 instructions / Level 3 resources). Maps to existing `~/.claude/skills/` structure.
4. **Claude Agent SDK** — Reactive ReAct loop, 5-layer context compaction (60–80k effective window), 7 permission modes (plan → bypassPermissions), `PreToolUse` hook for HITL, Sessions API for resume/fork.
5. **mini-SWE-agent / Aider architect mode** — Minimal scaffold (≈100 LOC bash-only), >74% SWE-bench Verified with Gemini 3 Pro. Aider tree-sitter RepoMap + architect/editor split (planner + cheap editor).
6. **MetaGPT / CrewAI** — Structured documents as inter-agent hand-off tokens (not free-form chat). CrewAI Flows = explicit state machine for deployment pipelines.
7. **Magentic-One (Microsoft)** — Dual-loop Orchestrator with Task Ledger (strategic) + Progress Ledger (tactical) + stall detection. Safety findings (agents recruited humans via social media) drive reversibility-weighted action assessment.

**Top 5 architectural primitives to steal for workshop:**

1. **Magentic-One two-ledger pattern** — `task_ledger.md` (goal + plan) + `progress_log.jsonl` (executed actions). Cheap, big debuggability win.
2. **OpenHands V1 event-sourcing** — Append-only logs as source of truth. Replay/recovery free.
3. **Manus progressive skill disclosure** — Three-level skill loading; minimal context waste.
4. **Claude Agent SDK PreToolUse hook for HITL** — Hermes's `clarify` callback fills the same role.
5. **mini-SWE-agent minimalism** — Start bash-only. Add tools only when bash demonstrably fails.

### Appendix E — Tool Translation Map (for `audit-claude-skills.py`)

The auto-translate pass (L21) walks each `requires-translation`-tagged skill's body and applies the substitutions below. Substitutions are **textual** (regex + word boundaries) and **conservative**: when a Claude tool has no clean Hermes equivalent, the skill is re-tagged `requires-manual-port` and emitted to `~/.hermes/skills/translated/_manual/` for human review rather than auto-translated.

#### Direct mappings (safe to auto-translate)

| Claude Code tool | Hermes equivalent | Notes |
|------------------|-------------------|-------|
| `Read` | `read_file` | Path argument syntax compatible; offset/limit args may need shimming |
| `Write` | `write_file` | Same semantics; Hermes validates parent dir exists |
| `Edit` | `edit_file` (Hermes provides `replace_in_file`) | `old_string`/`new_string` syntax differs slightly — translator emits a code-comment warning |
| `Bash` / `Bash command` | `terminal` | Hermes `terminal` supports `pty=true/false`; default is `false` (matches Claude's behavior) |
| `Grep` | `search` (Hermes ripgrep wrapper) | `pattern` / `path` / `glob` args compatible |
| `Glob` | `find_files` | Hermes built-in; pattern syntax identical |
| `WebFetch` | `http_request` (`method=GET, url=..., extract_with_prompt=...`) | Hermes doesn't fold extraction into the tool; translator emits a 2-step pattern (`http_request` → LLM summary call) |
| `WebSearch` | `web_search` | Direct rename; query syntax identical |

#### Tag-only (no auto-translate; emit to `_manual/` for human porting)

| Claude Code tool | Why not auto-translated |
|------------------|------------------------|
| `TaskCreate` / `TaskUpdate` / `TaskList` | Hermes has no first-class task list. Manual port = invent task tracking via Hermes session state or skip |
| `AskUserQuestion` | Hermes uses `clarify` callback in run loop; semantics differ enough to require manual review |
| `Skill` | Recursive skill invocation — Hermes calls skills by name via different syntax; needs manual rewrite |
| `ExitPlanMode` | Claude-Code-only construct (plan mode is harness-level); has no Hermes equivalent |
| `Agent` (spawn subagent) | Translates to Hermes `delegate_task` BUT semantics differ (max depth 2, Level 0 only); manual review |
| `NotebookEdit` / `ReadMcpResourceTool` / `ListMcpResourcesTool` | Niche or MCP-specific; manual case-by-case |

#### Hermes-only tools that auto-translate WON'T introduce (Phase 1 scope)

`http_request`, `terminal`, `delegate_task`, `web_search`, MCP tools — these are added when a skill that *should* use them is hand-written, not via auto-translate of existing Claude skills.

#### Audit-script output structure

```json
{
  "audit_run_at": "2026-05-20T10:00:00Z",
  "claude_skills_root": "/Users/caiobellizzi/.claude/skills/",
  "hermes_translated_root": "/Users/caiobellizzi/.hermes/skills/translated/",
  "totals": {"scanned": 121, "agent_agnostic": 14, "auto_translated": 38, "requires_manual_port": 47, "claude_specific_skip": 22},
  "skills": [
    {
      "name": "commit",
      "path": "/Users/caiobellizzi/.claude/skills/commit/SKILL.md",
      "classification": "agent_agnostic",
      "tools_referenced": [],
      "translated_to": null,
      "notes": "No tool references; copies as-is to ~/.hermes/skills/commit/"
    },
    {
      "name": "triage-issue",
      "path": "/Users/caiobellizzi/.claude/skills/triage-issue/SKILL.md",
      "classification": "auto_translated",
      "tools_referenced": ["Read", "Grep", "Bash"],
      "translations_applied": [{"from": "Read", "to": "read_file"}, {"from": "Grep", "to": "search"}, {"from": "Bash", "to": "terminal"}],
      "translated_to": "/Users/caiobellizzi/.hermes/skills/translated/triage-issue/SKILL.md",
      "notes": "Translated cleanly. Smoke-test before promoting to ~/.hermes/skills/."
    },
    {
      "name": "gsd-plan-phase",
      "path": "/Users/caiobellizzi/.claude/skills/gsd-plan-phase/SKILL.md",
      "classification": "requires_manual_port",
      "tools_referenced": ["TaskCreate", "AskUserQuestion", "Read", "Edit"],
      "untranslatable_tools": ["TaskCreate", "AskUserQuestion"],
      "translated_to": "/Users/caiobellizzi/.hermes/skills/translated/_manual/gsd-plan-phase/SKILL.md",
      "notes": "Contains 2 untranslatable Claude-Code-only tools. Manual rewrite required."
    }
  ]
}
```

**Safety rules in the audit script:**

1. **Never write to `~/.hermes/skills/<name>/` directly** — always to `~/.hermes/skills/translated/<name>/`. Promotion requires explicit user action (`cp -r` after smoke-test) so a broken translation can never silently shadow a working skill.
2. **Emit a `TRANSLATION_NOTES.md` per auto-translated skill** documenting every substitution made + line numbers. User reviews before promoting.
3. **Dry-run mode default** — `--dry-run` shows what would be translated without writing; user reruns with `--apply` to commit changes.
4. **Idempotent re-runs** — running the audit twice on the same `~/.claude/skills/` produces identical output (deterministic ID hashing, stable JSON key ordering).

### Appendix D — Brain HTTP surface (workshop's contract)

Workshop calls Brain via these endpoints (default Agno 2.6.7 routes):

| Endpoint | Use case |
|----------|----------|
| `POST /agents/query/runs` | Get vault context for a coding task (returns synthesized answer with citations) |
| `POST /agents/research/runs` | Trigger multi-angle research for a task that requires it (HITL-gated on Brain side) |
| `POST /agents/ingest/runs` | Write ADR / lesson learned back to vault after PR creation (HITL-gated on Brain side) |
| `POST /agents/curator/runs` | Cost-ledger updates: `message=record-cost&amount=0.12&task=workshop-build-123` |
| `POST /agents/{id}/runs/{run_id}/continue` | Resume a paused Brain agent (when workshop needs to forward an approval) |
| `GET /health` | Liveness check before any workshop task starts |

**Auth**: None on Brain today. Workshop and Brain share the loopback interface; trust model is single-host. If workshop ever moves to a separate VPS, enable Agno `os_security_key` and pass `Authorization: Bearer ...` from Hermes skills.

**Concurrency**: Brain has no rate limiting; single-tenant solo dev is fine. If workshop spawns parallel tasks in Phase 2+, add per-second cap in Hermes skill code.

**Vault contract** (read by workshop, written by Brain only):
- `VAULT_ROOT` resolves via `UAB_VAULT_PATH` → `SECOND_BRAIN_DIR` → `./vault` (already wired)
- PARA layout: `00-Projects/`, `01-Areas/`, `02-Resources/`, `03-Archives/`, `Inbox/`, `_system/`
- Workshop writes only to `_system/workshop-adrs/` and `_system/cost-ledger.md` (via Brain's ingest agent)

---

## References

**Hermes Agent:**
- [Hermes Agent GitHub](https://github.com/nousresearch/hermes-agent)
- [Hermes Agent Docs](https://hermes-agent.nousresearch.com/docs/)
- [Hermes Agent Architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture)
- [Issue #477 — OpenHands skill proposal](https://github.com/NousResearch/hermes-agent/issues/477)
- [Issue #534 — Aider skill proposal](https://github.com/NousResearch/hermes-agent/issues/534)

**Agno:**
- [Agno docs](https://docs.agno.com)
- [Agno AgentOS](https://www.agno.com/agentos)
- [Agno HITL](https://docs.agno.com/agent-os/usage/hitl)

**OpenHands:**
- [OpenHands V1 GitHub](https://github.com/OpenHands/OpenHands)
- [OpenHands Software Agent SDK](https://github.com/OpenHands/software-agent-sdk)
- [OpenHands V1 SDK paper (arXiv:2511.03690)](https://arxiv.org/abs/2511.03690)

**Claude Agent SDK:**
- [Claude Agent SDK overview](https://code.claude.com/docs/en/agent-sdk/overview)
- [Building agents with Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk)
- [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

**Aider:**
- [Aider docs](https://aider.chat/docs/)
- [Aider architect mode](https://aider.chat/docs/usage/modes.html)

**Multi-agent pattern primary sources:**
- [Anthropic — Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [OpenAI — A Practical Guide to Building Agents (PDF)](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf)
- [LangGraph — Planning Agents](https://www.langchain.com/blog/planning-agents)
- [LangGraph Swarm](https://github.com/langchain-ai/langgraph/tree/main/libs/swarm)
- [LangChain Open SWE](https://blog.langchain.com/introducing-open-swe-an-open-source-asynchronous-coding-agent/)

**Real-world systems:**
- [Cognition Devin 2.0](https://cognition.ai/blog/devin-2)
- [Manus AI architecture (arXiv:2505.02024)](https://arxiv.org/abs/2505.02024)
- [Magentic-One (Microsoft Research)](https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/)
- [Magentic-One paper (arXiv:2411.04468)](https://arxiv.org/pdf/2411.04468)
- [MetaGPT (arXiv:2308.00352)](https://arxiv.org/html/2308.00352v6)
- [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent)

**Multi-agent failure modes:**
- [Self-Refine (arXiv:2303.17651)](https://arxiv.org/abs/2303.17651)
- [Why Do Multi-Agent LLM Systems Fail? — MAST (arXiv:2503.13657)](https://arxiv.org/html/2503.13657v1)
- [Rethinking MoA: Is Mixing Different LLMs Beneficial? (arXiv:2502.00674)](https://arxiv.org/abs/2502.00674)
- [Talk Isn't Always Cheap — MAD failure modes (arXiv:2509.05396)](https://arxiv.org/pdf/2509.05396)
- [Too Polite to Disagree — Sycophancy in MAS (arXiv:2604.02668)](https://arxiv.org/html/2604.02668v1)
- [Representational Collapse in LLM Committees (arXiv:2604.03809)](https://arxiv.org/pdf/2604.03809)
- [When Routing Collapses (arXiv:2602.03478)](https://arxiv.org/abs/2602.03478)
- [GraphTracer — DAG failure tracing (arXiv:2510.10581)](https://arxiv.org/pdf/2510.10581)
- [Measuring Identity Bias via Anonymization (arXiv:2510.07517)](https://arxiv.org/html/2510.07517v1)

**Brain ground truth (this repo):**
- `/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/.planning/PROJECT.md`
- `/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/.planning/ROADMAP.md`
- `/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/.planning/STATE.md`
- `/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/.planning/REQUIREMENTS.md`
- `/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/.planning/phases/01-ultra-brain-agno/01-01-PLAN.md`
- `/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/agentos/` (5 agents, 7 tools)
- `/Users/caiobellizzi/Documents/Projects/ultra-agents-brain/channels/telegram_adapter.py` (reference HITL pattern)

---

## Execution gate

Before this plan begins execution (creating the sibling repo, installing Hermes, etc.), the four open questions above (coder, `/fix` priority, repo visibility, Phase 1 cron) should have explicit answers. They do not block plan approval; they parameterize the execute-phase.

After approval, the natural next steps are:
1. `/gsd:execute-plan` (or manual) to run the bootstrap checklist
2. Track Phase 1 against the verification matrix
3. After all V1–V12 pass, tag `v0.1.0`, write a short retro to Brain via the `brain-ingest` skill, and decide whether to start Phase 2 (broadcast review board / Aider integration / specialist topology).
