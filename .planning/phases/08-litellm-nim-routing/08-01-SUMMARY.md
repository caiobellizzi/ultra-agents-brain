---
phase: "08-litellm-nim-routing"
plan: "08-01"
status: complete
date: 2026-05-22
---

# 08-01 SUMMARY — NVIDIA NIM via LiteLLM + per-agent routing

## Outcome

5-tier LiteLLM matrix replaces undifferentiated Gemma-only routing.
NVIDIA NIM wired as third cloud backend behind `NVIDIA_NIM_API_KEY`.
Research agent now consumes a dedicated `research-worker` tier.
48/48 eval suite stays green.

## Commits

1. `feat(litellm)` — wire NIM tiers + capability-routed fallbacks in `deploy/litellm/config.yaml`
2. `feat(agentos)` — add `research-worker` tier in `agentos/model.py`; switch `agentos/agents/research.py` (factory + module singleton)
3. `feat(env)` — `.env.example` adds `NVIDIA_NIM_API_KEY`, 5× `LITELLM_*_MODEL` overrides, pins `LITELLM_IMAGE=ghcr.io/berriai/litellm:main-stable`
4. `docs(readme)` — README env-vars table + LiteLLM architecture bullet updated per readme-sync rule

## Verification

| Step | Result |
|---|---|
| `python3 -c 'yaml.safe_load(...)'` on config.yaml | ✅ parses |
| `docker compose -f deploy/docker-compose.yml config` | ✅ renders cleanly |
| `pytest evals/` | ✅ 48/48 passed in 0.02s (local-stub baselines unchanged) |
| Live curl against 6 NIM aliases | ⏭ deferred — local env has no `NVIDIA_NIM_API_KEY` set; must be exercised on VPS after deploy |
| Supervisor smoke test on VPS `:7000/teams/supervisor/runs` | ⏭ deferred — requires VPS deploy + NIM key |
| Manual `NVIDIA_NIM_API_KEY` invalidation → cloud-sonnet failover | ⏭ deferred — same |

## Deferred / follow-up

- **Operator action**: set `NVIDIA_NIM_API_KEY` on the VPS `.env`, restart the LiteLLM container, then curl each of the 6 NIM aliases at `127.0.0.1:4000/v1/chat/completions` to confirm 200s.
- **LiteLLM #23970**: pinned to `main-stable` (rolling) rather than a numeric release. Operator should verify the rolling tag contains the `nvidia_nim/` prefix fix when deploying; if not, bump to a known-good numeric tag.
- **Cost cap**: `DAILY_COST_CAP_USD` can drop once NIM routing is validated in production (NIM is free at 40 RPM/model).

## Must-haves audit

| Truth | Status |
|---|---|
| 5 tiers resolve to distinct, intentional model choices | ✅ |
| NIM wired through LiteLLM with `NVIDIA_NIM_API_KEY` | ✅ |
| `research-worker` exists in `model.py` and consumed by `research.py` | ✅ |
| `private-worker` and `cheap-worker` strictly local | ✅ no NIM/cloud fallbacks |
| 48-test eval suite stays green | ✅ 48/48 |

| Artifact | Status |
|---|---|
| `deploy/litellm/config.yaml` registers 8 NIM-touching aliases + rewritten fallbacks | ✅ |
| `.env.example` documents `NVIDIA_NIM_API_KEY` + tier overrides | ✅ |
| `LITELLM_IMAGE` pinned in `.env.example` | ✅ `main-stable` |
| README sync | ✅ env table + architecture bullet |
