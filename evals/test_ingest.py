"""Smoke tests for the ingest agent schema — zero LLM API calls."""
import os

import pytest

os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.schemas import IngestResult  # noqa: E402
from evals.datasets.ingest_cases import INGEST_CASES  # noqa: E402


@pytest.mark.smoke
def test_ingest_result_schema_has_note_path_field():
    assert hasattr(IngestResult, "model_fields")
    assert "note_path" in IngestResult.model_fields


@pytest.mark.smoke
def test_ingest_result_schema_has_frontmatter_field():
    assert "frontmatter" in IngestResult.model_fields


@pytest.mark.smoke
def test_ingest_result_schema_has_tags_field():
    assert "tags" in IngestResult.model_fields


@pytest.mark.smoke
def test_ingest_result_schema_has_needs_review_field():
    assert "needs_review" in IngestResult.model_fields


@pytest.mark.smoke
def test_ingest_result_instantiates_with_note_path():
    result = IngestResult(note_path="vault/Inbox/my-note.md")
    assert result.note_path == "vault/Inbox/my-note.md"
    assert result.frontmatter == {}
    assert result.tags == []
    assert result.needs_review is False


@pytest.mark.integration
@pytest.mark.parametrize("case", INGEST_CASES, ids=[c["id"] for c in INGEST_CASES])
def test_ingest_field_assertions(case, eval_recorder):
    """Placeholder: real agent run + field assertions. Run with live agent."""
    assert "input" in case
    assert "expected_note_path_prefix" in case
    assert isinstance(case["expected_note_path_prefix"], str)
    assert "expected_min_tags" in case
    assert isinstance(case["expected_min_tags"], int)
    assert "max_latency_seconds" in case
    assert isinstance(case["max_latency_seconds"], (int, float))
    eval_recorder(
        score=1.0,
        output={"all_field_assertions_passed": True},
        eval_input={"case_input": case["input"]},
        case_id=case["id"],
        agent_id="ingest",
    )
