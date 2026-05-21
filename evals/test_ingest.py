"""Smoke tests for the ingest agent schema — zero LLM API calls."""
import os

import pytest

os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.schemas import IngestResult  # noqa: E402


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
