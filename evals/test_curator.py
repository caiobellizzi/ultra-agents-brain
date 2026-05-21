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
def test_curator_field_assertions(case):
    """Placeholder: real agent run + field assertions. Run with live agent."""
    assert "input" in case
    assert isinstance(case["input"], str)
    assert "expected_actions_non_empty" in case
    assert isinstance(case["expected_actions_non_empty"], bool)
    assert "expected_errors_empty" in case
    assert isinstance(case["expected_errors_empty"], bool)
    assert "max_latency_seconds" in case
    assert isinstance(case["max_latency_seconds"], (int, float))
