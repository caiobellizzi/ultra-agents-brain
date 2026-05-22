---
phase: "09-litellm-provider-label"
plan: "09-01"
status: complete
date: 2026-05-22
---

# 09-01 SUMMARY — relabel Agno dashboard provider to LiteLLM

## Outcome

Agno's `OpenAIChat` is subclassed as `LiteLLMChat` in `agentos/model.py`
with `name = "LiteLLM"` and `provider = "LiteLLM"`. The dashboard at
os.agno.com now reports every agent as `provider: LiteLLM` instead of
the misleading `OpenAI`. Tier id (`research-worker`, `orchestrator`, …)
on the model chip is unchanged.

## Surprise: dataclass inheritance

First attempt declared the subclass without `@dataclass`. Test showed:
- `type(m).__name__` was `LiteLLMChat` ✅
- but `m.name == "OpenAIChat"` and `m.provider == "OpenAI"` ❌

Both `Model` and `OpenAIChat` are `@dataclass`. Without redecorating the
subclass, the parent's `__init__` runs and resets the field defaults to
their parent values. Fix: decorate `LiteLLMChat` with `@dataclass` so
the new defaults are picked up. Documented in the class docstring.

## Commits

1. `refactor(agentos)` — add `@dataclass class LiteLLMChat(OpenAIChat)` with `name`/`provider` overrides, switch `chat_model()` factory
2. `docs(readme)` — note dashboard label change in LiteLLM architecture bullet

## Verification

| Step | Result |
|---|---|
| `pytest evals/` (local) | ✅ 48/48 |
| `scp` + `systemctl restart uab-brain` on VPS | ✅ active |
| `curl /agents/research` model dict | ✅ `{"name":"LiteLLM","model":"research-worker","provider":"LiteLLM"}` |
| End-to-end smoke: `POST /agents/chat/runs` | ✅ HTTP 200, content `pong` |
| Visual confirmation on os.agno.com | ⏭ operator action (refresh dashboard) |

## Must-haves audit

| Truth | Status |
|---|---|
| Dashboard shows `provider: LiteLLM` and `name: LiteLLM` | ✅ verified via `/agents/research` response on VPS |
| Tier id unchanged on dashboard | ✅ `model: "research-worker"` preserved |
| 48-test eval suite stays green | ✅ |
| Live agent call still succeeds | ✅ chat agent returned `pong` |
