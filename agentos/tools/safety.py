"""Thin pre-check helper for high-risk / private-content refusals.

Replaces the refusal logic that used to live in trust_gate. Called at the top of
_ingest_to_vault_impl and _research_topic_impl before doing any real work.
PermissionError surfaces as a tool error to the LLM, which is the correct signal
for a policy refusal.
"""

from __future__ import annotations

from ultra_brain.trust import classify_action


def assert_safe(description: str, target: str = "") -> None:
    """Raise PermissionError if the action is high-risk or private-content refused.

    Args:
        description: Human-readable description of the action (passed to classify_action).
        target: Optional target path or resource (passed as target_path).

    Raises:
        PermissionError: If the action is not allowed by policy.
    """
    decision = classify_action(description, target_path=target)
    if not decision.allowed:
        raise PermissionError(f"Action refused: {decision.reason}")
