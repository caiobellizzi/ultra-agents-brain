"""Cost ledger integration for AgentOS.

Registers a litellm success_callback so every LLM call (regardless of which
agent triggers it) appends a row to the vault's _system/cost-ledger.md.

Import this module once at app startup — the side-effect of registering the
callback is the integration point.
"""

from __future__ import annotations

import os
from pathlib import Path

import litellm

from ultra_brain.cost import CostLedger

VAULT_ROOT = Path(os.environ.get("VAULT_ROOT", "/srv/second-brain"))
_ledger = CostLedger(VAULT_ROOT / "_system" / "cost-ledger.md")


def _record_cost(kwargs: dict, completion_response: object, start_time: object, end_time: object) -> None:
    """litellm success_callback signature."""
    try:
        _ledger.ensure()
        usage = getattr(completion_response, "usage", None)
        cost = getattr(completion_response, "_hidden_params", {}).get("response_cost", 0.0) or 0.0
        model = getattr(completion_response, "model", kwargs.get("model", "unknown"))
        scope = kwargs.get("metadata", {}).get("agent_id", "agentos")
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        notes = f"prompt={prompt_tokens} completion={completion_tokens}"
        _ledger.record(scope=scope, operation="chat", model=model, cost_usd=cost, notes=notes)
    except Exception:
        pass  # never crash the agent for a ledger write failure


litellm.success_callback = [*litellm.success_callback, _record_cost]
