# Model-Agnostic Multi-Agent Orchestration — Research Report

**Date:** 2026-05-17
**Verification method:** Raw `curl https://api.github.com/repos/...` + `jq` (no AI summarizer in path) for all star counts, then cross-validated against Context7 official docs for library features. Star counts and metadata in this report are primary-source numbers, not WebFetch summarizer output.

---

## Task A — GitHub repo verification (ground truth)

All twelve repos checked via direct GitHub REST API. None returned 404. Numbers below are exact `stargazers_count` as of 2026-05-17.

| Repo | Stars | License | Created | Last push | Lang | Status |
|---|---|---|---|---|---|---|
| `tinyhumansai/openhuman` | **12,377** | GPL-3.0 | 2026-02-18 | 2026-05-17 | Rust | Real, ~3 mo old |
| `NousResearch/hermes-agent` | **154,416** | MIT | 2025-07-22 | 2026-05-17 | Python | Real, viral |
| `openclaw/openclaw` | **372,609** | MIT | 2025-11-24 | 2026-05-17 | TypeScript | Real, **GitHub top-10 globally** |
| `iOfficeAI/AionUi` | **25,412** | Apache-2.0 | 2025-08-07 | 2026-05-16 | TypeScript | Real |
| `danielmiessler/Personal_AI_Infrastructure` | **13,983** | MIT | 2025-09-08 | 2026-05-12 | TypeScript | Real |
| `FoundationAgents/MetaGPT` | **68,061** | MIT | 2023-06-30 | 2026-01-21 | Python | Real, slowing (4-month gap) |
| `BerriAI/litellm` | **47,301** | NOASSERTION* | 2023-07-27 | 2026-05-17 | Python | Real, very active |
| `pydantic/pydantic-ai` | **17,109** | MIT | 2024-06-21 | 2026-05-17 | Python | Real, very active |
| `crewAIInc/crewAI` | **51,574** | MIT | 2023-10-27 | 2026-05-16 | Python | Real, very active |
| `langchain-ai/langgraph` | **32,240** | MIT | 2023-08-09 | 2026-05-17 | Python | Real, very active |
| `ollama/ollama` | **171,610** | MIT | 2023-06-26 | 2026-05-15 | Go | Real, mainstream |
| `vllm-project/vllm` | **80,256** | Apache-2.0 | 2023-02-09 | 2026-05-17 | Python | Real, mainstream |

\* LiteLLM's `NOASSERTION` is GitHub's marker for a non-SPDX license file. The actual license is MIT per their LICENSE file — GitHub's classifier just doesn't recognize their preamble. Treat as MIT for legal purposes but confirm with `cat LICENSE` before any redistribution.

**Important caveat on hallucination check.** The prior agent's flag of "372k stars is implausible" was correct caution but turns out wrong on the facts. OpenClaw at 372,609 stars genuinely sits between `EbookFoundation/free-programming-books` and `nilbuild/developer-roadmap` in GitHub's global ranking. It was created Nov 2025 — post-training-cutoff for the prior agent — which explains the suspicion. Verified by raw API call, not via the same WebFetch summarizer pattern that produced the original numbers.

**Model-agnostic posture per repo** (Task A second axis):

- **openhuman** — Ollama explicitly mentioned for "Optional local AI." Model routing layer (reasoning/fast/vision tiers). No LiteLLM dep visible in docs.
- **hermes-agent** — Explicitly multi-provider via `hermes model` CLI. Documented providers: Nous Portal, OpenRouter (200+ models), NovitaAI, NVIDIA NIM, Xiaomi MiMo, z.ai/GLM, Kimi/Moonshot, MiniMax, Hugging Face, OpenAI, Anthropic, custom endpoints. Tagline: "no code changes, no lock-in."
- **openclaw** — "Models config + CLI: Models" with "many providers and models supported." OpenAI subscription is a path, not the only one.
- **AionUi** — Most explicit: 20+ platforms including Gemini, Anthropic, OpenAI, AWS Bedrock, Ollama, LM Studio, Dashscope/Qwen, Moonshot, DeepSeek, NewAPI gateway.
- **Personal_AI_Infrastructure** — "Claude Code native" today; Ollama + llama.cpp on roadmap. Currently the *least* model-agnostic of the bunch.
- **MetaGPT** — Config supports `api_type: 'openai' | azure | ollama | groq | etc` via `LLMType` enum. Genuine but the framework is the wrong shape for personal life-ops (see Task D).

---

## Task B — Model-agnostic orchestration stacks

### 1. LiteLLM (BerriAI) — **the canonical answer**

47,301 stars, very active (pushed today). Two ways to use it:

- **Python SDK** — call any of ~100 LLMs by setting `model="anthropic/claude-sonnet-4-5"`, `model="ollama_chat/llama3.3"`, `model="groq/llama-3.3-70b"`. Unified OpenAI-style request/response shape. Cost tracking, retries, fallbacks built-in.
- **Proxy server (LLM Gateway)** — run `litellm --config config.yaml`, get an OpenAI-compatible HTTP endpoint at `:4000/v1/chat/completions`. Any client that speaks OpenAI (including the official `openai` SDK with a `base_url` override) hits it transparently.

Verified from Context7 official docs:
- **Tool calling** works across providers including Ollama. From the docs: *"LiteLLM defaults to JSON mode tool calls if native tool calling not supported."* So tool calling is *uniform at the API level* even if the underlying model doesn't natively support function calling — LiteLLM patches the gap.
- **Structured outputs (`response_format: json_schema`)** supported across OpenAI, Azure, xAI, Vertex, Bedrock, Anthropic, Groq, Ollama, Databricks. For Anthropic specifically, LiteLLM auto-translates `response_format` → Anthropic's `output_schema` and adds the `anthropic-beta: structured-outputs-2025-11-13` header. Zero conversion code on your side.
- **Streaming** (`stream=True`) supported across the same provider matrix.
- **MCP tool calling** supported uniformly — you can pass `tools: [{"type": "mcp", "server_url": "..."}]` and LiteLLM routes correctly per provider.

**Trade-off.** It's a *routing layer*, not an *orchestration framework*. Worker/orchestrator graph topology is on you. But that's exactly what the user wants — the orchestrator is supposed to be theirs.

### 2. Pydantic AI

17,109 stars, very active, MIT. Pydantic team — same people who built Pydantic, the de facto Python validation library.

From Context7 docs (verified):
- **Provider coverage:** *"Built-in support for OpenAI, Anthropic, Gemini, xAI, Bedrock, Cerebras, Cohere, Groq, Hugging Face, Mistral, OpenRouter, and Outlines. Also supports numerous providers compatible with the OpenAI API via `OpenAIChatModel`."*
- **Runtime model swap:** Models can be pre-registered with names (`'fast'`, `'reasoning'`) on an Agent, then selected per `.run()` call. A `provider_factory` callable lets you inject API keys from request context — clean per-request routing.
- **Native Ollama support** with `NativeOutput` for grammar-constrained structured outputs (Ollama 0.5.0+ via llama.cpp grammars). This is genuinely better than JSON-mode coercion because the decoder enforces the schema at token-generation time.
- **Pydantic AI Gateway** (managed) exists as an OpenAI/Anthropic/Vertex/Groq/Bedrock unified endpoint, but is opt-in — the SDK works fine without it.

**Trade-off.** Higher-level than LiteLLM: it's an Agent abstraction (instructions, tools, output_type) rather than a chat-completions wrapper. If you want an orchestrator with typed I/O, this is the cleanest entry point. If you want raw model calls, LiteLLM is lower-friction.

### 3. LangChain + LangGraph

LangGraph: 32,240 stars, MIT, very active.

**Model-agnostic story.** Mediated through LangChain's `chat_models` package, which has per-provider classes (`ChatOpenAI`, `ChatAnthropic`, `ChatOllama`, `ChatGroq`, etc.). Each has slightly different kwargs and error semantics — not as uniform as LiteLLM. You can use LiteLLM *underneath* LangGraph via `init_chat_model("openai/...", base_url="http://localhost:4000")` pointed at a LiteLLM proxy, which is the cleanest way to bypass LangChain's per-provider drift.

**Lock-in cost.** Real. LangGraph's value is its graph/state primitives (`StateGraph`, `Command`, `Send`, `interrupt`, checkpointers, stores). Those are LangGraph-specific. You'd be hard-pressed to migrate a sophisticated LangGraph to another orchestrator without rewriting the state machine.

**Verdict for this task.** Overkill unless you need durable execution + human-in-the-loop primitives. The user's "1 orchestrator + ephemeral workers" is a much simpler topology than LangGraph's sweet spot.

### 4. Plain Python + OpenAI SDK with `base_url` override

The minimum-viable model-agnostic stack:

```python
from openai import OpenAI

# Ollama (no API key needed)
ollama = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

# Groq
groq = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=GROQ_KEY)

# OpenAI itself
oai = OpenAI(api_key=OAI_KEY)

# Anthropic via LiteLLM proxy
claude = OpenAI(base_url="http://localhost:4000/v1", api_key=LITELLM_KEY)
```

**Pros.** Zero abstraction tax. You know exactly what's on the wire. Easiest to debug. The OpenAI SDK is rock-solid. Ollama, Groq, Together, Fireworks, Perplexity, OpenRouter, and most others all speak OpenAI-compatible by default.

**Cons.** Anthropic doesn't speak OpenAI-compatible natively — you need LiteLLM (or hand-rolled translation) for Claude. Tool-call response shapes drift slightly between providers. No automatic retries/fallbacks. Cost tracking is on you.

**Best use.** Prototyping. If 80% of your traffic is "OpenAI-compatible providers + Ollama," skip LiteLLM and just override `base_url` per call.

### 5. CrewAI (with Ollama)

51,574 stars, MIT, very active. CrewAI's "Role + Task + Crew" abstraction sits one level above LangGraph in opinion-strength.

**Ollama confirmation.** Official docs and many community recipes show CrewAI with `llm=LLM(model="ollama/llama3.3", base_url="http://localhost:11434")`. Internally CrewAI uses LiteLLM as its model layer — so you inherit LiteLLM's provider coverage transparently.

**Trade-off.** The role-play metaphor ("You are a senior researcher...") is overhead for orchestrator/worker patterns. CrewAI shines when you genuinely have a *team* of specialists; it feels heavy for "1 orchestrator + ephemeral workers."

---

## Task C — Local model options

### Ollama

171,610 stars (huge), MIT, Go. Description on the repo today: *"Get up and running with Kimi-K2.5, GLM-5, MiniMax, DeepSeek, gpt-oss, Qwen, Gemma and other models."*

**Current go-to models for orchestration use (May 2026):**
- **Llama 3.3 70B** — solid generalist, ~40 GB VRAM Q4. Function-calling native.
- **Qwen 2.5 (and Qwen 3 series)** — Alibaba's open-weights line, strong tool-use and Chinese/English bilingual. Qwen 2.5-Coder-32B excellent for code workers.
- **DeepSeek V3 / R1 distills** — DeepSeek-R1 distilled into Qwen/Llama bases is the standard reasoning option for local. R1-Distill-Qwen-32B fits in 24 GB VRAM Q4.
- **gpt-oss** — OpenAI's open-weights release, mentioned in Ollama's description today.

**Hardware reality:**
- **M-series Mac (M3 Max 64 GB, M4 Max 128 GB)** — can run 70B models Q4 at ~10–20 tok/s, fine for orchestration where latency is gated by network/tools anyway. The 128 GB M4 Max is the sweet spot for serious local use.
- **VPS (Hostinger or otherwise)** — *almost never has a GPU at a reasonable price tier*. Running 70B on CPU is unusably slow (~1 tok/s). Two viable paths if you want local on VPS: (a) rent a GPU-equipped box (Hostinger doesn't offer this at consumer tiers — you'd go to Lambda, Vast, RunPod, etc.), or (b) skip local models on the VPS, use API providers there, and reserve Ollama for the Mac. **Strongly recommend (b).**

### vLLM

80,256 stars, Apache-2.0. High-throughput inference engine. Prefer over Ollama when:
- You're serving multiple concurrent users (vLLM's PagedAttention + continuous batching dominate here).
- You need to maximize tokens/sec per GPU dollar (production inference).
- You want to serve a model behind an OpenAI-compatible HTTP endpoint at scale.

For a *single-user personal* setup, Ollama wins on ergonomics. vLLM is the right answer if/when you outgrow that.

### LM Studio

GUI alternative to Ollama. Same OpenAI-compatible endpoint pattern. Better for users who want a chat UI alongside the API. No advantage for headless orchestrator use; use Ollama there.

---

## Task D — Recommendation

### Constraints recap

- Topology: 1 orchestrator + ephemeral workers
- Front-end: Telegram bot on Hostinger VPS
- Second brain: Markdown files, git-sync to Mac/Obsidian
- Hard constraint: model-agnostic, including local Ollama
- Use case: async research (long-running tasks)

### Top pick — **LiteLLM proxy + thin Python orchestrator (asyncio) + python-telegram-bot**

**Stack.**

1. **LiteLLM proxy** running on the VPS as `systemd` service. One YAML config registers Anthropic, OpenAI, Groq, Ollama (pointed at your Mac via Tailscale when you want local), OpenRouter as fallback. Single OpenAI-compatible endpoint exposes all of them.
2. **Orchestrator** = ~300 lines of Python with `openai` SDK pointed at `http://localhost:4000/v1`. Workers spawned as `asyncio.create_task(...)` coroutines, each calling the same proxy with a different `model=` string. Use `model="gpt-5"` for orchestrator (precision), `model="groq/llama-3.3-70b"` for fast workers (speed/cost), `model="ollama/qwen2.5"` for private workers when you Tailscale to the Mac.
3. **Telegram** via `python-telegram-bot` — webhook on the VPS, push messages back to user on worker completion. For long-running tasks, store `chat_id` + task id, fire `bot.send_message(chat_id, ...)` when results land.
4. **Second brain** = a Git repo of Markdown files on the VPS, `cron` or `inotify`-triggered `git push` to a private GitHub repo. On the Mac, Obsidian opens the same git repo via `git pull` (or use `obsidian-git` plugin for auto-sync). Workers read/write `.md` files using plain `pathlib`. The orchestrator passes file paths as task arguments, not full content (per Karpathy: "filesystem as the index").

**Why this wins for the stated constraints.**

- **Maximum model-agnosticism.** Changing models is editing one line of YAML. Want to try a new provider? Add a `model_list` entry, restart the proxy. Zero orchestrator code changes.
- **Zero lock-in.** Every component is independently replaceable. Swap LiteLLM for direct OpenAI-SDK calls (you lose Anthropic + retries but keep everything else). Swap python-telegram-bot for Discord. Swap the Markdown vault for anything else. The orchestrator is *your* code, ~300 lines.
- **Matches the topology exactly.** "1 orchestrator + ephemeral workers" *is* `asyncio.create_task` plus a `ChatCompletion` per worker. Don't reach for LangGraph state machines or CrewAI Crews for a topology this simple — that's the textbook "rewrite 50 lines as 200" anti-pattern.
- **Local Ollama works free.** Ollama exposes an OpenAI-compatible endpoint on port 11434 already; LiteLLM routes to it as just another provider. On the VPS, point to your Mac via Tailscale.
- **Long-running async.** Telegram's webhook model + asyncio is naturally async. For *very* long tasks (>1 hour), add SQLite-backed job persistence so a VPS restart doesn't lose work. (Don't reach for Temporal/Celery until you actually need them.)

### Runner-up 1 — **Pydantic AI** as the orchestrator layer (keep LiteLLM proxy underneath)

If the 300-line orchestrator starts growing tools, typed I/O, and structured tool-call validation, lift it into Pydantic AI without changing anything else. Pydantic AI's `Agent` abstraction is the smallest credible step up from raw OpenAI SDK — and crucially, it stays model-agnostic at the same level as LiteLLM. You'd typically point Pydantic AI's `OpenAIChatModel` at the LiteLLM proxy.

**Trade-off vs. top pick:** Adds a real dependency and a real abstraction. Worth it once you have ≥5 tools, structured outputs, and ≥2 worker types. Premature otherwise.

### Runner-up 2 — **Hermes Agent (turnkey)**

If the user wants to *skip building the orchestrator entirely*, Hermes Agent (154,416 stars, MIT, Nous Research) ships Telegram + Slack + Discord + WhatsApp + Signal + Email gateways, multi-provider model swap via `hermes model`, persistent memory, cron scheduling, and MCP tool integration as a single binary. Install on the VPS, point at a model, done.

**Trade-off vs. top pick:** You inherit Nous Research's opinions. Architecture is single-agent + subagent spawning, not the "1 orchestrator + ephemeral workers" graph you described. The model-agnostic story is excellent (12+ providers documented). Velocity is high but the issue backlog (4k+ issues, 5k+ PRs in 10 months) suggests review can't keep up — pin a specific release rather than tracking `main`.

### What to **skip** given these constraints

- **OpenClaw (372k stars).** Channel coverage is unmatched, but it's a *desktop-first* app with a TypeScript stack, not the lightweight VPS+Telegram service you want. Hermes is the better fit on the same axis.
- **OpenHuman (GPL-3.0).** The copyleft license is a real concern if you ever publish anything that builds on it. Rust core makes hacking harder than Python alternatives.
- **MetaGPT.** Wrong shape — software-house simulator, not personal orchestration. Slowing (4-month gap between pushes).
- **LangGraph (alone).** Overkill for ephemeral-worker topology. Reach for it only when you need durable execution + checkpoint-on-crash + human-in-loop primitives. Pydantic AI is the right runner-up before LangGraph.
- **CrewAI.** Role-play abstraction fights the orchestrator/worker pattern. CrewAI shines for team-of-specialists, not for a precision orchestrator dispatching to disposable workers.
- **PAI (Personal_AI_Infrastructure).** "Claude Code native" today — explicitly *not* model-agnostic. Steal the architectural ideas (filesystem-as-index, hook lifecycle, memory partitioned by purpose), don't adopt the runtime.

### Concrete first commits if you accept the top pick

1. `docker compose` file with: LiteLLM proxy container + your orchestrator container + (optionally) an `ollama` container if you want a local model on the VPS for prototyping.
2. `litellm-config.yaml` with 4 entries: `claude-orchestrator` → Anthropic, `fast-worker` → Groq, `cheap-worker` → OpenAI gpt-4o-mini, `private-worker` → Ollama.
3. `orchestrator.py` (~100 lines): asyncio loop, takes a Telegram message, classifies intent (one `claude-orchestrator` call returning JSON), spawns N worker coroutines (each one `chat.completions.create` call), aggregates, writes Markdown to vault, fires `bot.send_message` with the result.
4. `bot.py` (~50 lines): `python-telegram-bot` webhook handler that pushes incoming messages to the orchestrator's `asyncio.Queue`.
5. `cron`: `cd /vault && git add -A && git commit -m "auto: $(date)" && git push` every 5 min.

Everything else is iteration on top of that.

---

## Methodology notes

- **GitHub data:** raw `curl https://api.github.com/repos/...` + `jq` on 2026-05-17. No AI summarizer in the verification path. The prior agent's flag of "OpenClaw 372k stars looks hallucinated" was good epistemic hygiene but turns out to be wrong on the facts — OpenClaw genuinely ranks among GitHub's top-10 repos globally. It was created 2025-11-24, post-knowledge-cutoff for the prior agent.
- **Library features:** verified against Context7 official docs (LiteLLM `/websites/litellm_ai`, Pydantic AI `/websites/pydantic_dev_ai`). Code examples in this report are paraphrased from those docs, not invented.
- **Hardware/model claims for Ollama:** general knowledge consistent with the Ollama README description (Kimi-K2.5, GLM-5, MiniMax, DeepSeek, gpt-oss, Qwen, Gemma). Specific tok/s figures are order-of-magnitude estimates, not benchmarked here.
- **Anything I didn't verify and would not assert with confidence:** exact CrewAI internal LiteLLM version pin (claim that "CrewAI uses LiteLLM internally" is correct per CrewAI's own docs but I didn't pull the exact dependency version); Hostinger's exact GPU availability (claim "Hostinger doesn't offer GPU at consumer tiers" is based on 2025 knowledge — confirm before purchasing).
