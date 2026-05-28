# Ultra-Workshop: Multi-Agent Architecture Pattern Research
## Patterns 6–10 Deep Analysis

**Context**: Companion project to Brain (Agno, HTTP at 127.0.0.1:7000). Orchestrator: NousResearch Hermes Agent. Budget: $20/day, single-VPS, solo dev.

---

## Pattern 6: Graph / State Machine

### a. Canonical Definition
A directed graph (DAG or cyclic) where nodes are agent actions and edges are transitions between them; conditional edges branch based on runtime state, enabling loops, retries, and explicit decision trees.

### b. Reference Implementations and Frameworks
**LangGraph** is the canonical implementation — built specifically for this pattern atop LangChain. Key APIs:
- `StateGraph(TypedDict)` — declares the shared state schema
- `.add_node(name, fn)` — adds a processing node
- `.add_edge(a, b)` — definite transition
- `.add_conditional_edges(node, router_fn, {value: target})` — dynamic branching
- `.compile()` — produces the runnable graph
- `MemorySaver` / `SqliteSaver` — built-in checkpointing with time-travel replay

LangGraph ships `langgraph-supervisor` and `langgraph-swarm` prebuilt patterns (separate PyPI packages) that layer supervisor and swarm topologies on top of the same primitive.

**LangChain Open SWE** (2025) uses LangGraph for a full coding agent: Manager graph → Planner subgraph → Programmer subgraph with embedded Reviewer loop, terminating at a GitHub PR open step. This is the closest published reference to ultra-workshop's target.

**Microsoft AutoGen / Magentic-One** also uses a graph-like outer-loop / inner-loop structure (Task Ledger + Progress Ledger), but the graph is implicit in the Orchestrator's planning loop rather than a declared DAG.

**Partial support**: CrewAI's "hierarchical" process approximates a 2-level DAG but can't express arbitrary conditional edges. AutoGen's `GroupChatManager` lacks explicit edge declarations.

### c. Where it Shines (Coding-Agent Context)
- **Predictable pipelines**: issue-intake → plan → code → test → lint → PR open maps cleanly to nodes with definite edges.
- **Retry loops**: `test_failed → rewrite_code → test` is a conditional edge trivially expressed.
- **Human-in-the-loop**: LangGraph's `interrupt_before`/`interrupt_after` hooks pause at any node for human approval — exactly what PR review gates need.
- **Parallel fan-out**: independent test suites or linting passes can fork into parallel nodes and join at a consensus node.
- Open SWE achieves full issue-to-PR autonomy at LangGraph Platform with built-in durable execution (agents survive hour-long runs and infra restarts).

### d. Failure Modes
- **State corruption under concurrency**: simultaneous node writes to shared state can race; LangGraph's per-node update semantics and thread-level checkpointing mitigate but don't eliminate this.
- **Routing quality degradation**: LangGraph's docs note routing accuracy drops noticeably after 8–12 sub-agent round trips as the supervisor's context fills.
- **Trajectory structure vs. length**: SWE-bench analysis (arXiv:2604.02547, 2026) shows agents failing not from running too long but from wrong structural choices early — a misrouted conditional edge early in the graph propagates error through all downstream nodes.
- **Error attribution is hard**: arXiv:2510.10581 (GraphTracer) shows that in DAG-based systems, symptoms appear at leaf nodes but root causes live in upstream nodes — temporal sequence analysis is insufficient; Information Dependency Graphs are needed.
- **Dead-end graph states**: missing a conditional branch for an edge case leaves the graph in a node with no outgoing edge, silently stalling.
- **Cost from state checkpointing**: persistent checkpointing to SQLite or Redis adds I/O overhead on every node transition.

### e. Fit for Ultra-Workshop
**Strong fit** — use as the primary orchestration spine:
- The issue→plan→code→test→lint→PR pipeline is a natural DAG.
- `interrupt_before=["pr_open"]` gives free human-approval gate on every PR.
- LangGraph's subgraph composability means Brain (HTTP) can be invoked as a single tool-node in the graph without coupling.
- For a $20/day budget, the graph structure enables early exit on test failure (skip PR steps), saving tokens on bad paths.

### f. Composition Opportunities
- **Wraps Blackboard**: the shared `StateGraph` state object *is* a blackboard; each node reads/writes the same dict.
- **Wraps MoA**: a `code_generation` node can internally spawn 3 parallel LLM calls and aggregate — MoA as a sub-pattern inside one graph node.
- **Wrapped by Swarm**: LangGraph Swarm is literally a graph where handoff logic is encoded as conditional edges — Swarm pattern is a specialization.

### g. Cost & Latency Profile
- **LLM calls per task**: N nodes on the critical path = N sequential LLM calls minimum. Parallel branches share wall-clock but not token budget.
- **Checkpointing overhead**: ~1 SQLite write per node (negligible).
- **Relative to single-agent**: 2–4× LLM calls for a 4-node pipeline vs. a single-prompt approach, but with dramatically better correctness and recoverability.
- **LangSmith data**: supervisor routing adds ~30% wall-clock overhead vs. direct swarm routing; swarm cuts this but degrades routing accuracy.

---

## Pattern 7: Blackboard

### a. Canonical Definition
A shared, persistent data structure (the "blackboard") that all specialized agents read from and write to; a control unit determines which agent acts next based on the current blackboard state. Agents are decoupled from each other — they only interact through the shared store.

### b. Reference Implementations and Frameworks
No major framework ships blackboard as a first-class primitive in 2025. It must be assembled:
- **LangGraph** can simulate it: declare a `TypedDict` state with all shared fields; each node reads and writes to it. The control shell becomes the routing logic in conditional edges. Missing: no built-in conflict resolution or locking.
- **AutoGen** agents sharing a `GroupChat` message history is a weak form of blackboard (all agents see all messages), but it's append-only and has no structured schema.
- **LbMAS** (arXiv:2510.01285, 2025) and the framework in arXiv:2507.01701 (Han et al., July 2025) are purpose-built research implementations demonstrating 13–57% relative improvements over master-slave baselines on coding and information-retrieval tasks.
- **`agent-blackboard`** (GitHub: claudioed/agent-blackboard) shows a practical 9-agent software engineering system: Documentation, API Design, Backend Architecture, Java/Go Development, DDD, Observability agents all writing to a shared repo.
- **Ray** for distributed execution if multiple VPS processes need shared state.

Google Research (2024) proposed applying this to LLM-based data science, noting it outperforms both single-agent and master-slave multi-agent setups.

### c. Where it Shines (Coding-Agent Context)
- **Iterative refinement**: a Planner writes a spec, a Coder writes code, a Tester writes test results, a Reviewer writes feedback — all visible to all agents on the next round without point-to-point message passing.
- **No pre-defined workflow**: control shell can dynamically pick the most relevant agent for the current blackboard state, avoiding rigid SOPs.
- **Transparency**: the blackboard is a full audit log — every agent's contribution is timestamped and attributable.
- **Self-debug loops**: execution feedback (test output, lint errors) lands on the blackboard; any subscribed agent can react without explicit routing.
- **Token efficiency**: LbMAS reports that the public blackboard reduces per-agent prompt lengths by eliminating redundant context preambles.

### d. Failure Modes
- **Blackboard contention**: two agents writing conflicting values to the same field (e.g., both update `current_plan`) requires optimistic locking or versioning — most implementations don't have this.
- **Control-shell complexity**: choosing which agent to activate next is itself a hard problem; a naive round-robin control shell wastes calls on irrelevant agents.
- **Stale reads**: an agent may act on outdated blackboard state if another agent modified it concurrently — particularly dangerous in async execution.
- **No native support**: every framework requires custom implementation, adding engineering overhead for a solo dev.
- **Security**: sensitive data (API keys, credentials in code) sitting in the shared store is a leakage risk.

### e. Fit for Ultra-Workshop
**Partial fit** — use as the state layer *within* a LangGraph graph rather than as a standalone architecture:
- LangGraph's `StateGraph` state IS the blackboard for ultra-workshop's purposes — no extra infrastructure needed.
- A standalone blackboard architecture (with dynamic control shell) is over-engineered for a predictable coding pipeline where the workflow stages are known in advance.
- **Don't use** as the primary orchestration mechanism for ultra-workshop; the pipeline is too structured. Use for the shared context that all agents in a graph or group chat can read.

### f. Composition Opportunities
- **Inside Graph/State Machine**: the graph's state dict is the blackboard — this composition is already implicit in LangGraph.
- **Inside Group Chat**: AutoGen's shared message history functions as a weak blackboard; a structured blackboard object can be injected as the first message.
- **With MoA**: proposer outputs all land on the blackboard; the aggregator reads all at once rather than being passed them serially.

### g. Cost & Latency Profile
- **LLM calls per task**: similar to graph — one per agent activation, but the control shell may trigger unnecessary agent calls (agents polled and finding nothing relevant).
- **Token overhead**: if the full blackboard is injected into every agent's context, token cost grows linearly with blackboard size — LbMAS mitigates with selective field injection.
- **Relative to single-agent**: LbMAS reports competitive performance at *fewer* tokens than baseline multi-agent systems due to reduced context duplication.

---

## Pattern 8: Mixture-of-Agents (MoA)

### a. Canonical Definition
N proposer agents generate independent responses in parallel; one or more aggregator agents synthesize these proposals into a final, higher-quality output. The key insight is "collaborativeness": LLMs produce better outputs when given peer responses as additional context, even from weaker models. (Wang et al., arXiv:2406.04692, accepted ICLR 2025.)

### b. Reference Implementations and Frameworks
- **Together AI's MoA** (`github.com/togethercomputer/MoA`): reference implementation with 3 MoA layers, Qwen1.5-110B-Chat as final aggregator. Runs proposers fully in parallel per layer.
- **LangGraph parallel fan-out**: `Send()` API dispatches identical tasks to N nodes simultaneously; a `join` node aggregates. Native MoA in ~20 lines.
- **AutoGen**: multiple `ConversableAgent` instances can be called in sequence with each seeing prior outputs — approximates MoA but not true parallel.
- **CrewAI**: "voting" process type runs identical tasks across agents, but sequential not parallel.
- **OpenAI Agents SDK**: no native MoA; handoffs are sequential by design.

**2025 critique — arXiv:2502.00674 ("Rethinking MoA")**: Self-MoA (sampling same top model N times) outperforms standard cross-model MoA by 6.6pp on AlpacaEval 2.0 and 3.8% on average across MMLU/CRUX/MATH. Quality beats diversity — including weak models hurts. The paper recommends **Self-MoA-Seq** for budget-constrained deployments.

**Security vulnerability**: a single deceptive agent in a 6-agent MoA dropped win rate from 49.2% to 37.9% (arXiv, 2025). Mitigation: Dropout Vote / Dropout Cluster filtering.

### c. Where it Shines (Coding-Agent Context)
- **Ambiguous requirements**: N proposers each interpret the spec differently; aggregator synthesizes the best elements. Reduces the "first interpretation bias" of a single agent.
- **Code review**: 3 parallel reviewers each flag different issues; aggregator produces a unified review without social pressure biases.
- **Test generation**: N agents generate independent test suites; aggregator takes the union, maximizing coverage.
- **Voting on pass/fail decisions**: run N linters/test runners in parallel; majority vote decides whether to proceed to PR. Higher confidence than a single run.

### d. Failure Modes
- **Cost multiplication**: N proposers × M layers = N×M LLM calls before a single output. A 3-layer, 3-proposer MoA runs 9 + 1 = 10 calls per task vs. 1.
- **Latency ceiling**: TTFT (time to first token) is blocked until the last MoA layer completes — unsuitable for interactive workflows.
- **Quality regression from mixing weak models**: the "Rethinking MoA" finding is decisive — mixing different-capability models often *hurts* compared to using the best model alone.
- **Agreement bias in aggregation**: if proposers produce similar outputs, the aggregator adds no value and costs 3–10× more.
- **Adversarial sensitivity**: one bad actor in the proposer pool dramatically degrades output (documented 25% drop in win rate).
- **Context length**: in coding tasks, each proposer may generate 500–2000 tokens of code; the aggregator must process all N outputs simultaneously, burning the context window.

### e. Fit for Ultra-Workshop
**Narrow fit** — use only for specific high-stakes decisions, not as the primary architecture:
- **Good for**: code review aggregation (3 reviewers → 1 consolidated review), test coverage voting, evaluating whether a PR is safe to merge.
- **Bad for**: the main coding loop (cost is prohibitive at $20/day; 10× per-task cost easily exceeds budget).
- **Per "Rethinking MoA"**: if using MoA at all, use Self-MoA (same strong model, 2–3 samples) rather than mixing Hermes + GPT-4o + Claude. Self-MoA gets better quality at lower API cost.
- **Budget math**: at $0.03/1K tokens (Sonnet-class), a 3-proposer MoA generating 1K tokens each + 3K aggregation = ~$0.12/task. At 50 tasks/day, that's $6/day just for one MoA step — possible but leaves little for the rest of the pipeline.

### f. Composition Opportunities
- **Inside a Graph node**: MoA as a sub-pattern in `code_review_node` within the LangGraph DAG — expensive but contained.
- **As an evaluator**: the "evaluator-optimizer" pattern from Anthropic's "Building Effective Agents" maps to MoA where multiple evaluator calls check a single output.
- **Wraps Blackboard**: proposers write independent analyses to the blackboard; aggregator reads all.

### g. Cost & Latency Profile
- **LLM calls per task**: N × layers + 1 aggregator. Default MoA (3 proposers, 1 aggregator): 4 calls minimum, 10 for 3-layer.
- **Wall-clock**: proposers run parallel, so latency ≈ slowest proposer + aggregator. Not 10× sequential latency, but still slow.
- **Relative to single-agent**: 4–10× token cost for comparable or (per 2025 research) often *worse* quality unless carefully configured as Self-MoA.

---

## Pattern 9: Group Chat / Debate

### a. Canonical Definition
Multiple agents share a single conversation thread ("room"); each agent can read all prior messages and append its own; a manager (LLM-based or round-robin) decides speaking order. Coordination emerges from the dialogue itself rather than pre-defined routes.

### b. Reference Implementations and Frameworks
- **AutoGen / AG2 `GroupChat` + `GroupChatManager`**: the most mature implementation. Four built-in speaker selection policies: round_robin, random, auto (LLM-selected), custom callable. `GroupChatManager` broadcasts each message to all agents. API: `GroupChat(agents=[...], messages=[], max_round=N)`.
- **LangGraph**: no native GroupChat, but the LangGraph blog shows a "multi-agent network" pattern where all agents share a message list in state — functional equivalent.
- **MetaGPT**: uses a "shared message pool" which is a structured group-chat variant where messages have role+content+cause_by metadata.
- **CrewAI**: "consensual" process type approximates group chat but is less flexible.
- **OpenAI Agents SDK**: no group chat; handoffs are bilateral, not multicast.
- **Magentic-One**: uses a structured group-chat-like inner loop (Orchestrator broadcasts task + receives responses), but the Orchestrator controls turn order explicitly.

**2025 multi-agent debate (MAD) research**: arXiv:2509.05396, arXiv:2604.02668, arXiv:2509.23055 document the sycophancy and conformity failure modes extensively.

### c. Where it Shines (Coding-Agent Context)
- **Adversarial code review**: a Defender agent argues the code is correct while a Critic agent argues it's wrong — forces articulation of assumptions.
- **Architecture decisions**: three agents propose different data structures; the group converges on the strongest.
- **Multi-perspective debugging**: one agent focuses on logic errors, one on type errors, one on edge cases — each reads the others' findings and builds.
- **Open-ended tasks**: when the coding subtask is unclear, a brief group chat to clarify scope before dispatching to a graph pipeline can prevent wasted work.

### d. Failure Modes
- **Sycophantic convergence** (most documented failure): agents agree not because the argument is correct but due to social pressure. arXiv:2604.02668 ("Too Polite to Disagree", 2026) shows sycophancy propagates through multi-agent systems — one agent caving causes cascading agreement.
- **Correct-answer abandonment**: agents flip from correct to incorrect under peer pressure even with "prioritize correctness" prompts — counter-intuitive and not fixable by simple instruction (arXiv:2509.05396).
- **Identity bias / self-bias**: agents disproportionately favor their own prior outputs and disproportionately agree with outputs attributed to prestigious sources (arXiv:2510.07517). Anonymizing agent labels helps.
- **Infinite chat loops**: AutoGen GitHub issue #5831 documents confirmed infinite loops when the `GroupChatManager` can't identify a handoff target.
- **Context window explosion**: in AutoGen, the full conversation history is injected into every agent's next call. For a 10-round debate with 4 agents generating 500 tokens each, the 10th round processes 20K+ tokens.
- **No termination guarantee**: group chat has no structural termination condition — `max_round` is a blunt instrument.
- **Cost unpredictability**: rounds × agents × tokens/message = quadratic cost growth.

### e. Fit for Ultra-Workshop
**Limited, targeted fit** — use for adversarial code review only, not as the primary orchestration mechanism:
- A 2-agent debate (Defender vs. Critic) with `max_round=3` for PR review is legitimate and bounded.
- Anonymize agent identities to reduce sycophancy (arXiv:2510.07517 finding).
- **Do not use** for main coding loop — cost and convergence failure make it unreliable for production pipelines.
- Hermes Agent's `delegate_tool` supports spawning subagents but doesn't natively manage group-chat semantics — would require AutoGen or custom implementation.
- Budget constraint: 4 agents × 3 rounds × 1K tokens = 12K tokens/review ≈ $0.04 at Haiku-class pricing. Viable if capped.

### f. Composition Opportunities
- **Inside a Graph node**: `review_node` launches a 2-agent group debate; the graph resumes after `max_round`.
- **Feeds Blackboard**: debate transcript lands on the blackboard as structured critique for downstream agents.
- **Wraps nothing**: group chat is a terminal pattern — it's hard to nest cleanly without becoming a recursive debate soup.

### g. Cost & Latency Profile
- **LLM calls per task**: R rounds × A agents = R×A calls. 3 rounds, 3 agents = 9 calls for one debate.
- **Token multiplier**: each call processes the full conversation history, so token cost is quadratic in rounds.
- **Relative to single-agent**: 9–20× cost for typical debate configurations; latency is fully sequential.
- **2026 note**: the MAD research community has cooled on group debate as a general-purpose improvement — it's now understood to help only for specific reasoning tasks where diversity of approach is genuinely needed and sycophancy is controlled.

---

## Pattern 10: Swarm

### a. Canonical Definition
A collection of lightweight, specialized agents where control transfers via explicit "handoff" functions that an LLM calls based on the current conversation context; no central orchestrator owns the routing — each agent decides autonomously to pass to a peer. Coordination is emergent from the handoff graph topology.

### b. Reference Implementations and Frameworks
- **OpenAI Swarm** (Oct 2024, educational): `Agent(name, instructions, functions=[transfer_to_XXX])`. A handoff is a Python function returning an `Agent` — the LLM calls it when appropriate. ~1000 lines of Python, explicitly not production.
- **OpenAI Agents SDK** (Mar 2025, production): direct successor. `handoff(agent)` helper; SDK converts to a tool. Adds guardrails, tracing, TypeScript support. Full `swarm` semantics preserved.
- **LangGraph Swarm** (`langgraph-swarm` PyPI package, 2025): wraps LangGraph graph with conditional edges that implement handoff semantics. Achieves ~40% latency reduction vs. supervisor pattern (per LangSmith instrumentation) by eliminating the central supervisor's round-trip LLM calls.
- **AutoGen Swarm** (AutoGen 0.4+): `SwarmAgent` class with `ON_CONDITION` handoff triggers. Confirmed infinite loop bug (GitHub #5831) when handoff target is undefined.
- **CrewAI**: no native swarm; closest is hierarchical process.
- **Hermes Agent**: supports subagent delegation via `delegate_tool` — approximates swarm handoff but is not a named pattern in the framework.

**Distinction from supervisor**: In a supervisor pattern, every message routes through a central agent (2 LLM calls/domain). In swarm, agents route directly to peers (1 LLM call/domain). LangSmith data: swarm saves ~30% of total response time and reduces per-query LLM calls.

### c. Where it Shines (Coding-Agent Context)
- **Well-separated specializations with clear handoff signals**: `triage_agent` → `planner_agent` → `coder_agent` → `test_agent` when each agent has a crisp "done" condition and knows exactly who to hand to next.
- **Low interdependency tasks**: each agent's context is self-contained; handoff carries the minimal state needed for the next agent.
- **Cost efficiency**: fewer LLM calls than supervisor for the same pipeline depth.
- **Ultra-workshop's Hermes base**: Hermes already uses tool-based subagent delegation — the swarm handoff pattern extends this naturally without a new framework dependency.

### d. Failure Modes
- **Thrashing / circular handoffs**: Agent A hands to B, B hands back to A, infinite loop. Documented in AutoGen #5831 and multiple 2025 post-mortems. Requires hard iteration caps external to the LLM.
- **Context loss on handoff**: each handoff must carry all needed context explicitly — no implicit shared state. Bugs from missing context are silent (agent proceeds on incomplete information).
- **Routing quality degradation with scale**: swarm works well for ≤5 agents; with 8+ agents, the LLM routing logic becomes unreliable (same degradation as supervisor but with no central fallback).
- **Hallucinated handoffs**: the LLM invents a `transfer_to_nonexistent_agent` — Swarm/Agents SDK handles this by raising an error, but downstream is stalled.
- **Budget spiral**: without an external hard ceiling, a misbehaving swarm calls agents repeatedly. The 2026 multi-agent failure playbook (cogentinfo.com) mandates `BudgetExhaustionException` as an infrastructure kill switch.
- **Debuggability**: without a central supervisor's trace, reconstructing the handoff chain requires explicit tracing (LangSmith or OpenAI dashboard).

### e. Fit for Ultra-Workshop
**Good fit as the inter-agent routing mechanism** — use for the top-level issue-to-PR pipeline:
- `issue_triage` → `planner` → `coder` → `tester` → `reviewer` → `pr_opener` as a 5-agent swarm.
- Each agent is self-contained; handoff context is the minimal `{issue_id, plan, code, test_results}` dict.
- LangGraph Swarm (via `langgraph-swarm`) integrates cleanly with the Graph/State Machine pattern — the swarm *is* a specialized graph.
- **Hard limit**: implement a `max_handoffs=10` external counter and a `$daily_budget` circuit breaker — do not rely on LLM self-regulation.
- Budget math: 5 handoffs × 1 LLM call each × ~2K tokens = 10K tokens per task ≈ $0.03 at Haiku-class. At 50 tasks/day: $1.50. Very budget-friendly.
- Hermes's `delegate_tool` already implements a handoff primitive — the swarm pattern maps directly onto the existing Hermes architecture without a framework switch.

### f. Composition Opportunities
- **Specialization of Graph/State Machine**: LangGraph Swarm is literally a graph with swarm-style conditional edges. Use Graph as the structural substrate, Swarm as the routing philosophy.
- **Wraps MoA**: individual swarm agents can internally invoke MoA for high-stakes decisions before handing off.
- **Uses Blackboard**: the handoff payload IS the blackboard slice — send only relevant state, not the full blackboard.
- **Does NOT compose well with Group Chat**: having agents simultaneously participate in a group debate AND in a swarm routing mesh creates two competing coordination mechanisms.

### g. Cost & Latency Profile
- **LLM calls per task**: 1 per agent × number of hops = N calls (same as graph, no supervisor overhead).
- **Latency**: fully sequential through the handoff chain; no parallelism unless an individual agent fans out internally.
- **Relative to single-agent**: N× calls for N-agent pipeline, but each call is scoped and shorter (no full conversation history). In practice 1.5–2× cost of a single well-prompted agent for the same task quality.
- **Supervisor comparison**: 1 fewer LLM call per hop vs. supervisor = 30–40% fewer API calls overall.

---

## Cross-Pattern Observations

**Most synergistic pairs:**
- **Graph/State Machine + Swarm** — highest synergy. LangGraph Swarm IS this composition. The graph provides structure (nodes, edges, checkpointing, HITL); Swarm provides lightweight inter-agent routing within or across nodes. Use together as ultra-workshop's foundation.
- **Graph/State Machine + Blackboard** — also natural: LangGraph's shared `StateGraph` state is the blackboard. Zero extra infrastructure.
- **MoA inside Graph nodes** — contained use: a single graph node can invoke 2–3 Self-MoA samples for a high-stakes decision without exposing the pattern to the whole pipeline.

**Conflicting / duplicating pairs:**
- **Group Chat vs. Swarm** — both handle inter-agent coordination but incompatibly. Group Chat is multicast and emergent; Swarm is bilateral and explicit. Mixing them creates two routing authorities fighting for control.
- **Standalone Blackboard vs. Graph/State Machine** — redundant for ultra-workshop. The graph's state already is the blackboard. A separate blackboard infrastructure is engineering overhead with no additional benefit.

**Strongest fit for ultra-workshop**: Graph/State Machine (LangGraph) with Swarm routing semantics (LangGraph Swarm) as the primary architecture. Add Blackboard implicitly via LangGraph state. Use MoA narrowly for code review aggregation. Avoid Group Chat as a primary mechanism.

**Worst fit**: Standalone Group Chat / Debate — documented sycophancy failures, quadratic token cost, no structural termination, and incompatibility with Hermes Agent's tool-based architecture make it the highest-risk, lowest-ROI pattern for a budget-constrained, production-targeted coding agent.
