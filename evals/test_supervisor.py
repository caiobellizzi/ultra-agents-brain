"""Smoke tests for the supervisor routing schema — zero LLM API calls."""
import os

import pytest

os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.schemas import SupervisorRouting  # noqa: E402


@pytest.mark.smoke
def test_supervisor_routing_schema_has_chosen_member_field():
    assert hasattr(SupervisorRouting, "model_fields")
    assert "chosen_member" in SupervisorRouting.model_fields


@pytest.mark.smoke
def test_supervisor_routing_schema_has_reason_field():
    assert "reason" in SupervisorRouting.model_fields


@pytest.mark.smoke
def test_supervisor_routing_schema_has_response_field():
    assert "response" in SupervisorRouting.model_fields


@pytest.mark.smoke
def test_supervisor_routing_instantiates_with_member():
    routing = SupervisorRouting(chosen_member="query")
    assert routing.chosen_member == "query"
    assert routing.reason == ""
    assert routing.response == ""


@pytest.mark.smoke
def test_supervisor_routing_members_are_known_agents():
    known_agents = {"chat", "query", "ingest", "research", "curator"}
    for member in known_agents:
        routing = SupervisorRouting(chosen_member=member)
        assert routing.chosen_member == member
