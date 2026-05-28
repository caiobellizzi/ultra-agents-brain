"""Stdlib-only LiteLLM proxy wrapper.

Model aliases (configured in LiteLLM config):
  orchestrator   — Tier A (high-capability)
  default-worker — Tier B (balanced)
  cheap-worker   — Tier C (cost-optimised)
  private-worker — Tier D (on-prem / private)
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

_BASE_URL = os.getenv("LITELLM_BASE_URL", "http://127.0.0.1:4000/v1")
_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "")


def complete(
    prompt: str,
    *,
    model: str = "default-worker",
    system: str = "",
    max_tokens: int = 1024,
    temperature: float = 0.2,
) -> str:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = json.dumps(
        {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if _MASTER_KEY:
        headers["Authorization"] = f"Bearer {_MASTER_KEY}"
    req = urllib.request.Request(
        f"{_BASE_URL.rstrip('/')}/chat/completions",
        data=payload,
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    choices = data.get("choices")
    if not choices:
        raise ValueError(f"LiteLLM returned no choices; full response: {data}")
    return choices[0]["message"]["content"]
