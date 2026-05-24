"""Policy helpers for optional live agent judging.

Live judging is intentionally opt-in. The recorder can mark eligible
performance rows as pending, but the user-facing request path never calls a
judge model directly.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from typing import Any

from agentos.eval_rubrics import rubric_ids, rubrics_for_agent

_TRUE_VALUES = {"1", "true", "yes", "on"}
_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|authorization|bearer|password|passwd|private[_-]?key|secret|token)",
    re.IGNORECASE,
)
_TOKEN_VALUE_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|xox[baprs]-[A-Za-z0-9-]{8,}|gh[pousr]_[A-Za-z0-9_]{8,})"
)


@dataclass(frozen=True)
class PrivacyDecision:
    allowed: bool
    reason: str = "ok"


@dataclass(frozen=True)
class JudgeDecision:
    eligible: bool
    rubric_ids: tuple[str, ...] = ()
    reason: str = "disabled"


@dataclass(frozen=True)
class EvalLivePolicy:
    enabled: bool = False
    default_sample_rate: float = 0.0
    sample_rate_overrides: dict[str, float] | None = None
    max_attempts: int = 3
    allow_content_read: bool = False
    max_payload_chars: int = 12000

    @classmethod
    def from_env(cls) -> "EvalLivePolicy":
        overrides: dict[str, float] = {}
        for key, value in os.environ.items():
            if key.startswith("EVAL_LIVE_SAMPLE_RATE_") and key != "EVAL_LIVE_SAMPLE_RATE":
                agent = key.removeprefix("EVAL_LIVE_SAMPLE_RATE_").lower()
                overrides[agent] = _parse_float(value, 0.0)
        return cls(
            enabled=_parse_bool(os.getenv("EVAL_LIVE_JUDGE_ENABLED")),
            default_sample_rate=_parse_float(os.getenv("EVAL_LIVE_SAMPLE_RATE"), 0.0),
            sample_rate_overrides=overrides,
            max_attempts=max(1, _parse_int(os.getenv("EVAL_LIVE_MAX_ATTEMPTS"), 3)),
            allow_content_read=_parse_bool(os.getenv("EVAL_LIVE_ALLOW_CONTENT_READ")),
            max_payload_chars=max(1, _parse_int(os.getenv("EVAL_LIVE_MAX_PAYLOAD_CHARS"), 12000)),
        )

    def sample_rate_for(self, agent_id: str | None) -> float:
        overrides = self.sample_rate_overrides or {}
        normalized = _normalize_agent(agent_id)
        return min(1.0, max(0.0, overrides.get(normalized, self.default_sample_rate)))

    def should_sample(self, *, agent_id: str | None, run_id: str) -> bool:
        rate = self.sample_rate_for(agent_id)
        if rate <= 0:
            return False
        if rate >= 1:
            return True
        digest = hashlib.sha256(f"{agent_id}:{run_id}".encode()).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        return bucket < rate

    def privacy_allows(self, payload: Any) -> PrivacyDecision:
        rendered = _stable_json(payload)
        if len(rendered) > self.max_payload_chars:
            return PrivacyDecision(False, "payload_too_large")
        if _SECRET_KEY_RE.search(rendered):
            return PrivacyDecision(False, "secret_marker")
        if _TOKEN_VALUE_RE.search(rendered):
            return PrivacyDecision(False, "token_like_value")
        return PrivacyDecision(True)

    def can_read_full_content(self, agent_id: str | None) -> bool:
        return _normalize_agent(agent_id) != "ingest" or self.allow_content_read

    def judge_decision(
        self,
        *,
        agent_id: str | None,
        run_id: str,
        eval_input: dict[str, Any] | None,
        eval_data: dict[str, Any],
    ) -> JudgeDecision:
        if not self.enabled:
            return JudgeDecision(False, reason="disabled")
        rubrics = rubrics_for_agent(agent_id)
        if not rubrics:
            return JudgeDecision(False, reason="no_rubric")
        attempts = int(eval_data.get("judge_attempts") or 0)
        if attempts >= self.max_attempts:
            return JudgeDecision(False, reason="max_attempts")
        if not self.privacy_allows({"input": eval_input, "data": eval_data}).allowed:
            return JudgeDecision(False, reason="privacy")
        if not self.should_sample(agent_id=agent_id, run_id=run_id):
            return JudgeDecision(False, reason="sampled_out")
        eligible = []
        for rubric in rubrics:
            if rubric.requires_content_read and not self.can_read_full_content(agent_id):
                if not rubric.metadata_only_supported:
                    continue
            eligible.append(rubric)
        if not eligible:
            return JudgeDecision(False, reason="content_not_allowed")
        return JudgeDecision(True, rubric_ids=rubric_ids(eligible), reason="pending")


def normalize_score(value: Any) -> float | None:
    if isinstance(value, dict):
        if "passed" in value:
            return 1.0 if bool(value["passed"]) else 0.0
        if "score" in value:
            return normalize_score(value["score"])
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 1.0:
            numeric = numeric / 10.0
        return min(1.0, max(0.0, numeric))
    return None


def _parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUE_VALUES


def _parse_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None else default
    except ValueError:
        return default


def _parse_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None else default
    except ValueError:
        return default


def _normalize_agent(agent_id: str | None) -> str:
    return (agent_id or "").replace("-", "_").lower()


def _stable_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return str(value)
