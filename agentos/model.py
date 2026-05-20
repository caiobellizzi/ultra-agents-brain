"""Shared model factory — all agents route through LiteLLM proxy on :4000."""

from __future__ import annotations

import os

from agno.models.openai import OpenAIChat

LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1")
LITELLM_API_KEY = os.environ["LITELLM_MASTER_KEY"]


_TIER_ENV: dict[str, str] = {
    "cheap-worker": "LITELLM_CHEAP_MODEL",
    "default-worker": "LITELLM_DEFAULT_MODEL",
    "orchestrator": "LITELLM_ORCHESTRATOR_MODEL",
    "private-worker": "LITELLM_PRIVATE_MODEL",
}


def chat_model(tier: str = "cheap-worker") -> OpenAIChat:
    """Return an OpenAIChat configured for the LiteLLM proxy.

    Tiers:
      cheap-worker    — fast/cheap model (env: LITELLM_CHEAP_MODEL)
      default-worker  — balanced capability (env: LITELLM_DEFAULT_MODEL)
      orchestrator    — most capable (env: LITELLM_ORCHESTRATOR_MODEL)
      private-worker  — local LM Studio only (env: LITELLM_PRIVATE_MODEL)

    For each named tier the resolved model id is read from the corresponding
    env var, falling back to the tier name itself (so existing deployments that
    already set up LiteLLM groups by these names continue to work unchanged).
    Arbitrary tier strings are passed through directly.
    """
    env_var = _TIER_ENV.get(tier)
    model_id = os.environ.get(env_var, tier) if env_var else tier
    return OpenAIChat(id=model_id, base_url=LITELLM_BASE_URL, api_key=LITELLM_API_KEY)
