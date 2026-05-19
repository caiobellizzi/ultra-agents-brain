"""Trust gates and privacy routing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .markdown import strip_private_blocks


LOW = "low"
MEDIUM = "medium"
HIGH = "high"

HIGH_RISK_RE = re.compile(
    r"\b(rm\s+-rf|delete\s+repo|drop\s+database|execute\s+code|run\s+shell|exfiltrat|credential|api\s+key|private\s+key)\b",
    re.IGNORECASE,
)
MEDIUM_RISK_RE = re.compile(r"\b(write|modify|archive|publish|push|commit|send|email|telegram)\b", re.IGNORECASE)


@dataclass(frozen=True)
class TrustDecision:
    risk: str
    allowed: bool
    needs_approval: bool
    route: str
    reason: str
    sanitized_text: str


def classify_action(description: str, *, target_path: str = "", private_worker_available: bool = False) -> TrustDecision:
    combined = f"{description} {target_path}".strip()
    has_private = "<private>" in combined.lower()
    sanitized = strip_private_blocks(description)
    if HIGH_RISK_RE.search(combined):
        return TrustDecision(HIGH, False, False, "refuse", "high-risk action is forbidden by policy", sanitized)
    if has_private and not private_worker_available:
        return TrustDecision(MEDIUM, False, False, "refuse", "private content requires private-worker routing", sanitized)
    if has_private:
        return TrustDecision(MEDIUM, True, True, "private-worker", "private content routed away from cloud LLMs", sanitized)
    if MEDIUM_RISK_RE.search(combined) or target_path.startswith(("01-Areas", "_system", "03-Archives")):
        return TrustDecision(MEDIUM, True, True, "approval", "medium-risk write requires Telegram approval", sanitized)
    return TrustDecision(LOW, True, False, "auto", "low-risk action may run automatically", sanitized)


def approval_prompt(action: str, decision: TrustDecision, *, cost_estimate: float = 0.0, telos_reasoning: str = "") -> str:
    lines = [
        "Approval required",
        f"Action: {decision.sanitized_text or action}",
        f"Risk: {decision.risk}",
        f"Route: {decision.route}",
        f"Cost estimate: ${cost_estimate:.4f}",
        f"Reason: {decision.reason}",
    ]
    if telos_reasoning:
        lines.append(f"TELOS: {telos_reasoning}")
    lines.append("Reply /approve to proceed or /deny to cancel.")
    return "\n".join(lines)
