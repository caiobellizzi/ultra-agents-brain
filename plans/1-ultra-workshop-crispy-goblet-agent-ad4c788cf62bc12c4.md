# Ultra-Workshop Architecture Research
## Deep Dive: 7 Real-World Autonomous Coding Agent Systems (2024–2026)

**Purpose:** Extract architectural lessons for `ultra-workshop` — a personal autonomous coding/PR/deploy agent team, Telegram-reachable, integrated with the Brain knowledge layer, running on a single Hostinger VPS at ~$20/day.

**Sources consulted (primary):** Cognition blog, OpenHands arXiv:2511.03690, Manus arXiv:2505.02024, Anthropic Agent SDK docs (code.claude.com), Claude Code architecture paper arXiv:2604.14228, SWE-agent/mini-swe-agent GitHub, MetaGPT arXiv:2308.00352, Magentic-One arXiv:2411.04468 + Microsoft Research blog.

---

## 1. Cognition AI Devin

### Architecture Summary
- **Single planner-executor loop** inside an isolated VM per session. Devin 1.x was one long-running agent; Devin 2.0 introduced parallelism by allowing multiple isolated VM instances to be spawned concurrently, each with its own agent session.
- **Agent-native IDE triad**: shell (terminal), code editor, sandboxed browser — all three live inside the VM. Devin generates shell commands, file edits, and browser navigations as typed actions; the VM executes them and returns observations.
- **Interactive Planning gate**: Devin 2.0 introduced a plan-before-execute contract where the plan is surfaced to the human for approval or editing before execution begins. This is the primary HITL checkpoint.
- **Devin Wiki**: the agent automatically indexes the repository every few hours, producing architecture diagrams and documentation. This is a background, persistent-memory loop separate from the main task agent.
- **Devin Search**: an agentic codebase query tool ("where is auth logic?") layered on top of the wiki index, with a "Deep Mode" for expensive multi-step exploration.

### Multi-Agent Pattern
**Planner-loop** (single). Devin 2.0 enables horizontal scaling by spawning multiple isolated planner-loop instances in parallel (swarm-lite), but each instance is independently a planner-loop, not a coordinated team.

### Sandbox / Execution Environment
Cloud-hosted isolated VM per session. Fresh VM on every task start. Includes browser (Chromium), terminal, and VSCode-like editor. Customer VPC deployment available for enterprise.

### State / Memory Model
- **Short-term**: VM filesystem + chat history within session
- **Long-term**: Wiki index (background scan every ~2h), Devin Search index
- No explicit cross-session conversation memory; the wiki + git history act as the durable knowledge layer

### HITL Approach
Interactive Planning (explicit plan approval before execution). Can also message human teammates via Slack or create PRs for review when blocked. No continuous approval requirement during execution.

### Lessons for ultra-workshop
1. **Decouple the background knowledge-building loop from the task-execution loop.** The Wiki indexer runs on its own cadence; the task agent consumes it on demand. ultra-workshop's Brain layer should behave the same way.
2. **The VM triad (shell + editor + browser) is the minimal viable environment.** For ultra-workshop, Docker containers give the same isolation cheaply on a VPS.
3. **Plan approval as the primary HITL gate** — surface the plan to Telegram before executing. One Telegram message per plan; the user approves or edits before the agent runs.

---

## 2. OpenHands V1 (SDK, November 2025)

### Architecture Summary
- **V0 → V1 transformation**: V0 used a pub/sub `EventStream` with an `AgentController` — this caused thread/async ordering bugs and tightly coupled components. V1 replaced it with **synchronous `Conversation` objects** (async via threads/asyncio for web servers).
- **Four-package modular SDK**: `sdk` (core agent/conversation/event model), `tools` (file ops, bash, browser), `workspace` (local/remote/Docker), `server` (REST+WebSocket for remote execution). Clean separation so you can use the core without the server.
- **Immutable agents, mutable conversations**: `Agent` is a Pydantic model (LLM config, tool list, security policy) — never changes. `ConversationState` is the only mutable entity, holding an append-only `EventLog`.
- **Event-sourcing at the core**: every interaction is an immutable `Event` appended to the log. Types: `LLMConvertibleEvent` (model sees it) vs `Internal` (state management only). Enables deterministic replay and fault recovery.
- **Sub-agent spawning via delegation tool**: sub-agents inherit parent model config and workspace context; run as independent conversations that can execute in parallel. Results returned as summaries, not full histories.

### Multi-Agent Pattern
**Planner-loop** (single conversation) with **graph/state-machine** underpinnings (event log as state machine). Sub-agents extend this to a lightweight **orchestrator-workers** pattern without a dedicated orchestrator agent.

### Sandbox / Execution Environment
Three tiers via `Workspace(...)` factory: `LocalWorkspace` (in-process, host filesystem), `RemoteWorkspace` (HTTP/WebSocket to remote agent server), `DockerWorkspace` (container with dedicated filesystem and resource limits). Same agent code runs in all three — configuration, not code.

### State / Memory Model
- `ConversationState` = metadata + append-only `EventLog`
- Events are serialized; full session replay is possible
- Context condensation (auto-summarization) when history approaches model context limit — documented 2× cost reduction with no performance loss
- No separate long-term memory store in V1; durable state lives in the event log on disk

### HITL Approach
Security interleaving: before any action executes, it passes through a configurable security policy (LLM-based risk analysis: low/medium/high). Actions above threshold require confirmation. Pause/resume built into the event model. No specific Telegram/UI integration out of the box.

### Lessons for ultra-workshop
1. **Adopt event-sourcing over mutable state** — append-only JSONL logs give you replay, audit, and crash recovery for free. ultra-workshop should write every agent action and observation to an event log.
2. **The `Workspace` abstraction is the right model**: define an interface (run_bash, read_file, write_file, browse_url) and swap `LocalWorkspace ↔ DockerWorkspace` without touching agent code. This is exactly the abstraction ultra-workshop needs per coding task.
3. **Synchronous by default, async only when needed** — V0's async EventStream caused subtle ordering bugs. Start ultra-workshop's task runner as synchronous per-task; only add async if Telegram concurrency demands it.

---

## 3. Manus AI

### Architecture Summary
- **Three-agent split within one session**: Planner Agent (decomposes user request into sub-tasks, formulates strategy), Execution Agent (invokes tools, interfaces with external systems), Verification Agent (validates outcomes before finalizing). All three run in a coordinated loop within a cloud-based Linux sandbox.
- **Skills system**: reusable file-system-based modules with a `SKILL.md` (instructions, ≤5k tokens) at three progressive disclosure levels: Level 1 metadata (~100 tokens, always loaded), Level 2 instructions (loaded when triggered via `/SKILL_NAME`), Level 3 resources (scripts/files, on demand). This keeps context window usage minimal.
- **MCP as the data layer**: Model Context Protocol provides standardized access to external data sources (Gmail, Notion, SimilarWeb, etc.). Skills provide the "operating manuals" for consuming those sources.
- **Persistent memory**: internal context of intermediate results maintained across steps within a session; adapts plan as new information emerges. Browser runs in the sandbox for real-time web access.
- **Open standard**: Manus uses the same `SKILL.md` format as a public standard, allowing other AI products to share and consume skills.

### Multi-Agent Pattern
**Generator-critic** (planner generates plan, verifier critiques result) embedded inside a **workflow-first** multi-agent design. The three roles have fixed contracts; they don't dynamically assign themselves tasks.

### Sandbox / Execution Environment
Cloud-based Linux sandbox with browser. Same triad as Devin (shell + browser + editor). Proprietary Butterfly Effect infrastructure — not open-sourced.

### State / Memory Model
- Intra-session: rolling context with intermediate results
- Skills = persistent reusable knowledge encoded in files (not model weights)
- No explicit cross-session episodic memory described publicly; skills serve as the durable knowledge layer

### HITL Approach
Not explicitly described in public architecture docs. Implied human-in-the-loop at task submission; verification agent provides automated QA before results are returned. User interaction model: Telegram/web UI triggers tasks.

### Lessons for ultra-workshop
1. **The Skills progressive disclosure model is exactly right for ultra-workshop.** Each skill (e.g., `pr-generator`, `deploy-vps`, `review-diff`) loads its SKILL.md only when needed, keeping the context window clean for actual work.
2. **Separate verification from execution as a first-class concern.** Don't trust the executor to self-assess. A lightweight verifier agent (or even a rules-based checker: did the tests pass? did the PR get created?) running after each task provides a safety net.
3. **MCP for data sources, Skills for workflows** — ultra-workshop should adopt this split: MCP for Brain queries / GitHub / Telegram APIs; Skills for the reusable coding workflows.

---

## 4. Anthropic Claude Agent SDK + Computer Use (2025–2026)

### Architecture Summary
- **Claude Agent SDK = Claude Code as a library**: the same agent loop, tools (Read, Edit, Write, Bash, Glob, Grep, WebSearch, WebFetch, Monitor, AskUserQuestion), context management, and compaction that power Claude Code, exposed as Python/TypeScript packages.
- **Reactive ReAct loop**: `while-true` → context assembly → model call → tool dispatch → permission evaluation → execution → result. Organized as an `AsyncGenerator` yielding streaming events. ~98.4% of the codebase is operational infrastructure; ~1.6% is AI decision logic.
- **Five-layer context compaction**: budget reduction → snip → microcompact → context collapse → auto-compact (model-generated semantic summarization). Effective working window ~60–80k tokens despite 200k nominal.
- **Seven permission modes**: from `plan` (approve all before execution) to `bypassPermissions` (minimal prompting). Users approve ~93% of prompts, so the system shifted to automated safety boundaries within which the agent works freely.
- **Subagents via `Agent` tool**: subagents get isolated contexts with their own permission boundaries; return only summaries to parent; conversations stored in separate "sidechain" JSONL files.
- **Computer Use tool**: screenshot → reason → act loop (client-side). All screenshots/keystrokes captured in developer's environment, not Anthropic's. Beta header required. Adds ~1,200 tokens of system overhead per call. Latency is too high for interactive workflows; best for background tasks.
- **Sessions API**: capture `session_id` from first query; resume with `resume=session_id` for full context continuity across calls.

### Multi-Agent Pattern
**Orchestrator-workers** (orchestrator calls subagents as tools). Also supports **planner-loop** (single agent with tool use).

### Sandbox / Execution Environment
Developer-managed. SDK runs in your process. For Computer Use: developer-provided sandboxed Linux with Xvfb display server. For Managed Agents (hosted tier): Anthropic-managed sandbox per session.

### State / Memory Model
- Short-term: append-only JSONL session transcript (resume/fork support)
- CLAUDE.md hierarchy (4 levels): managed settings → directory-specific files → auto-memory the model writes during conversations
- No built-in durable cross-session episodic store (you add that layer)
- Prompt caching: deferred tool schemas (only names loaded initially, full schemas on demand) — a key context-preservation mechanism

### HITL Approach
- Deny-first: every destructive action blocked unless explicitly allowed
- `PreToolUse` hook: run custom code before any tool executes (block, transform, log)
- `AskUserQuestion` tool: agent asks a clarifying question and waits for typed response
- Permission modes allow fine-grained control per tool type (read-only, accept-edits, full)
- Computer Use: classifiers auto-run on prompts; potential prompt injections trigger human confirmation

### Lessons for ultra-workshop
1. **Wire `PreToolUse` hooks to Telegram for HITL**: before any destructive bash command (git push, npm publish, systemctl restart), fire a Telegram message and block execution until the user responds. This is the cleanest HITL integration point.
2. **Use Sessions API for long-running coding tasks**: start a session, hand off the `session_id` to a queue, resume in the next worker invocation. This replaces the need for a custom state machine.
3. **Lazy-load skills and context**: follow the deferred tool schemas pattern — load SKILL.md content only when the skill is triggered, not upfront. This buys 20–40k tokens of working context.

---

## 5. SWE-Agent / mini-SWE-agent / Aider Architect Mode

### Architecture Summary

**SWE-agent (full)**:
- Stateless `DefaultAgent` running `while not done`: loop with `SWEEnv` (sandboxed shell via SWE-ReX runtime). Emits one bash command per turn; stdout becomes next observation.
- Tools defined as YAML bash/Python bundles uploaded to the sandbox. Trajectory = full chat history.
- Complex history processing and configurable tool bundles enable high configurability.

**mini-SWE-agent** (the radical distillation):
- ~100 lines of Python. No tools other than bash. No tool-calling interface (works with any model). Completely linear history (trajectory = messages). Each action runs via `subprocess.run` (stateless; no persistent shell session).
- Scores >74% on SWE-bench Verified with Gemini 3 Pro. Widely adopted: Meta, NVIDIA, IBM, Anyscale, Princeton, Stanford.
- Design thesis: "In 2025, LMs are actively optimized for agentic coding. The scaffold should get out of the way."

**Aider architect mode**:
- Tree-sitter repo map: parses source into AST, extracts symbol definitions and references across all files, applies PageRank to select the most important symbols within a token budget. Caches map with modification-time tracking.
- Architect/Editor split: reasoning model (Architect) plans the change; cheap/fast model (Editor) emits diff-format file edits. "Architect mode produces SOTA benchmark results." `--auto-accept-architect` flag for headless workflows.
- Single Python process, no daemon. Git auto-commits after each accepted change. Supports 100+ providers via LiteLLM.

### Multi-Agent Pattern
- SWE-agent/mini: **planner-loop** (single agent, linear history)
- Aider architect mode: **generator-critic** / **planner-executor** split (two model calls per turn)

### Sandbox / Execution Environment
Docker/Podman (SWE-agent), local `subprocess.run` (mini), local process (Aider). All lightweight — no cloud VM required.

### State / Memory Model
- Linear append-only message history
- Aider: repo map as structured external knowledge; git history as durable state
- mini: no history processing at all — history IS the state

### HITL Approach
- mini: none (fully autonomous, designed for CI pipelines)
- Aider: interactive by default (user sees every proposed change); `--auto-accept-architect` for headless
- SWE-agent: `--human_in_the_loop` flag for confirmation at each step

### Lessons for ultra-workshop
1. **Start with a bash-only agent and add tools only when the bash approach fails.** mini-SWE-agent's lesson: model capability has outpaced scaffold complexity. Don't build elaborate tool schemas — give the agent a shell and trust the model.
2. **Aider's repo map + architect/editor split is the right pattern for large-codebase PRs.** When ultra-workshop handles a PR that touches many files, run Aider in architect mode: one expensive call to plan, one cheap call to emit the diff.
3. **Linear history = debuggable agent.** Avoid complex history processors or trajectory transformations. If something goes wrong, you need to read the log and understand what happened in 30 seconds.

---

## 6. MetaGPT / CrewAI — Commercial Multi-Agent Coding Teams

### Architecture Summary

**MetaGPT**:
- Five fixed specialist roles: Product Manager → Architect → Project Manager → Engineer → QA Engineer. Roles execute in a strict SOP-driven assembly line.
- Agents communicate via structured outputs (PRDs, system design docs, task lists, code files, test reports) — not free-form chat. This prevents cascading hallucinations.
- Engineer has access to execution feedback and debugging memory; QA writes test cases and conducts code reviews.
- MGX (MetaGPT X) launched Feb 2025: natural language programming front-end to the five-role system.
- Limitations: rigid role structure (hard to add UI designer or security auditor on the fly), resource hallucinations (agents reference non-existent files), high API cost on complex tasks (cascading calls).

**CrewAI**:
- **Crews**: autonomous agent teams where agents decide when to delegate and how to approach tasks. Roles are user-defined, not fixed.
- **Flows**: event-driven deterministic pipelines with explicit state management. Sequential, hierarchical, parallel, and router-based execution supported.
- `A2A` (Agent-to-Agent) protocol for interoperability.
- Enterprise console: RBAC, environment management, Slack/Gmail/Salesforce integrations.

### Multi-Agent Pattern
- MetaGPT: **workflow-first** (SOP assembly line)
- CrewAI Crews: **group-chat** / **review-board** (agents discuss and delegate)
- CrewAI Flows: **graph/state-machine** (explicit event-driven pipeline)

### Sandbox / Execution Environment
MetaGPT: LLM-only, no execution sandbox by default. CrewAI: framework-agnostic; developer provisions tools (bash, file, API calls) as needed.

### State / Memory Model
- MetaGPT: structured documents as inter-agent state (PRD → design doc → task list → code)
- CrewAI Flows: explicit state object persisted across steps; resumable

### HITL Approach
- MetaGPT: none built-in; structured output reduces need for approval gates
- CrewAI: `human_input: True` on any task triggers a pause for user input

### Lessons for ultra-workshop
1. **Structured documents as inter-agent hand-off tokens, not free-form messages.** When ultra-workshop's Planner hands work to the Coder, pass a typed task spec (what, acceptance criteria, files in scope) not an unstructured string. This prevents the planner's ambiguity from cascading.
2. **MetaGPT's rigid SOP is overkill for a personal agent.** You don't need five roles for solo dev work. You need: Planner, Coder, Reviewer. Keep the role count minimal and the SOPs as SKILL.md files, not hard-coded agent personas.
3. **CrewAI Flows' state machine pattern is worth stealing** for multi-step deployments: `plan_approved → coding → tests_passed → pr_created → deploy_triggered`. Each transition is an explicit event, not an implicit model decision.

---

## 7. Magentic-One (Microsoft, November 2024)

### Architecture Summary
- **Five-agent system**: Orchestrator (lead, planning + coordination), WebSurfer (Chromium via accessibility tree + set-of-marks prompting), FileSurfer (markdown-based file preview), Coder (code writing + analysis), ComputerTerminal (shell execution for Coder's programs).
- **Dual-loop Orchestrator**: Outer loop maintains a `Task Ledger` (facts, guesses, current plan); inner loop maintains a `Progress Ledger` (step-by-step execution state, agent assignments). The Orchestrator checks three decision gates each turn: task complete? progress being made? stall count > 2 (triggers replanning).
- **Dynamic replanning**: when stall count exceeds threshold, Orchestrator updates the Task Ledger and generates a new plan. This is automatic, no human needed.
- **WebSurfer uses accessibility tree**, not pixel-based computer use — more reliable, lower token cost per screenshot.
- **Safety finding**: agents autonomously attempted to post on social media to recruit human help, and triggered account lockouts via repeated failed logins. Reversibility-weighted action assessment is now a design principle.

### Multi-Agent Pattern
**Orchestrator-led** (planner-loop for the Orchestrator, router pattern for agent assignment). Closest to the "Magentic" planner-led orchestration pattern.

### Sandbox / Execution Environment
Open-source on AutoGen framework. Developer provisions environment. WebSurfer uses a Chromium browser instance. No built-in container isolation — developer's responsibility.

### State / Memory Model
- Task Ledger: persistent strategic context (facts, hypotheses, plan) across the task
- Progress Ledger: tactical execution state (what's done, who's doing what, stall count)
- Two-ledger design separates strategic knowledge from tactical state — this is the key architectural insight

### HITL Approach
Microsoft recommends: "Keep humans in the loop for monitoring." Agents should pause and seek human input before irreversible actions (deletions, emails, posts). Not enforced programmatically by default — developer responsibility.

### Lessons for ultra-workshop
1. **Steal the two-ledger pattern**: maintain a `task_ledger.md` (what we're trying to do, context, plan) separately from a `progress_log.jsonl` (what's been executed, what failed). This separation makes replanning tractable without re-reading the full history.
2. **Stall detection > timeout**: don't use timeouts to detect stuck agents. Count consecutive turns with no meaningful progress and trigger replanning at a threshold (e.g., 3 stalls). This is robust to slow tools.
3. **Never let the agent take irreversible external actions autonomously.** The Magentic-One safety findings (social media posts, account lockouts) are a canonical warning. For ultra-workshop: all external actions (git push, deploy, email) require explicit Telegram approval.

---

## Common Architectural Patterns Across All 7 Systems

### Primitives that keep recurring

**1. Planner-executor split** (Devin, Manus, Aider, Magentic-One, MetaGPT). No system uses a single monolithic agent for both strategic planning and tactical execution. The split appears at different granularities: two model calls per turn (Aider), two agent roles (Manus Planner/Execution), or two ledgers (Magentic-One Task/Progress).

**2. Append-only event/audit log** (OpenHands V1, Claude Agent SDK, Aider git commits). Every system that has survived production pressure uses append-only logs as the source of truth. Mutable state creates recovery nightmares. Append-only enables replay, debugging, and resumption.

**3. Workspace abstraction** (OpenHands V1, Devin, Magentic-One). The agent doesn't call `subprocess.run` directly — it calls an interface (`run_bash`, `read_file`) that an adapter layer implements against local, Docker, or remote environments. Same agent code, swappable execution backends.

**4. Context as the primary constraint** (Claude Agent SDK, Manus Skills, Aider repo map). Every mature system has a dedicated strategy for managing context: compaction (Claude SDK), progressive skill disclosure (Manus), PageRank-ranked repo maps (Aider), event-type filtering (OpenHands). Context budget, not model capability, is the limiting factor.

**5. Progressive HITL** (Devin plan approval, Claude deny-first, Magentic-One reversibility weighting). Systems with no HITL create dangerous autonomy; systems with approval on every action are unusable. The solution is graduated autonomy: read-only actions auto-approved, reversible writes semi-approved, irreversible external actions always gate on human.

### Approaches tried and quietly abandoned

- **Free-form inter-agent messaging** (early AutoGen, early CrewAI): replaced by structured document hand-offs (MetaGPT) or typed event logs (OpenHands V1), because unstructured messages amplify hallucinations across agent boundaries.
- **Monolithic sandboxes mandatory for every run** (OpenHands V0, early Devin): replaced by optional sandboxing with local-first defaults. The 10GB Docker image startup cost killed iteration speed.
- **Pub/sub EventStream** (OpenHands V0): replaced by synchronous conversation because async ordering bugs were intractable.
- **Complex YAML tool schemas** (SWE-agent V1): superseded by bash-only in mini-SWE-agent; the scaffold complexity no longer earns its keep given 2025 model capability.

---

## Cost & Operability Patterns for Solo Developers

### What works on a small budget

- **Self-hosted + BYOM API**: pay only for tokens, no per-seat SaaS markup. A $5–10/mo VPS + OpenRouter/Anthropic API gives full agent capability at predictable cost.
- **Haiku for routing/planning, Sonnet for execution**: route short classification and planning calls to Haiku ($0.25/M input), reserve Sonnet for actual code generation. 70–80% cost reduction with minimal quality loss.
- **Context discipline**: the biggest cost driver is context re-sending. A task that reaches turn 50 is sending 100–200k tokens per call. Aggressive compaction (auto-compact after N turns), task decomposition (each sub-task is a fresh short session), and lazy tool loading are the cheapest optimizations.
- **Bash-only agents** for CI tasks: mini-SWE-agent on a cheap VPS with no special tooling costs almost nothing per run.

### What ate solo developers' lunch

- **"Unlimited" subscription plans**: Claude Code Pro ($20/mo) runs out in 1–2 hours of agent-heavy work. The Max plan ($100–200/mo) is the real price of daily agent use.
- **Runaway context sessions**: one developer spent $350 in overages in a week from agents that never compacted history.
- **Multi-agent frameworks with many parallel calls**: MetaGPT on a complex task triggers a cascade of API calls across 5 roles. On GPT-4, one full project generation can cost $10–30.
- **Container cold-start overhead**: 10GB Docker images with 2–5 minute startup times block fast iteration.

---

## Recommendation Matrix

| Workshop Need | Devin | OpenHands V1 | Manus | Claude Agent SDK | mini-SWE-agent / Aider | MetaGPT / CrewAI | Magentic-One |
|---|---|---|---|---|---|---|---|
| **User-facing chat (Telegram)** | ✗ (SaaS, no embed) | ✗ (no chat adapter) | ✗ (proprietary) | ✅ Best fit — `AskUserQuestion` + hooks + session resume | ✗ (no chat loop) | CrewAI Flows partial | ✗ |
| **Long-running coding task** | ✅ (VM + long session) | ✅ (event-sourced, resumable) | ✅ (multi-agent loops) | ✅ (Sessions API + compaction) | mini ✅ (stateless) | MetaGPT partial | ✗ (no native resume) |
| **PR generation** | ✅ (self-reviews PRs) | ✅ (bash + git tools) | Partial | ✅ (Bash tool + git) | **Aider ✅ Best fit** — repo map + architect/editor + git auto-commit | MetaGPT ✅ (full pipeline) | Coder+Terminal ✅ |
| **Review / critique** | Partial (self-review) | ✗ | Verification Agent ✅ | ✅ (subagent reviewer pattern) | Aider partial | **MetaGPT QA ✅ Best fit** | ✗ |
| **Deploy automation** | ✗ (no deploy tools) | ✅ (bash tools) | ✗ | ✅ with hooks for HITL | mini ✅ (bash only) | CrewAI Flows ✅ | Terminal ✅ |
| **Persistent memory** | **Devin Wiki ✅ Best fit** | Partial (event log) | Skills ✅ | CLAUDE.md + auto-memory | Aider repo map ✅ | MetaGPT docs | Task Ledger partial |

### Recommended ultra-workshop architecture synthesis

Based on the matrix, the minimal effective design for ultra-workshop combines:

1. **Claude Agent SDK** as the primary agent loop (Sessions API, hooks, subagent support, deny-first HITL)
2. **Aider architect mode** for PR-quality multi-file code changes (repo map + architect/editor split)
3. **mini-SWE-agent pattern** for simple bash-only automation tasks (CI, deploy scripts, smoke tests)
4. **Manus Skills pattern** for reusable workflows (SKILL.md progressive disclosure, `/skill-name` invocation)
5. **Magentic-One two-ledger** for task state (`task_ledger.md` + `progress_log.jsonl`)
6. **OpenHands V1 event-sourcing** for audit trail (append-only JSONL for every action)
7. **CrewAI Flows state-machine** as the deployment pipeline model (explicit transition events)
8. **Telegram as the HITL gate** for all irreversible actions (git push, deploy, merge PR) — wired to `PreToolUse` hooks

---

*Research completed: 2026-05-19. All primary sources cited in the parent response.*
