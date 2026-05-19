# Multi-Agent Orchestration Frameworks for Personal Autonomous Systems

Research brief for designing a personal multi-agent orchestrator with a chat-tool front-end (Telegram/Slack/Discord) and a persistent "second brain" memory layer. Data verified against the GitHub API on 2026-05-17 and Context7 official docs.

These seven candidates split into four shapes — and the shapes matter more than the feature lists:

1. **DIY orchestration libraries** — LangGraph, CrewAI. You assemble everything.
2. **Wrong-shape candidate** — MetaGPT. Built for software-team simulation, not personal life ops.
3. **Turnkey personal assistants** — OpenClaw, Hermes Agent, OpenHuman. Direct fits.
4. **Meta-shell over CLI agents** — AionUi. Electron UI that conducts other agents (including Claude Code).

The user's existing Claude Code ecosystem is load-bearing: it changes which of these compete with the orchestrator vs. extend it.

---

## 1. LangGraph — `langchain-ai/langgraph`

**What it is.** A low-level Python orchestration library that models agents as a directed graph of nodes with explicit state. Stars: 32.2k. License: MIT. Last push: 2026-05-17 (active). Version 1.2.0 released May 2026 — past the 1.0 stability line.

**Architectural pattern.** State-machine graph (Pregel-inspired). Three canonical multi-agent topologies ship as recipes: **supervisor** (central router delegates to specialists via `langgraph-supervisor-py`), **swarm** (peer agents hand off control), and **hierarchical** (supervisor of supervisors). Memory is first-class: `checkpointers` persist thread state, `stores` hold cross-thread long-term memory with semantic search (Postgres, Redis, in-memory backends ship in the box).

**Strengths.** Durable execution — agents resume exactly where they crashed. Human-in-the-loop is a primitive, not an afterthought. LangSmith gives you trace-level debugging. The memory model maps cleanly onto a second-brain layer: thread checkpoints are conversation state, store namespaces are user/topic-scoped semantic memory. It's the only library here where "agent crashes mid-task, resumes tomorrow when user pings via Telegram" is a one-liner.

**Weaknesses.** You build the chat gateway yourself. You build the integrations yourself. LangChain ecosystem drift is real — APIs churn. Steep learning curve relative to CrewAI. Not a product, a toolkit.

**Integration story.** (a) Chat: nothing built-in; wire your own python-telegram-bot/Bolt/discord.py adapter to invoke the graph. (b) Second brain: native fit via `Store` interface — back it with Postgres+pgvector or Redis, namespace by user/domain. (c) Claude Code ecosystem: Claude Code agents become MCP tools the graph invokes; no overlap, pure extension.

**Verdict.** Pick LangGraph when you want a **bespoke orchestrator** with full control over state, memory, and recovery semantics — and you're willing to write the chat/integration layer yourself. The right foundation if the orchestrator itself is the product.

---

## 2. CrewAI — `crewaiinc/crewai`

**What it is.** A higher-level Python framework for "crews" of role-playing agents executing tasks. Stars: 51.6k. License: MIT (OSS framework) + commercial AMP tier. Last push: 2026-05-16. Confirmed standalone: full OSS works with local Ollama, no enterprise dependency.

**Architectural pattern.** **Role + task** abstraction with two processes: `sequential` (predefined task chain) and `hierarchical` (manager LLM auto-delegates, with optional `planning=True`). Four memory types out of the box: short-term, long-term, entity, contextual — toggled via `memory=True` on a Crew. Embedder is configurable (OpenAI, Ollama, etc.).

**Strengths.** Fastest path from "I have an idea" to "I have a crew." Memory types map intuitively to second-brain concepts (entities = people/projects, long-term = patterns). 2.8k code examples in Context7 — the documentation surface is enormous. AMP enterprise tier exists but the OSS is fully usable on its own.

**Weaknesses.** Role-play metaphor doesn't always fit personal workflows ("you are a senior researcher" feels silly when triaging your inbox). The hierarchical manager is opinionated — less control than LangGraph's explicit graph. Memory is convenient but less flexible than LangGraph's typed stores. Enterprise upsell present but not coercive.

**Integration story.** (a) Chat: no built-in gateway; wrap a Crew invocation behind your bot framework. (b) Second brain: `memory=True` + custom embedder gets you 80% there; the `Memory` class accepts Mem0/external backends. (c) Claude Code: Claude Code is invokable as a tool from a CrewAI task; some conceptual overlap (both think in agents) but not blocking.

**Verdict.** Pick CrewAI over LangGraph when **speed-to-prototype** beats fine-grained control, and your problem maps naturally to "team of specialists with a coordinator." The right choice if you want a working orchestrator this week.

---

## 3. MetaGPT — `FoundationAgents/MetaGPT`

**What it is.** Stars: 68.1k, MIT, but **last push 2026-01-21** — slowing. Simulates a software company: PM, architect, engineer roles produce code from a single requirement.

**Architectural pattern.** Role-based SOP execution: `Code = SOP(Team)`. Strictly artifact-generation oriented.

**Verdict.** **Wrong shape for personal life-ops orchestration.** It's a software-house simulator that outputs requirements docs, ER diagrams, and codebases. Memory is per-project; chat integration is absent. Useful if you want to spawn a coding subagent inside another orchestrator — not as the orchestrator itself. Skip.

---

## 4. OpenHuman — `tinyhumansai/openhuman`

**What it is.** Stars: 12.3k. License: **GPL-3.0** (the only copyleft entry — material). Created Feb 2026, 366 contributors. Rust+TypeScript desktop app (Tauri). "Personal AI super intelligence, private, simple, powerful."

**Architectural pattern.** Desktop-first product, not a library. Four pillars: (1) **Memory Tree** — auto-fetches 118+ OAuth-connected services every 20 minutes, compresses into ≤3k-token hierarchical Markdown summaries stored locally in SQLite + an **Obsidian-compatible vault**; (2) model routing across reasoning/fast/vision tiers; (3) TokenJuice compression (claimed 80% reduction); (4) desktop mascot that joins Google Meets as a participant.

**Strengths.** **The second brain is the product.** Karpathy-inspired Obsidian-wiki workflow is exactly the "persistent memory layer" the user described. 118 OAuth connectors with auto-sync removes the worst part of building a personal AI (data ingestion). Optional `agentmemory` backend lets the same memory power Claude Code, Cursor, Codex side-by-side — directly addresses the user's existing-ecosystem constraint.

**Weaknesses.** **GPL-3.0** infects any code you statically link or distribute that builds on it — a real concern if you ever ship anything. Early beta — explicit warning in README. Three-month-old project (Feb 2026); unproven longevity. Rust core means hacking on internals is steeper than the Python alternatives. Chat coverage is thinner than OpenClaw/Hermes.

**Integration story.** (a) Chat: "multi-channel inbox" claimed, fewer platforms detailed than OpenClaw. (b) Second brain: **flagship feature** — Memory Tree + Obsidian vault is on-disk, inspectable, editable, agentmemory-shareable. (c) Claude Code: explicit story via the agentmemory backend — best cross-tool memory story in this list.

**Verdict.** Pick OpenHuman when the **second brain matters more than the orchestrator**, you accept GPL-3.0, and you can tolerate early-beta rough edges. Strongest fit on the memory axis specifically; weakest on the maturity axis.

---

## 5. Hermes Agent — `NousResearch/hermes-agent`

**What it is.** Stars: 154.4k (verified). MIT. Python. Created Jul 2025, **8,640+ commits, 4.1k issues, 5k+ PRs in ~10 months** — extraordinarily active. Built by Nous Research. "The agent that grows with you."

**Architectural pattern.** Single-agent harness with a **closed learning loop**: autonomous skill creation after complex tasks, FTS5 cross-session search + LLM summarization, Honcho dialectic user modeling, and parallel subagent spawning. Compatible with the `agentskills.io` open standard (shared skill ecosystem). Seven terminal backends including Modal/Daytona serverless that hibernate when idle.

**Strengths.** **First-class messaging gateway** — Telegram, Discord, Slack, WhatsApp, Signal, Email all via a single `hermes gateway start`. Voice memo transcription. Cron scheduling with delivery to any platform ("daily summary at 8am via Telegram"). MCP integration means your Claude Code skills plug straight in. Skills + memory + multi-channel chat are all built-in primitives, not glue you write.

**Weaknesses.** Single-agent (with subagent spawning) rather than true multi-agent orchestration — if you need a graph of specialists working in parallel, this isn't it. Massive PR/issue backlog suggests velocity outpacing review. Heavy dependency footprint (uv-installed full Python+Node toolchain plus optional voice deps).

**Integration story.** (a) Chat: **best-in-class** — five platforms + email + voice in the box. (b) Second brain: persistent memory + user profile modeling + FTS5 search; not as deep as OpenHuman's Memory Tree but operationally simpler. (c) Claude Code: MCP-native; OpenClaw migration path shipped; runs alongside Claude Code as a peer assistant rather than as a controller.

**Verdict.** **Top recommendation** if the goal is "personal autonomous orchestrator accessible via chat tool with persistent memory." Hermes solves the entire problem statement as a turnkey product. The trade-off: you accept Nous Research's opinions about how an agent should work.

---

## 6. OpenClaw — `openclaw/openclaw`

**What it is.** Stars: 372.6k (verified). MIT. TypeScript/Node. Created Nov 2025. Sponsored by OpenAI, GitHub, NVIDIA, Vercel — heavyweight backing. "Personal AI assistant you run on your own devices. The lobster way."

**Architectural pattern.** **Gateway** as control plane: sessions, channels, tools, events. **Multi-agent routing** — inbound channels/accounts route to isolated agent workspaces with per-agent sessions. Hub-and-spoke. Workspace at `~/.openclaw/workspace`; skills registry via ClawHub.

**Strengths.** **Channel coverage is unmatched** — 23+ platforms (WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Matrix, Teams, etc.), voice on macOS/iOS/Android, Live Canvas for visual workflows. Multi-agent routing means different chat surfaces can route to different agent workspaces (work agent on Slack, personal agent on iMessage). Strong security defaults: untrusted-DM pairing required by default, optional Docker/SSH sandboxing for non-`main` sessions. Daily release cadence.

**Weaknesses.** Six-month-old project despite the star count — community velocity, not battle-tested longevity. Hermes ships a `hermes claw migrate` command precisely because OpenClaw users are migrating off it — worth understanding why before committing (per Nous, OpenClaw's plugin-reliant memory was a pain point). TypeScript stack if you prefer Python. Skills less mature than Hermes's self-improving loop.

**Integration story.** (a) Chat: **most channels of any candidate** + best multi-platform UX. (b) Second brain: workspace-local but plugin-reliant; weakest memory story among the three turnkey assistants. (c) Claude Code: runs as a peer assistant; Hermes is actively poaching its user base.

**Verdict.** Pick OpenClaw over Hermes when **channel breadth and multi-agent routing per channel** matter more than memory depth. The strongest "I want one agent answering me wherever I am" story. Weakest of the three turnkey options on the memory dimension.

---

## 7. AionUi — `iOfficeAI/AionUi`

**What it is.** Stars: 25.4k. Apache-2.0. TypeScript/Electron+React+Vite+Bun. Created Aug 2025. "Free, local, open-source 24/7 Cowork app." Tagline literally lists OpenClaw, Hermes Agent, Claude Code, Codex among the CLIs it wraps.

**Architectural pattern.** **Meta-shell**: Electron desktop UI that auto-detects installed CLI agents (Claude Code, Codex, Hermes Agent, OpenClaw, Qwen Code, Cursor Agent, 16+ more) and lets you Cowork with all of them in a unified interface. Built-in agent engine for zero-setup users. SQLite + file-based + git-versioned conversation/document history. MCP tool support.

**Strengths.** **Doesn't replace Claude Code — it conducts it.** If the user is already invested in Claude Code agents/skills, AionUi keeps that ecosystem and adds a chat-tool surface (Telegram/Lark/DingTalk/WeChat; Slack planned). Team mode coordinates multiple CLI agents on one task. WebUI for phone-from-LAN access. 20 built-in professional assistants (PPT/Word/Excel/dashboard creators).

**Weaknesses.** **Chinese ecosystem bias** — Lark/DingTalk/WeChat first-class; Slack still "planned"; Telegram supported but not the primary surface. Electron desktop dependency (always-on app on a machine). Multi-agent coordination across heterogeneous CLIs is impressive but fragile. The "Cowork" framing is desktop-centric — less natural for ambient chat-tool-first usage.

**Integration story.** (a) Chat: Telegram + WebUI cover the user's stated need; Slack pending. (b) Second brain: local SQLite + git-versioned files — workmanlike, not innovative. (c) Claude Code: **uniquely additive** — wraps it rather than competing. Lowest-disruption option if the existing Claude Code investment is large.

**Verdict.** Pick AionUi when you want to **preserve and conduct an existing CLI agent ecosystem** rather than start over with a new harness. Best fit when "the Claude Code stack stays; I just need a chat surface and coordination layer."

---

## Comparison Table

| Framework | Orchestration pattern | Memory story | Chat integration ease | Lock-in risk | Recommended fit |
|---|---|---|---|---|---|
| **LangGraph** | Stateful graph; supervisor/swarm/hierarchical recipes | Excellent — typed Stores + checkpointers, Postgres/Redis backends, semantic search built in | **Build your own** (no gateway) | Low (MIT, swappable LLM, ecosystem-agnostic) | Bespoke orchestrator where state/memory/recovery matter and you own the chat layer |
| **CrewAI** | Role-task crews; sequential or hierarchical with manager LLM | Good — 4 memory types via `memory=True`, BYO embedder, Mem0-compatible | Build your own (no gateway) | Low OSS / Medium if you adopt AMP enterprise tier | Fastest "team of specialists" prototype; cleaner DX than LangGraph |
| **MetaGPT** | SOP-driven software-company role simulation | Project-scoped artifacts | None | Low (MIT) but irrelevant — wrong shape | **Skip** — built for code generation, not personal ops |
| **OpenHuman** | Desktop assistant + Memory Tree + 118 OAuth integrations | **Best in class** — Memory Tree + Obsidian vault + agentmemory cross-tool backend | Multi-channel claimed; thinner than OpenClaw/Hermes | **High** (GPL-3.0 — copyleft) + Early Beta | When second-brain depth dominates and GPL is acceptable |
| **Hermes Agent** | Single agent + parallel subagents + closed learning loop + skills | Strong — persistent memory, Honcho user modeling, FTS5 search, agentskills.io | **Best in class** — TG/Discord/Slack/WhatsApp/Signal/Email + voice + cron all built in | Low (MIT, BYO LLM, OpenClaw-migration tooling shipped) | **Top pick** — solves the entire stated problem turnkey |
| **OpenClaw** | Gateway control plane + multi-agent routing per channel | Workspace-local + plugins; weakest of the turnkey three | **Best channel breadth** — 23+ platforms incl. iMessage/Matrix/Teams | Low (MIT) but users actively migrating to Hermes — signal to weigh | When 5+ chat channels matter more than memory sophistication |
| **AionUi** | Meta-shell conducting existing CLI agents (Claude Code, Codex, Hermes, OpenClaw) | Local SQLite + git-versioned files | Telegram + WebUI; Lark/DingTalk/WeChat first-class; Slack planned | Low (Apache-2.0); preserves your existing CLI investments | When you keep Claude Code and want a chat surface on top |

---

## Final Recommendation

**Pick Hermes Agent.** It solves the entire problem statement — autonomous orchestration, persistent self-curated memory, native chat-tool gateway (TG/Discord/Slack/WhatsApp/Signal/Email), cron scheduling, MCP integration with your Claude Code skills — as a turnkey product. The closed learning loop and skill self-improvement are unique. The migration story from OpenClaw is also the loudest market signal in this list.

**Runner-up: LangGraph.** If after evaluating Hermes you find its single-agent shape too constraining for genuine multi-agent parallel work, drop down a layer to LangGraph. You'll write more code, but you'll own the architecture. Postgres-backed Stores give you the same second-brain primitive without GPL contamination, and the supervisor/swarm recipes are first-class.

**Wildcard: AionUi over Hermes** only if your existing Claude Code agent/skill investment is large enough that throwing it away costs more than the chat-surface convenience Hermes provides. AionUi conducts; Hermes replaces.

**Skip MetaGPT** (wrong shape) and **avoid OpenHuman until it leaves early beta** unless the Obsidian-vault second brain is non-negotiable and you accept GPL-3.0.

The Hermes ↔ OpenClaw lineage matters strategically: these aren't permanent choices. `hermes claw migrate` exists; OpenHuman has an `agentmemory` cross-tool backend; AionUi auto-detects whichever you pick. Optimize for the next 6 months, not the next 5 years.

---

## Sources

- GitHub API (stars, license, last-push, contributors) verified 2026-05-17
- Context7 official docs: LangGraph (`/websites/langchain_oss_python_langgraph`), CrewAI (`/crewaiinc/crewai`)
- Project READMEs: openclaw/openclaw, NousResearch/hermes-agent, iOfficeAI/AionUi, tinyhumansai/openhuman
- crewai.com (commercial tier confirmation)
