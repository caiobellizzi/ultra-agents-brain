# Plan: NVIDIA NIM via LiteLLM + per-agent model routing

## Context

`ultra-agents-brain` declares a 4-tier LiteLLM routing architecture in `agentos/model.py:1-37` and wires it into 6 agents (chat, query, research, ingest, curator, supervisor team). The plumbing exists but is **undifferentiated**: all four tiers in `deploy/litellm/config.yaml` currently resolve to the same local `google/gemma-4-e4b` served by LM Studio. Existing cloud fallbacks are `cloud-sonnet` (Anthropic) and `cloud-groq` (Groq Llama 3.3 70B).

This plan adds **NVIDIA NIM** (build.nvidia.com hosted endpoint) as a third cloud backend through LiteLLM, then differentiates each tier so the supervisor, the research agent, and the vault agents each run on a model genuinely suited to their workload. NIM is permanently free at 40 RPM per model (no expiry, no card) — enough for typical personal use across multiple flagship reasoning models (DeepSeek V4 Pro, GLM-5.1, Llama 3.3 70B, Mistral Large 2). Driver: "use top-brand LLMs for free via proxy" + "best model for each agent."

## Decisions (grilling outcome)

| # | Decision | Resolution |
|---|---|---|
| Q1 | NIM privacy posture | **Equivalent to Anthropic/Groq.** NIM can serve any non-private tier; `private-worker` stays strictly local. |
| Q2 | Serving order | **Capability-routed mix.** Orchestrator/research = NIM-first; default = local-first w/ NIM fallback; cheap & private = local-only. |
| Q3 | Routing granularity | **Add `research-worker` tier** (5 total). Supervisor and research diverge; chat/query/ingest stay on `default-worker`. |
| Q4a | Orchestrator model | **DeepSeek V4 Pro primary + GLM-5.1 failover.** Both reasoning models, dual vendor, 80 RPM headroom. |
| Q5 | Research-worker model | **DeepSeek V4 Flash primary + Llama 3.1 405B failover.** 1M context for multi-source aggregation. |
| Q6 | Default-worker NIM fallback | **Llama 3.3 70B + Mistral Large 2.** NIM's most stable FC models for graceful degradation. |
| Q7 | Last-resort | Orchestrator/research → `cloud-sonnet`. Default → `cloud-groq`. Cheap & private → fail loudly (no cloud). |
| Q8 | Cheap-worker | **100% local, no NIM.** Curator's batch RSS workload would saturate 40 RPM. |
| Q9 | Rollout | **Big bang** — single PR, one eval run. |

## Final architecture

### Tier map

| Tier | Consumed by | Primary | Within-tier failover | Last-resort | Privacy |
|---|---|---|---|---|---|
| `orchestrator` | supervisor team | NIM `deepseek-ai/deepseek-v4-pro` (thinking on) | NIM `z-ai/glm5.1` (thinking on) | `cloud-sonnet` (Anthropic) | Cloud-allowed |
| `research-worker` *(new)* | research agent | NIM `deepseek-ai/deepseek-v4-flash` (thinking on, 1M ctx) | NIM `meta/llama-3.1-405b-instruct` | `cloud-sonnet` | Cloud-allowed |
| `default-worker` | chat, query, ingest | **Local** LM Studio (Gemma 4 e4b) | NIM `meta/llama-3.3-70b-instruct` → NIM `mistralai/mistral-2-large-instruct` | `cloud-groq` | Cloud-allowed |
| `cheap-worker` | curator | **Local** LM Studio (Gemma 4 e4b) | — | **fail loudly** | Cloud-allowed (unused) |
| `private-worker` | EVAL_JUDGE_TIER, future sensitive | **Local** LM Studio (Gemma 4 e4b) | — | **fail loudly** | Local-only by contract |

### Effective NIM RPM budget

- orchestrator: 40 (DeepSeek V4 Pro) + 40 (GLM-5.1) = **80 RPM**
- research-worker: 40 (V4 Flash) + 40 (Llama 3.1 405B) = **80 RPM**
- default-worker NIM fallback: 40 (Llama 3.3 70B) + 40 (Mistral 2) = **80 RPM**
- **Total NIM headroom: 240 RPM** across non-overlapping model IDs.

## Files to modify

### 1. `deploy/litellm/config.yaml` — register NIM aliases + rewire fallbacks

**Naming clash to resolve first.** Current config has `model_name: orchestrator` pointing at local Gemma. We want `orchestrator` to be NIM-first. Two options:

- **Rename the local Gemma fallback aliases** to `*-local` (e.g., `orchestrator-local`) and make the bare alias names point at NIM. Clean but renames 4 aliases.
- **Replace the existing `orchestrator` entry directly** so the alias now resolves to DeepSeek V4 Pro at the proxy level. Cleanest from the agent's perspective (no code changes), but loses the local fallback as a named alias.

**Recommended: replace `orchestrator` directly, add NIM entries for `research-worker` (new) and `default-worker-nim*` (new), and introduce a new `*-local` entry only where we still need it (chained as a last-resort fallback inside the tier).**

Concretely, after the edit the `model_list` shape is:

```yaml
model_list:
  # ---- Orchestrator tier (supervisor team — NIM-first reasoning) ----
  - model_name: orchestrator                  # REPLACE existing entry
    litellm_params:
      model: nvidia_nim/deepseek-ai/deepseek-v4-pro
      api_key: os.environ/NVIDIA_NIM_API_KEY
      timeout: 600
      max_retries: 1
      extra_body:
        chat_template_kwargs:
          thinking: true        # DeepSeek thinking mode
    model_info:
      mode: chat                # required; do NOT add `tier` (LiteLLM 1.85 silently breaks on it — see memory 19751)

  - model_name: orchestrator-failover         # NEW
    litellm_params:
      model: nvidia_nim/z-ai/glm5.1
      api_key: os.environ/NVIDIA_NIM_API_KEY
      timeout: 600
      max_retries: 1
      extra_body:
        chat_template_kwargs:
          enable_thinking: true # GLM thinking mode (default but explicit)
    model_info:
      mode: chat

  # ---- Research-worker tier (research agent — 1M context aggregation) ----
  - model_name: research-worker               # NEW
    litellm_params:
      model: nvidia_nim/deepseek-ai/deepseek-v4-flash
      api_key: os.environ/NVIDIA_NIM_API_KEY
      timeout: 600
      max_retries: 1
      extra_body:
        chat_template_kwargs:
          thinking: true
    model_info:
      mode: chat

  - model_name: research-worker-failover      # NEW
    litellm_params:
      model: nvidia_nim/meta/llama-3.1-405b-instruct
      api_key: os.environ/NVIDIA_NIM_API_KEY
      timeout: 600
      max_retries: 1
    model_info:
      mode: chat

  # ---- Default-worker (LOCAL-first; keep existing local entry as primary) ----
  - model_name: default-worker                # KEEP existing local Gemma entry untouched (primary)
    litellm_params:
      model: openai/google/gemma-4-e4b
      api_base: os.environ/LM_STUDIO_API_BASE
      api_key: os.environ/LM_STUDIO_API_KEY
      timeout: 300
      max_retries: 1
    model_info:
      mode: chat

  - model_name: default-worker-nim            # NEW (fallback path after local fails)
    litellm_params:
      model: nvidia_nim/meta/llama-3.3-70b-instruct
      api_key: os.environ/NVIDIA_NIM_API_KEY
      timeout: 180
      max_retries: 1
    model_info:
      mode: chat

  - model_name: default-worker-nim-failover   # NEW
    litellm_params:
      model: nvidia_nim/mistralai/mistral-2-large-instruct
      api_key: os.environ/NVIDIA_NIM_API_KEY
      timeout: 180
      max_retries: 1
    model_info:
      mode: chat

  # ---- Cheap-worker (LOCAL only — KEEP existing entry, no NIM) ----
  - model_name: cheap-worker                  # UNCHANGED
    # ...existing LM Studio entry...

  # ---- Private-worker (LOCAL only — KEEP existing entry, no NIM) ----
  - model_name: private-worker                # UNCHANGED
    # ...existing LM Studio entry...

  # ---- Cloud fallbacks (UNCHANGED) ----
  - model_name: cloud-sonnet                  # UNCHANGED
  - model_name: cloud-groq                    # UNCHANGED
```

**Rewrite `litellm_settings.fallbacks` and bump `request_timeout`** (replace existing block):

```yaml
litellm_settings:
  request_timeout: 600          # bumped from 300; thinking-mode generations can run long
  num_retries: 1
  fallbacks:
    - orchestrator: ["orchestrator-failover", "cloud-sonnet"]
    - orchestrator-failover: ["cloud-sonnet"]
    - research-worker: ["research-worker-failover", "cloud-sonnet"]
    - research-worker-failover: ["cloud-sonnet"]
    - default-worker: ["default-worker-nim", "default-worker-nim-failover", "cloud-groq"]
    - default-worker-nim: ["default-worker-nim-failover", "cloud-groq"]
    - default-worker-nim-failover: ["cloud-groq"]
    # cheap-worker and private-worker have no fallback — fail loudly (preserve existing private-worker → cheap-worker chain if you want a softer floor)
  context_window_fallbacks:
    - default-worker: ["research-worker"]   # if vault Q&A overflows 128K, route to 1M ctx
    - orchestrator: ["research-worker"]     # supervisor with huge context → V4 Flash
```

**Do NOT add `model_info.tier`** to any new entry — LiteLLM 1.85 silently breaks all deployments on invalid `model_info.tier` values (memory 19751). Keep `model_info` limited to `mode: chat` (matches the existing entries' shape).

### 2. `agentos/model.py:1-37` — add `research-worker` to `_TIER_ENV`

Add one row to the dict:

```python
_TIER_ENV = {
    "cheap-worker": "LITELLM_CHEAP_MODEL",
    "default-worker": "LITELLM_DEFAULT_MODEL",
    "orchestrator": "LITELLM_ORCHESTRATOR_MODEL",
    "research-worker": "LITELLM_RESEARCH_MODEL",    # NEW
    "private-worker": "LITELLM_PRIVATE_MODEL",
}
```

No other code changes — `chat_model("research-worker")` will resolve via the same generic path.

### 3. `agentos/agents/research.py` — switch research agent's tier

- `research.py:25` (docstring): update `"""Create a fully-configured research agent (orchestrator tier)."""` → `"""Create a fully-configured research agent (research-worker tier)."""`.
- `research.py:28` (factory): change `chat_model("orchestrator")` → `chat_model("research-worker")`.
- `research.py:59` (module-level singleton): change `chat_model("default-worker")` → `chat_model("research-worker")` so both code paths converge on the new tier.

### 4. `.env.example` — add NVIDIA_NIM_API_KEY and document tier override vars

**Drift correction:** The current `.env.example` does **not** contain any `LITELLM_*_MODEL` env vars. They're consumed by `agentos/model.py:13-18` but undocumented. `chat_model()` falls back to the tier name if the env var is unset, so they're optional — not adding them is not a bug, but they should be in `.env.example` for discoverability.

Append in the model-config section (between `OPENROUTER_API_KEY=` and the LM Studio block):

```bash
# NVIDIA NIM (build.nvidia.com hosted endpoint, free at 40 RPM/model)
# Get a key at https://build.nvidia.com → Settings → API Keys (format: nvapi-...)
NVIDIA_NIM_API_KEY=

# Optional tier overrides — when unset, the tier name itself is used as the
# LiteLLM alias. Override these only when you want a tier to resolve to a
# different LiteLLM alias than its name (e.g. blue/green model swaps).
LITELLM_CHEAP_MODEL=cheap-worker
LITELLM_DEFAULT_MODEL=default-worker
LITELLM_ORCHESTRATOR_MODEL=orchestrator
LITELLM_RESEARCH_MODEL=research-worker
LITELLM_PRIVATE_MODEL=private-worker
```

### 5. `deploy/docker-compose.yml` + `.env.example` — pin LiteLLM version

Current state:
- `.env.example:8` → `LITELLM_IMAGE=ghcr.io/berriai/litellm:main-latest` (unpinned, rolling tag).
- `deploy/docker-compose.yml:3` default → `litellm/litellm:latest` (different unpinned tag; only used if env var missing).

Pin **`.env.example`** to a specific tag that includes the fix for LiteLLM issue **#23970** (March 2026 — `nvidia_nim/` provider prefix dropped on websearch-interception follow-up, which affects routes containing a slash in the model id like `z-ai/glm5.1`). Concretely:

```bash
LITELLM_IMAGE=ghcr.io/berriai/litellm:v1.60.0   # or latest verified-good tag
```

Verify the chosen tag's release notes mention the `nvidia_nim` prefix fix before pinning. The compose-file default (`litellm/litellm:latest`) can be left as-is — env wins at runtime, and pinning the env is the operationally relevant change. If the `z-ai/glm5.1` route still misbehaves on the verified tag, the documented workaround is to disable `websearch_interception` in the LiteLLM config.

Note: LiteLLM runs with `network_mode: host` (memory 19545 — switched to host mode so the container can reach LM Studio on `127.0.0.1:1234`). Do not change the network mode — NIM is HTTPS-outbound and works fine in host mode.

### 6. README sync

Per `~/.claude/rules/readme-sync.md`, the same PR must update `README.md` with:
- New env var `NVIDIA_NIM_API_KEY` in the env-vars table.
- New `research-worker` tier in any tier documentation.
- Note that NIM is treated equivalent to Anthropic/Groq for privacy purposes.

## Existing functions / utilities being reused

- `agentos/model.py:chat_model()` — single factory, no signature change. Adding a new tier is a one-line dict entry.
- `OpenAIChat(id, base_url, api_key)` from `agno` — already wraps OpenAI-compatible endpoints; NIM speaks the same protocol through LiteLLM.
- LiteLLM `fallbacks` and `context_window_fallbacks` — already in use for `cloud-sonnet` and `cloud-groq`; extending them is the same shape of edit.
- `pytest evals/` — 48 tests already validate end-to-end behavior on the VPS (baselines stamped `a0bf35c` 2026-05-21). This is the verification harness for the rollout.

## Verification (end-to-end)

Run these in order after the PR is staged:

1. **Static config syntax**:
   ```bash
   docker compose -f deploy/docker-compose.yml config
   ```
   Confirms the rewritten `config.yaml` parses cleanly.

2. **NIM connectivity** (one curl per primary NIM model, after `docker compose up -d`):
   ```bash
   for alias in orchestrator orchestrator-failover research-worker research-worker-failover default-worker-nim default-worker-nim-failover; do
     curl -sS -X POST http://127.0.0.1:4000/v1/chat/completions \
       -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
       -H "Content-Type: application/json" \
       -d "{\"model\":\"$alias\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":8}" \
       | jq -r --arg a "$alias" '"\($a): \(.choices[0].message.content // .error.message)"'
   done
   ```
   All 6 should return a short completion (not an auth or 404 error).

3. **Eval suite** — must stay green:
   ```bash
   pytest evals/
   ```
   Expect 48/48 pass. Any new failure must be triaged before merge.

4. **Supervisor smoke test** (matches the validated path from memory S574 — VPS uses port 7000; local Mac dev uses 7001 per memory 19734):
   ```bash
   # VPS:
   curl -sS -X POST http://127.0.0.1:7000/teams/supervisor/runs \
     -H "Content-Type: application/json" \
     -d '{"message":"List my recent vault notes."}' \
     | jq -r '.status, .content[:200]'
   ```
   Expect `COMPLETED` and a reasonable supervisor response that names real vault notes (proves end-to-end NIM-orchestrator routing). On local Mac dev replace `:7000` with `:7001`.

5. **Cost cap sanity** — confirm `DAILY_COST_CAP_USD` still tracks correctly. Since NIM is free, expect cost to drop relative to the previous Anthropic-fallback frequency.

6. **Fallback exercise** (optional, manual): temporarily set an invalid `NVIDIA_NIM_API_KEY`, send one supervisor request, confirm it falls through to `cloud-sonnet` and the response is still coherent. Restore the key after.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| LiteLLM #23970 affects `nvidia_nim/z-ai/glm5.1` routing | Pin `LITELLM_IMAGE` to a known-good tag (see file #5). Smoke-test the GLM alias in verification step 2 before merging. |
| DeepSeek thinking mode injects `<think>` blocks into `content` (Agno may not strip) | Verification step 3 (eval suite) will catch any output-shape regression. If broken: either move the strip to a post-processor in `agentos/model.py`, or disable thinking via `chat_template_kwargs.thinking: false`. |
| 40 RPM ceiling hit during burst (multi-tool supervisor + research run) | Failover chain handles this gracefully (80 RPM/tier + cloud-sonnet last resort). Monitor LiteLLM `/metrics` for `429` counters. |
| NVIDIA changes hosted-endpoint policy or deprecates a model | DeepSeek `r1` was already deprecated; same could happen to `v4-pro` or `glm5.1`. Failover chain absorbs single-model deprecation. Quarterly review of NIM model catalog. |
| Privacy: NIM has no published "no training" guarantee for hosted endpoint | Accepted per Q1 (equivalent to Anthropic/Groq). `private-worker` stays strictly local, preserving an escape hatch for genuinely sensitive workloads. |
| Big-bang regression hard to attribute | Mitigated by running every step of verification in order; if eval suite regresses, revert the single PR. |
