"""Smoke tests for the curator agent schema — zero LLM API calls."""
import os

import pytest

os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.schemas import CuratorResult  # noqa: E402


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
