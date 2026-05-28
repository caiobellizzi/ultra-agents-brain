# Ultra-Workshop: Multi-Agent Architecture Pattern Research

> Research scope: Five canonical patterns for the ultra-workshop autonomous coding/PR/deploy agent team.
> Orchestrator: NousResearch Hermes Agent. Substrate candidates: OpenHands V1 / Claude Code subprocess / Aider.
> Brain: Agno AgentOS at 127.0.0.1:7000. Date: 2026-05-19.

---

## Pattern 1 — Workflow-first + Coordinate Team

### a. Canonical Definition

A **pre-defined execution plan** (the workflow) drives the top-level sequence of steps; at each step a **team leader** delegates to one or more specialist agents and synthesizes their outputs before proceeding to the next step. Agent A (leader) decomposes the goal into steps, Agent B/C/D (workers) execute assigned steps, and they coordinate via a shared state object that the leader controls.

---

### b. Reference Implementations and Frameworks

| Framework | Support level | API surface |
|---|---|---|
| **Agno** | First-class | `Team(mode=TeamMode.coordinate)` + `Workflow(steps=[...])`. `TeamMode.coordinate` is the default; `TeamMode.broadcast` fans out. `Workflow` wraps sequential steps. `Loop`, `Parallel`, `Condition`, `Router` constructs available inside a `Workflow`. |
| **LangGraph** | First-class | `StateGraph` nodes + edges. `create_supervisor()` from `langgraph-supervisor` library. Supervisor calls workers as tools (`handoff_tool_prefix`). Compile with `checkpointer` for persistence. |
| **CrewAI** | First-class | `Crew(process=Process.sequential)` or `Process.hierarchical` with `manager_agent=`. `planning=True` flag triggers an internal planning step before the crew executes. |
| **AutoGen** | Supported | `GroupChat` + `GroupChatManager`; or a `ConversableAgent` with `SelectorGroupChat`; AutoGen 0.4 adds modular components. No opinionated workflow wrapper — you build it with `RoundRobinGroupChat`. |
| **OpenAI Agents SDK** | First-class | Manager pattern: central LLM orchestrates specialized agents as tool calls. `Handoff` objects wire agent transitions. Workflows expressed in Python; no graph DSL. |
| **Hermes Agent** | Partial (v0.12) | `delegate_task` spawns isolated child agents. Level 0 only (isolated, max depth 2). Shared memory, result-passing, and DAG topology are Phase 1–2 of the [planned multi-agent upgrade](https://github.com/NousResearch/hermes-agent/issues/344). Phase 3 adds pre-defined agent archetypes (Researcher, Developer, Reviewer, Synthesizer). |
| **LangChain/LangGraph-JS** | Supported | Same graph-based approach in TypeScript. |

**What's missing in Hermes**: Shared state between children, child-to-child communication, and retry-on-failure for sub-agents. These are roadmap items for 2026 Q2–Q3.

---

### c. Where It Shines (coding-agent context)

This is the natural outer shell of any multi-step coding workflow. Example steps for ultra-workshop:

1. **Triage** — parse issue/PR intent, route to skill
2. **Plan** — decompose into file-level tasks
3. **Execute** — delegate tasks to coder agent(s)
4. **Test** — run test suite, collect failures
5. **Review** — send diff to reviewer agent
6. **Publish** — open PR or deploy

Each step is deterministic; the workflow transitions are in code, not in LLM reasoning. This gives auditability that pure ReAct loops lack. It is especially strong for **CI/CD-like pipelines** where steps have hard preconditions (tests must pass before PR opens).

Agno's `Workflow` with `Parallel` construct means the Execute step can fan out file edits concurrently while the leader waits for all to complete before advancing — matching CI parallelism semantics exactly.

---

### d. Failure Modes

- **Context overflow in the leader**: The coordinator accumulates context from every worker's output. At 5 workers × 10 tool calls each, the leader's context can balloon. Agno docs warn: *"Get coordination wrong and you've built a more expensive failure mode."* [beam.ai's production analysis](https://beam.ai/agentic-insights/multi-agent-orchestration-patterns-production) recorded costs scaling from $0.50 to $50,000/month in orchestrator-worker systems at scale.
- **Cascading error propagation**: A bad Plan step output poisons every downstream step. No backtracking in sequential workflows unless explicitly coded. CrewAI's sequential process has this by design.
- **Token overhead**: A 3-agent pipeline can consume 29,000 tokens versus 10,000 for an equivalent single-agent approach — a ~3× overhead ([beam.ai](https://beam.ai/agentic-insights/multi-agent-orchestration-patterns-production)).
- **Coordination overhead latency**: 4-agent pipelines accumulate ~950 ms of coordination overhead even if actual processing takes 500 ms.
- **Hermes-specific**: `delegate_task` currently isolates children; if a child hangs or returns garbage, the parent has no visibility until the child returns.

---

### e. Fit for Ultra-Workshop

**Use this as the top-level skeleton for the entire workshop pipeline.** Every other pattern below slots in as a node inside this workflow. It is the backbone, not a component.

---

### f. Composition Opportunities

- Pattern 2 (planner loop) plugs into the **Plan** step — the planner loop generates the ordered task list.
- Pattern 3 (broadcast review board) replaces the monolithic **Review** step with a fan-out to N reviewers.
- Pattern 4 (generator+critic) replaces the **Execute→Test** loop with a tighter diff/critique cycle per file.
- Pattern 5 (router) sits at the **Triage** step, classifying incoming work before the workflow starts.
- The `Workflow(steps=[planner, coordinator, reviewer])` wraps all of them.

---

### g. Cost & Latency Profile

| Dimension | Estimate |
|---|---|
| LLM calls per task | 5–15 (one per workflow step + per delegation) |
| Latency | Medium–High (sequential steps accumulate; parallelism within steps helps) |
| Budget fit | Moderate risk. With a $20/day budget at Sonnet 4.5 pricing (~$3/1M tokens), a 5-step workflow with 4 workers × 10K tokens each = ~200K tokens ≈ $0.60/task. Allows ~33 tasks/day before budget pressure. Add CrewAI-style orchestrator overhead (30–50% extra tokens) and the ceiling drops to ~25 tasks/day. |

---

---

## Pattern 2 — Tasks Mode / Planner Loop (ReAct-style)

### a. Canonical Definition

An agent receives a goal, **generates a plan** (ordered list of steps or a DAG), **executes each step** (calling tools, subagents, or code runners), **observes** the result, and **replans** if execution diverges from expectations — repeating until the goal is satisfied or a stopping condition fires. Agent A (planner) emits a task list; Agent B (executor, optionally a cheaper model) walks the list one step at a time; Agent A (replanner) assesses whether to continue or respond.

---

### b. Reference Implementations and Frameworks

| Framework | Support level | API surface |
|---|---|---|
| **LangGraph** | First-class | `plan-and-execute` tutorial; `plan_step → execute_step → replan_step` nodes with `should_end` conditional edge. DAG variant: task parameters as `${N}` variables, topological scheduling. Official blog post: [langchain.com/blog/planning-agents](https://www.langchain.com/blog/planning-agents). |
| **Agno** | First-class | `TeamMode.tasks` — "decompose work into discrete, trackable units assigned to individual agents." Also exposed via `Workflow(steps=[...])` with `Loop` construct for the replan cycle. |
| **AutoGen** | Supported | `Planner` agent + `Engineer` agent pattern; `SelectorGroupChat` picks the right agent per step. No explicit "replan" primitive — handled via `ConversableAgent` continuation logic. |
| **OpenAI Agents SDK** | Partial | Manager pattern can implement this; no dedicated plan-execute primitive. ReAct loop implicit in tool-calling loop. |
| **CrewAI** | Partial | `planning=True` on `Crew` adds a planning step; but the planner cannot replan mid-execution without custom flow logic. |
| **Hermes Agent** | Native (single-agent) | The core `AIAgent` loop in `run_agent.py` is a synchronous think-act-observe loop. Multi-step replanning requires the planned Phase 2 meta-agent replanning feature. |
| **LangChain ReWOO** | Variant | Plan once with placeholders → run all tools in parallel → synthesize. Only 2 LLM calls total (5× token efficiency over ReAct) but **no replanning** — breaks on unexpected tool output. |

**Anthropic's classification**: This maps to their *Orchestrator-Workers* pattern when the planner is dynamic — "subtasks aren't pre-defined, but determined by the orchestrator based on the specific input" ([anthropic.com/engineering/building-effective-agents](https://www.anthropic.com/engineering/building-effective-agents)).

---

### c. Where It Shines (coding-agent context)

Ideal for **open-ended issue resolution** where the full scope of changes cannot be known upfront — e.g., a refactoring task that reveals 7 files need changing only after the first grep. The planner loop's replanning step is the key differentiator: if the test runner reports 3 new failures, the replanner generates a corrective sub-plan instead of abandoning.

Concrete use in ultra-workshop: the Plan step of the outer Workflow (Pattern 1) runs a planner loop. The planner emits a task DAG, execution begins, and when a file-edit tool call fails (merge conflict, missing import), the replanner inserts a fix-step before proceeding. This is exactly the pattern used by OpenHands V1 (`Conversation` + iterative execution).

OpenHands scores ~77% on SWE-Bench Verified with Claude Sonnet 4.5 precisely because it uses this pattern — it doesn't know upfront which files to edit; the agent discovers them through tool calls.

---

### d. Failure Modes

- **Plan brittleness**: If the world changes mid-execution (another agent pushes to the same branch), the plan becomes stale. Mitigation: add re-plan triggers on `git` conflicts.
- **Planner-executor capability mismatch**: Using a strong model for planning and a weak model for execution causes the executor to misread the plan. LangChain recommends the executor model have sufficient tool-use capability.
- **Infinite replanning**: Every replan that fails spawns another replan. Without a hard iteration cap, this becomes the *Ouroboros Bug* — documented in GitHub #15909 as a Claude Code sub-agent that consumed **27 million tokens over 4.6 hours** without a cap.
- **Over-optimization for plan completion vs. user goal**: The agent satisfies plan steps that are now outdated relative to the original intent. Mitigation: anchor replanning prompt to original goal, not just current step status.
- **Context window saturation**: Each observation appended to the ReAct loop grows the context. For complex tasks, this hits the 200K-token limit before completion. LangGraph's `checkpointer` persists state and allows resumption; Agno's `Workflow` sessions do the same.
- **MAST taxonomy**: The three most common failure modes in plan-execute agents are step repetition (FM-1.3), reasoning-action discrepancies (FM-2.6), and missing termination signals (FM-1.5) — each a system design problem, not a model quality problem.

---

### e. Fit for Ultra-Workshop

**Use this as the inner planning engine inside the Plan step of the outer Workflow.** Specifically: the Plan node of the workshop pipeline should be a planner-loop agent that emits a task DAG before the Execute step begins. Cap iterations at 3 replans maximum; if the third replan also fails, escalate to human-in-the-loop.

---

### f. Composition Opportunities

- Wraps naturally inside Pattern 1 (Workflow) as the dynamic planning node.
- Can invoke Pattern 4 (generator+critic) as the execution primitive for each plan step (generate diff → critique → refine).
- Pattern 5 (router) can classify steps in the plan and dispatch each to the right specialist executor.
- Can be the fallback inside a Pattern 5 router: "if unclassifiable, use planner loop."

---

### g. Cost & Latency Profile

| Dimension | Estimate |
|---|---|
| LLM calls per task | 3–10 for planning + 1–3 per execution step + 1–2 for replan decisions |
| Latency | Medium (planning is one LLM call; execution steps run fast if executor is a lightweight model) |
| Budget fit | Good if strong model used only for planner/replanner. ReWOO variant (no replanning) cuts to 2 LLM calls total — optimal for tasks where the plan is likely correct. At $20/day budget: planning with Sonnet + execution with Haiku ≈ $0.30/task → ~66 tasks/day. |

---

---

## Pattern 3 — Broadcast Review Board

### b. Note on Naming

This pattern has no single canonical name in the literature. It overlaps with:
- Anthropic's **Parallelization / Voting** subpattern ([anthropic.com/engineering/building-effective-agents](https://www.anthropic.com/engineering/building-effective-agents))
- **Fan-out / Fan-in** in beam.ai's taxonomy
- **Multi-Agent Debate** in AutoGen and LangGraph
- **Mixture-of-Agents (MoA)** in the research literature
- **LLM Committee / Consensus** in arXiv:2604.03809

In Agno's API, it maps to `TeamMode.broadcast`.

### a. Canonical Definition

A single artifact (PR diff, plan, code change) is **broadcast simultaneously to N independent reviewer agents**; each produces a verdict (pass/fail/concerns) and rationale; a **synthesizer** (or majority vote rule) aggregates responses into a final judgment. Agent A (broadcaster/leader) fans out the task to Agents B₁…Bₙ in parallel; each returns an independent evaluation; Agent A (or a separate Synthesizer) aggregates into one decision.

---

### b. Reference Implementations and Frameworks

| Framework | Support level | API surface |
|---|---|---|
| **Agno** | First-class | `Team(mode=TeamMode.broadcast)` — leader gets `delegate_task_to_members` tool that sends to ALL agents simultaneously. |
| **LangGraph** | First-class | Fan-out edges from one node to N parallel reviewer nodes; fan-in via `RunnableLambda` or a dedicated aggregation node. `Parallel` in LangChain Expression Language. |
| **AutoGen** | Supported | `RoundRobinGroupChat` with N critic agents; or `SelectorGroupChat` with explicit review turn order. |
| **CrewAI** | Partial | No native broadcast; simulate by assigning same task to N agents with `Process.sequential` and explicit context injection — verbose but functional. |
| **OpenAI Agents SDK** | Partial | No native fan-out; build it by calling N agents concurrently via `asyncio.gather`. |
| **Hermes Agent** | Partial | `delegate_task` to multiple children in parallel; children are isolated and can't share state. No native aggregation primitive — parent must synthesize children's summaries. |

**Research basis**: Madaan et al. (Self-Refine, arXiv:2303.17651) showed ~20% average improvement from iterative feedback. The N-Critics extension (arXiv:2310.18679) showed ensemble critics outperform single-critic refinement. Anthropic notes the voting subpattern runs "the same task multiple times to get diverse outputs" and is useful when "multiple independent agents checking each other's work" increases confidence.

---

### c. Where It Shines (coding-agent context)

Best applied at the **PR review step** of the workshop pipeline. After the coder agent produces a diff, broadcasting it to 3 specialized reviewers in parallel:
- **Security reviewer**: checks for injection, hardcoded secrets, unsafe deserialization
- **Test coverage reviewer**: checks that new code has tests, identifies untested branches
- **Architecture reviewer**: checks for pattern violations, naming, coupling

Each reviewer produces structured feedback (PASS / NEEDS_CHANGE + specific line comments). The synthesizer aggregates: if any reviewer returns NEEDS_CHANGE, the diff is sent back to the coder. This is more reliable than a single "review everything" agent because each reviewer has a narrow, well-defined scope.

Concrete evidence: ICLR 2025 study with 20,000 reviews found that LLM reviewer feedback led 27% of human reviewers to update their reviews — validating that structured automated review is actionable in practice.

---

### d. Failure Modes

- **Echo chamber / sycophancy** (arXiv:2509.05396, "Talk Isn't Always Cheap"): When the majority of reviewer agents provide the same answer — regardless of correctness — minority agents conform. A single confident wrong reviewer can drag the group toward an incorrect consensus.
- **Representational collapse** (arXiv:2604.03809): When all N reviewers are the same base model with different role prompts, pairwise cosine similarity of reasoning traces is ~0.888 and effective rank is 2.17/3.0 — meaning the "3 reviewers" are providing barely more information than 2. This is measurably worse on harder tasks.
- **Weaker agent contamination** (arXiv:2509.05396): Including a weaker model in the reviewer pool degrades collective performance; the weaker agent produces confident-sounding but incorrect feedback that anchors other reviewers.
- **Aggregation hallucination**: When reviewer opinions conflict, LLM-based synthesizers can invent a consensus that no individual reviewer actually held ([beam.ai](https://beam.ai/agentic-insights/multi-agent-orchestration-patterns-production)).
- **API rate limit collision**: N agents firing simultaneously hit collective rate limits even if each individual agent is within bounds.
- **Cost explosion**: N reviewers = N LLM calls per review. At N=5 and 50 reviews/day = 250 extra LLM calls. At Sonnet pricing with 10K token diffs, this is ~$7.50/day just for reviews.

---

### e. Fit for Ultra-Workshop

**Use this for the PR review step only, with N=3 narrowly-scoped reviewers.** Do NOT use the same base model with only role prompts — use different model tiers or genuinely different instruction sets to avoid representational collapse. Cap at 3 reviewers on a fixed budget.

---

### f. Composition Opportunities

- Sits inside Pattern 1 (Workflow) as the Review node.
- Can wrap Pattern 4 (generator+critic): if any reviewer returns NEEDS_CHANGE, the generator+critic loop fires on the specific file/section flagged.
- Pattern 5 (router) can pre-filter which reviewers to invoke based on the diff type (infra change → security + ops reviewers only; pure docs → no security review needed).

---

### g. Cost & Latency Profile

| Dimension | Estimate |
|---|---|
| LLM calls per review | N (parallel, so wall-clock = 1 call's latency) |
| Latency | Low (parallel execution; total wall-clock ≈ single reviewer time) |
| Budget fit | Moderate pressure. N=3 reviewers × 10K tokens × $3/1M = $0.09/review. At 50 reviews/day ≈ $4.50/day on reviews alone. N=5 pushes to $7.50/day — leaves little room for execution costs. |

---

---

## Pattern 4 — Generator + Critic (Self-Refine)

### a. Canonical Definition

Agent A (generator) produces an artifact (code diff, commit message, PR description); Agent B (critic) evaluates it against explicit criteria and returns structured feedback; Agent A revises the artifact using that feedback; the cycle repeats until the critic returns PASS or a maximum iteration count is reached. Anthropic calls this the **Evaluator-Optimizer** pattern; the Self-Refine paper (Madaan et al., 2023) proved it with a single model playing all three roles.

---

### b. Reference Implementations and Frameworks

| Framework | Support level | API surface |
|---|---|---|
| **Anthropic (conceptual)** | First-class pattern | Evaluator-Optimizer: "one LLM call generates a response while another provides evaluation." Python snippet: `evaluator_result = PASS | NEEDS_IMPROVEMENT | FAIL`. ([anthropic.com/engineering/building-effective-agents](https://www.anthropic.com/engineering/building-effective-agents)) |
| **AutoGen** | First-class | `Critic` agent role (part of canonical `Engineer + Critic` pattern). `CriticAgent` in AutoGen provides review and feedback. |
| **LangGraph** | First-class | Reflexion pattern: generator node → evaluator node → conditional edge back to generator. [`Reflexion` tutorial](https://langchain-ai.github.io/langgraphjs/tutorials/plan-and-execute/plan-and-execute/) wraps Self-Refine in a graph. |
| **CrewAI** | Supported | No dedicated critic primitive, but `Process.hierarchical` with a manager agent performing quality review implements it. `planning=True` adds a pre-execution critic pass. |
| **Agno** | Supported | `Workflow` with a `Loop` construct: `Step(generator) → Step(critic) → Condition(pass) → exit or loop`. |
| **OpenAI Agents SDK** | Supported | Manager + worker; manager reviews output and calls worker again if needed. No dedicated critic API. |
| **Hermes Agent** | Native (single-agent) | The `Curator` in v0.12 grades and refines skills. The reviewer skill (`skills/brain.review/`) in the ultra-agents-brain repo implements this for Brain. Extending to workshop diffs is natural. |

**Research basis**: Self-Refine (arXiv:2303.17651) — same LLM plays generator, feedback provider, and refiner; ~20% improvement on 7 tasks. N-Critics (arXiv:2310.18679) — ensemble critics outperform single-critic. IF-CRITIC (arXiv:2511.01014) — checklist-guided critique for fine-grained instruction following.

---

### c. Where It Shines (coding-agent context)

This is the **tightest feedback loop in the workshop** and shines at two specific nodes:

1. **Diff generation loop**: Coder agent generates a diff → critic checks against a rubric (does it compile? does it pass linting? does it address the issue spec?) → coder revises. This is how OpenHands achieves 77% SWE-Bench: the CodeAct loop is essentially generator+critic at the tool-call level.

2. **Commit message / PR description**: Generator writes a commit message → critic checks against Conventional Commits spec and BLUF principle → generator revises until clean. Cheap, fast, high-value.

The key insight from Anthropic: "LLMs can provide useful feedback themselves" — you don't need a separate model. A single Haiku can play both roles at minimal cost for low-stakes outputs; use Sonnet as critic only for high-stakes diffs.

---

### d. Failure Modes

- **Agreement bias / sycophancy**: When generator and critic are the same model (or the same provider fine-tune), the critic grades its own outputs leniently. Confirmed in the Self-Refine paper — same-model critique is weaker than cross-model critique.
- **Oscillation**: Generator incorporates critic feedback → critic now objects to the revision → generator reverts → infinite loop. Mitigation: add a monotonically-improving score requirement; if iteration N+1 is not better than N on a measurable metric (test pass rate, lint score), stop.
- **Runaway iterations**: Without a hard cap, 20 revision cycles × 10K tokens each = 200K tokens per task on a simple change. Anthropic specifies "maximum number of iterations" as a required stopping condition.
- **Critic latency adds up**: Each generator-critic exchange is 2 sequential LLM calls. A 5-cycle refinement = 10 LLM calls before any commit is produced. At Sonnet pricing this is ~$0.15/refinement cycle.
- **False PASS**: The critic returns PASS on a diff that still has a bug. This is the most dangerous failure because the outer workflow proceeds with confidence. Mitigation: use the test suite as a ground-truth oracle rather than relying solely on LLM critique.

---

### e. Fit for Ultra-Workshop

**Use this inside the Execute step for per-file code generation, and independently for commit message quality.** The test suite should be the final authority (ground truth) — the critic's role is pre-screening before running expensive CI.

---

### f. Composition Opportunities

- Sits inside each Execute step of Pattern 1 (Workflow).
- Can be the execution primitive for each task in the Pattern 2 (planner loop).
- Can be triggered by Pattern 3 (broadcast review board) when any reviewer returns NEEDS_CHANGE — route that reviewer's specific feedback back to the generator as the critic input.
- Pattern 5 (router) can select which critic profile to invoke based on file type (Python file → lint+test critic; Terraform file → security+cost critic).

---

### g. Cost & Latency Profile

| Dimension | Estimate |
|---|---|
| LLM calls per task | 2N where N = refinement cycles (typically 1–3 cycles) → 2–6 calls |
| Latency | Medium (sequential pairs; no parallelism possible) |
| Budget fit | Good at N=1–2. Using Haiku as critic and Sonnet as generator: Haiku critique ≈ $0.01, Sonnet generation ≈ $0.05 per cycle. 2 cycles ≈ $0.12/file. At 20 files/task and 15 tasks/day = $36/day at 2 cycles — exceeds budget. Optimization: use Haiku for both roles on simple files; escalate to Sonnet critique only on files flagged by linter. |

---

---

## Pattern 5 — Router

### a. Canonical Definition

Agent A (classifier/router) receives the incoming request or artifact, classifies it along one or more dimensions (task type, complexity, risk level, domain), and dispatches it to Agent B₁, B₂, or B₃ (specialized handlers) without passing through a central coordinator. The router itself is stateless; the handler owns execution from that point. Anthropic's term: **Routing** workflow. Agno's API: `TeamMode.route`.

---

### b. Reference Implementations and Frameworks

| Framework | Support level | API surface |
|---|---|---|
| **Agno** | First-class | `Team(mode=TeamMode.route)` — leader analyzes incoming request and routes to most appropriate member based on role. Example: [AI Support Team](https://docs.agno.com/examples/teams/route/ai_support_team). |
| **Anthropic** | First-class pattern | "Routing classifies an input and directs it to a specialized followup task." ([anthropic.com/engineering/building-effective-agents](https://www.anthropic.com/engineering/building-effective-agents)) Concrete example: simple questions → Haiku, complex → Sonnet. |
| **OpenAI Agents SDK** | First-class | Decentralized handoff pattern: each agent decides to handle or hand off. `Handoff` tool triggers transfer. More dynamic than static routing — the handler can re-route. |
| **LangGraph** | First-class | Conditional edges implement routing: `add_conditional_edges(router_node, classify_fn, {type_A: agent_A, type_B: agent_B})`. |
| **CrewAI** | Partial | `Process.hierarchical` manager agent implicitly routes tasks to workers; no explicit router node. |
| **AutoGen** | Supported | `SelectorGroupChat` uses an LLM to select the next speaker — effectively an LLM-based router each turn. |
| **Hermes Agent** | Partial | Gateway does platform-level routing (Telegram → session → agent). Task-level routing (skill selection) is part of the planned Phase 3 `LLM-based coordinator`. Currently, the agent picks tools/skills itself via its orchestration engine — not a separate router agent. |

**Research basis**: arXiv:2602.03478 ("When Routing Collapses") identifies the main production failure mode. arXiv:2603.01548 shows graph-based self-healing routing reduces LLM control-plane calls by 93%.

---

### c. Where It Shines (coding-agent context)

Three concrete uses in ultra-workshop:

1. **Issue triage router**: Incoming GitHub issue → router classifies as [bug-fix | feature | refactor | docs | dependency-update] → dispatches to the appropriate specialized Hermes skill or OpenHands configuration. Each handler is pre-configured with the right tools and context for its class.

2. **Model-tier router**: Before any LLM call, the router classifies query complexity (simple file rename vs. complex algorithm change) and routes to Haiku (cheap) or Sonnet (capable). Anthropic explicitly recommends this: "sending easy tasks to Haiku and harder tasks to Sonnet." Potential 40–60% cost reduction.

3. **Diff-type router at Review**: After coder produces a diff, router inspects it (pure test changes? infra changes? new auth code?) and selects which subset of Pattern 3 reviewers to invoke — avoiding paying for a security review on a documentation-only commit.

---

### d. Failure Modes

- **Routing collapse** (arXiv:2602.03478): As cost budgets increase, routers default to the most expensive model even when cheaper ones suffice — "under-utilize small models, wasting computation." Root cause: scalar performance scores used for training cause small prediction errors to flip model rankings, triggering suboptimal selection. EquiRouter mitigates with decision-aware ranking.
- **Ambiguous prompt misrouting**: A prompt like "fix it" is unclassifiable. Routing it anywhere is a coin flip. Production recommendation: if the classifier's confidence is below a threshold, return for clarification rather than guess — avoids wasting tokens on a misrouted task.
- **Single point of failure**: Misclassification cascades to the wrong handler, which may silently produce wrong output that only fails at CI time. The router has no feedback loop — it doesn't know if the handler succeeded.
- **Static router staleness**: Rule-based routers (keyword matching, prompt length) are fast but inaccurate. A short prompt can be hard ("implement the visitor pattern") and a long one can be trivial (boilerplate with "add error handling"). LLM-based routers are more accurate but add 1 LLM call of latency.
- **MAST data**: 79% of multi-agent production failures trace back to specification ambiguity and unstructured coordination — the router's job description must be extremely precise or it routes with the wrong assumptions.

---

### e. Fit for Ultra-Workshop

**Use this at two points**: (1) Issue triage to select the handler skill, (2) diff-type classification to select the reviewer subset. Keep the router itself lightweight (Haiku or a rule-based classifier for common cases) to minimize latency and cost.

---

### f. Composition Opportunities

- Sits at the entrance of Pattern 1 (Workflow) — the first node of the workflow is always a routing step.
- Pattern 5 can route into Pattern 2 (planner loop) for complex issues or directly to a simple Pattern 4 (generator+critic) for trivial ones.
- Pattern 3 (broadcast review board) uses a router to select which reviewers to invoke.
- Nested routing: outer router classifies domain (code vs. infra vs. docs); inner router selects complexity tier and model.

---

### g. Cost & Latency Profile

| Dimension | Estimate |
|---|---|
| LLM calls per task | 1 (if LLM-based) or 0 (if rule-based heuristics) |
| Latency | Low (Haiku at ~500ms; rule-based at <10ms) |
| Budget fit | Excellent. Even at 200 routing calls/day, Haiku-based routing ≈ 200 × 1K tokens × $0.25/1M ≈ $0.05/day — negligible. The savings from routing simple tasks to Haiku instead of Sonnet far exceed the router's cost. |

---

---

## Cross-Pattern Observations

**Most synergistic pairs:**

- **Pattern 1 + Pattern 2**: Workflow outer shell wrapping planner loop inner engine. This is the standard architecture for production coding agents (OpenHands V1, Claude Code). They reinforce each other: the workflow provides structure and stopping conditions; the planner loop provides adaptability within each step.
- **Pattern 4 + Pattern 3**: Generator+critic loop with a broadcast review board as the final critic. The inner loop handles per-file refinement; the board provides cross-cutting quality checks before PR open. Their failure modes are complementary — agreement bias inside the loop is caught by independent reviewers on the board.
- **Pattern 5 + everything**: The router is composable with all other patterns and adds cost efficiency without changing their semantics.

**Patterns that conflict:**

- **Pattern 2 (planner loop) vs. Pattern 3 (broadcast review board)** at the same level: a planner loop already performs dynamic replanning; adding a broadcast review board at the same decision point creates redundant, expensive evaluation. Use the board *after* the planner loop completes a unit of work — not inside it.
- **Pattern 4 (generator+critic) as outer wrapper**: Self-refine applied at the workflow level (critiquing the entire plan before execution) adds 2–4 LLM calls before any work begins. For ultra-workshop's budget, this is wasteful unless the plan is unusually high-stakes.

**Strongest fit for a coding-agent workshop:**

Pattern 1 (Workflow) is the mandatory skeleton. Pattern 2 (planner loop) is the mandatory inner engine for the Plan step. Pattern 5 (router) is the mandatory entry point and model-tier selector. Patterns 3 and 4 are selectable quality gates — Pattern 4 at execution time, Pattern 3 at PR review time. The recommended default configuration for ultra-workshop:

```
Router (Pattern 5)
  → Workflow (Pattern 1)
      → Plan step: Planner Loop (Pattern 2)
      → Execute step: per-file Generator+Critic (Pattern 4), max 2 cycles
      → Review step: Broadcast Review Board (Pattern 3), N=3 reviewers
      → Publish step: create PR / deploy
```

This composition covers all five patterns in their natural positions, minimizes redundancy, and fits within the $20/day budget at ~20 tasks/day throughput.

---

## Sources

- [Anthropic — Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Simon Willison — Building Effective Agents summary](https://simonwillison.net/2024/Dec/20/building-effective-agents/)
- [OpenAI — A Practical Guide to Building Agents (PDF)](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf)
- [OpenAI Agents SDK documentation](https://openai.github.io/openai-agents-python/agents/)
- [LangChain — Planning Agents blog](https://www.langchain.com/blog/planning-agents)
- [LangGraph Plan-and-Execute tutorial (JS)](https://langchain-ai.github.io/langgraphjs/tutorials/plan-and-execute/plan-and-execute/)
- [LangGraph supervisor reference](https://reference.langchain.com/python/langgraph-supervisor)
- [LangChain workflows and agents docs](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [Agno Teams Overview](https://docs.agno.com/teams/overview)
- [Agno — Four Execution Modes changelog](https://www.agno.com/changelog/orchestrate-multi-agent-teams-with-four-built-in-execution-modes)
- [Agno — AI Support Team route example](https://docs.agno.com/examples/teams/route/ai_support_team)
- [NousResearch Hermes Agent — Architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture)
- [NousResearch Hermes Agent — Multi-Agent Issue #344](https://github.com/NousResearch/hermes-agent/issues/344)
- [NousResearch Hermes Agent — GitHub](https://github.com/nousresearch/hermes-agent)
- [CrewAI — Hierarchical Process docs](https://docs.crewai.com/how-to/hierarchical-process)
- [AutoGen 0.4 — DeepWiki overview](https://deepwiki.com/agno-agi/agno)
- [Self-Refine paper — arXiv:2303.17651](https://arxiv.org/abs/2303.17651)
- [N-Critics paper — arXiv:2310.18679](https://arxiv.org/abs/2310.18679)
- [IF-CRITIC paper — arXiv:2511.01014](https://arxiv.org/pdf/2511.01014)
- [Talk Isn't Always Cheap — arXiv:2509.05396](https://arxiv.org/pdf/2509.05396)
- [Representational Collapse in LLM Committees — arXiv:2604.03809](https://arxiv.org/pdf/2604.03809)
- [Why Do Multi-Agent LLM Systems Fail? (MAST) — arXiv:2503.13657](https://arxiv.org/html/2503.13657v1)
- [When Routing Collapses — arXiv:2602.03478](https://arxiv.org/abs/2602.03478)
- [beam.ai — 6 Multi-Agent Orchestration Patterns for Production](https://beam.ai/agentic-insights/multi-agent-orchestration-patterns-production)
- [Augment Code — Why Multi-Agent LLM Systems Fail](https://www.augmentcode.com/guides/why-multi-agent-llm-systems-fail-and-how-to-fix-them)
- [OpenHands SDK paper — arXiv:2511.03690](https://arxiv.org/html/2511.03690v2)
- [OpenHands Index blog](https://www.openhands.dev/blog/openhands-index)
- [MarkTechPost — OpenClaw vs Hermes Agent](https://www.marktechpost.com/2026/05/10/openclaw-vs-hermes-agent-why-nous-researchs-self-improving-agent-now-leads-openrouters-global-rankings/)
