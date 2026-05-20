"""Shared model factory — all agents route through LiteLLM proxy on :4000."""

from __future__ import annotations

import os

from agno.models.openai import OpenAIChat

LITELLM_BASE_URL = os.environ.get("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1")
LITELLM_API_KEY = os.environ["LITELLM_MASTER_KEY"]


def chat_model(tier: str = "cheap-worker") -> OpenAIChat:
    """Return an OpenAIChat configured for the LiteLLM proxy.

    Args:
        tier: LiteLLM model group name (`cheap-worker`, `smart-worker`, etc.).
    """
    return OpenAIChat(id=tier, base_url=LITELLM_BASE_URL, api_key=LITELLM_API_KEY)
