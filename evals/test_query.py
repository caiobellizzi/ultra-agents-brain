"""Smoke tests for the query agent schema — zero LLM API calls."""
import os

import pytest

os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.schemas import QueryAnswer, VaultCitation  # noqa: E402


@pytest.mark.smoke
def test_query_answer_schema_has_answer_field():
    assert hasattr(QueryAnswer, "model_fields")
    assert "answer" in QueryAnswer.model_fields


@pytest.mark.smoke
def test_query_answer_schema_has_citations_field():
    assert "citations" in QueryAnswer.model_fields


@pytest.mark.smoke
def test_query_answer_schema_has_confidence_field():
    assert "confidence" in QueryAnswer.model_fields


@pytest.mark.smoke
def test_query_answer_instantiates_with_answer():
    answer = QueryAnswer(answer="The vault says...")
    assert answer.answer == "The vault says..."
    assert answer.citations == []
    assert answer.confidence == 1.0


@pytest.mark.smoke
def test_query_answer_citations_are_vault_citations():
    citation = VaultCitation(path="vault/q.md", title="Q Note")
    answer = QueryAnswer(answer="found it", citations=[citation])
    assert len(answer.citations) == 1
    assert answer.citations[0].title == "Q Note"
