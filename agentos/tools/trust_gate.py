"""Trust gate decorator — wraps an Agno tool with risk classification + HITL.

Routes:
  - LOW (auto)     → runs unchanged
  - MEDIUM (approval) → raises AgnoHITLRequired so Agno pauses for approval
  - MEDIUM (private-worker) → routed off-cloud (placeholder; refuse for now)
  - HIGH (refuse)  → raises PermissionError; never executes

Approval flow is surfaced by the channel adapter (Telegram inline buttons),
not by the agent itself. Agno's HITL is signalled by raising the agno-native
HumanInLoopRequired exception if present; otherwise we re-raise PermissionError
so the orchestrating agent can surface the approval prompt to the user.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from ultra_brain.trust import approval_prompt, classify_action

try:
    from agno.exceptions import HumanInLoopRequired  # type: ignore
except Exception:  # pragma: no cover — fall back if Agno renames the exception
    class HumanInLoopRequired(Exception):  # type: ignore[no-redef]
        pass


def trust_gate(action_description: str, *, target_path_arg: str | None = None) -> Callable:
    """Decorator factory.

    Args:
        action_description: Static description of what the tool does
            (e.g., "write note to vault").
        target_path_arg: Optional name of a kwarg whose value should be passed
            as `target_path` to `classify_action`.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            target = ""
            if target_path_arg and target_path_arg in kwargs:
                target = str(kwargs[target_path_arg])
            decision = classify_action(action_description, target_path=target)
            if not decision.allowed:
                raise PermissionError(f"Action refused: {decision.reason}")
            if decision.needs_approval:
                raise HumanInLoopRequired(approval_prompt(action_description, decision))
            return fn(*args, **kwargs)

        return wrapped

    return decorator
