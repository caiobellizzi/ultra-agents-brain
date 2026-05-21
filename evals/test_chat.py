"""Smoke tests for the chat agent schema — zero LLM API calls."""
import os

import pytest

os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.schemas import ChatReply, VaultCitation  # noqa: E402
from evals.datasets.chat_cases import CHAT_CASES  # noqa: E402


@pytest.mark.smoke
def test_chat_reply_schema_has_text_field():
    assert hasattr(ChatReply, "model_fields")
    assert "text" in ChatReply.model_fields


@pytest.mark.smoke
def test_chat_reply_schema_has_citations_field():
    assert "citations" in ChatReply.model_fields


@pytest.mark.smoke
def test_chat_reply_schema_has_suggested_actions_field():
    assert "suggested_actions" in ChatReply.model_fields


@pytest.mark.smoke
def test_chat_reply_instantiates_with_text():
    reply = ChatReply(text="hello")
    assert reply.text == "hello"
    assert reply.citations == []
    assert reply.suggested_actions == []


@pytest.mark.smoke
def test_chat_reply_citations_are_vault_citations():
    citation = VaultCitation(path="vault/note.md", title="Note", tags=["tag1"])
    reply = ChatReply(text="hi", citations=[citation])
    assert len(reply.citations) == 1
    assert reply.citations[0].path == "vault/note.md"


@pytest.mark.integration
@pytest.mark.parametrize("case", CHAT_CASES, ids=[c["id"] for c in CHAT_CASES])
def test_chat_field_assertions(case):
    """Placeholder: real agent run + field assertions. Run with live agent."""
    assert "input" in case
    assert "expected_text_contains" in case
    assert isinstance(case["expected_text_contains"], list)
    assert "max_latency_seconds" in case
    assert isinstance(case["max_latency_seconds"], (int, float))
