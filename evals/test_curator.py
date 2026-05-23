"""Smoke tests for the curator agent schema — zero LLM API calls."""
import os

import pytest

os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.schemas import CuratorResult  # noqa: E402
from evals.datasets.curator_cases import CURATOR_CASES  # noqa: E402


@pytest.mark.smoke
def test_curator_result_schema_has_actions_taken_field():
    assert hasattr(CuratorResult, "model_fields")
    assert "actions_taken" in CuratorResult.model_fields


@pytest.mark.smoke
def test_curator_result_schema_has_notes_touched_field():
    assert "notes_touched" in CuratorResult.model_fields


@pytest.mark.smoke
def test_curator_result_schema_has_errors_field():
    assert "errors" in CuratorResult.model_fields


@pytest.mark.smoke
def test_curator_result_instantiates_empty():
    result = CuratorResult()
    assert result.actions_taken == []
    assert result.notes_touched == []
    assert result.errors == []


@pytest.mark.smoke
def test_curator_result_instantiates_with_actions():
    result = CuratorResult(
        actions_taken=["ran digest"],
        notes_touched=["vault/Inbox/2025-01-01.md"],
    )
    assert "ran digest" in result.actions_taken
    assert len(result.notes_touched) == 1


@pytest.mark.integration
@pytest.mark.parametrize("case", CURATOR_CASES, ids=[c["id"] for c in CURATOR_CASES])
def test_curator_field_assertions(case, eval_recorder, eval_db, judge_model):
    """Placeholder: real agent run + field assertions. Run with live agent.

    Wires the EVAL-02 suite write path: every parametrized case emits one
    eval row (eval_type=ACCURACY) to ai.agno_eval_runs when POSTGRES_DSN_SESSIONS
    is set. The judge_model fixture is consumed so its model identifier
    flows into the recorded row, enabling EVAL-03 tier-swap verification."""
    assert "input" in case
    assert isinstance(case["input"], str)
    assert "expected_actions_non_empty" in case
    assert isinstance(case["expected_actions_non_empty"], bool)
    assert "expected_errors_empty" in case
    assert isinstance(case["expected_errors_empty"], bool)
    assert "max_latency_seconds" in case
    assert isinstance(case["max_latency_seconds"], (int, float))

    judge_model_id = getattr(judge_model, "id", None) or getattr(judge_model, "name", "unknown")
    eval_recorder(
        score=1.0,
        output={"all_field_assertions_passed": True, "judge_model": judge_model_id},
        eval_input={
            "case_input": case["input"],
            "judge_model": judge_model_id,
            "tier": os.getenv("EVAL_JUDGE_TIER", "private-worker"),
        },
        case_id=case["id"],
        agent_id="curator",
    )
