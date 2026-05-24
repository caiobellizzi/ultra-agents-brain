"""Shared live-eval rubrics for optional agent-as-judge rows."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class EvalRubric:
    rubric_id: str
    agent_id: str
    criteria: str
    scoring_strategy: str
    threshold: float
    requires_content_read: bool = False
    metadata_only_supported: bool = True


LIVE_RUBRICS: tuple[EvalRubric, ...] = (
    EvalRubric(
        rubric_id="chat-helpfulness-v1",
        agent_id="chat",
        criteria=(
            "Judge whether the chat response is helpful, directly answers the "
            "user, avoids fabricated vault facts, and preserves an appropriate "
            "tone for a personal knowledge assistant."
        ),
        scoring_strategy="binary",
        threshold=1.0,
    ),
    EvalRubric(
        rubric_id="query-groundedness-v1",
        agent_id="query",
        criteria=(
            "Judge groundedness against the structured citation objects and "
            "answer content. Do not reward visible markdown citation tokens; "
            "the response must be supported by the citation data structure."
        ),
        scoring_strategy="numeric",
        threshold=0.7,
    ),
    EvalRubric(
        rubric_id="ingest-fidelity-v1",
        agent_id="ingest",
        criteria=(
            "Judge whether the ingest result preserves the source meaning, "
            "chooses a sensible note path, and avoids leaking private source "
            "content unless full-content judging is explicitly allowed."
        ),
        scoring_strategy="numeric",
        threshold=0.7,
        requires_content_read=True,
        metadata_only_supported=True,
    ),
)


def rubrics_for_agent(agent_id: str | None) -> tuple[EvalRubric, ...]:
    if not agent_id:
        return ()
    return tuple(rubric for rubric in LIVE_RUBRICS if rubric.agent_id == agent_id)


def rubric_by_id(rubric_id: str) -> EvalRubric | None:
    for rubric in LIVE_RUBRICS:
        if rubric.rubric_id == rubric_id:
            return rubric
    return None


def rubric_ids(rubrics: Iterable[EvalRubric]) -> tuple[str, ...]:
    return tuple(rubric.rubric_id for rubric in rubrics)
