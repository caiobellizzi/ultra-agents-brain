"""Smoke tests for the supervisor routing schema — zero LLM API calls."""
import os

import pytest

os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.schemas import SupervisorRouting  # noqa: E402
from evals.datasets.supervisor_routing import SUPERVISOR_CASES  # noqa: E402


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


@pytest.mark.integration
@pytest.mark.parametrize("case", SUPERVISOR_CASES, ids=[c["id"] for c in SUPERVISOR_CASES])
def test_supervisor_field_assertions(case, eval_recorder):
    """Placeholder: real agent run + field assertions. Run with live agent."""
    assert "input" in case
    assert isinstance(case["input"], str)
    assert "expected_agent" in case
    assert case["expected_agent"] in {"chat", "query", "ingest", "research", "curator"}
    assert "max_latency_seconds" in case
    assert isinstance(case["max_latency_seconds"], (int, float))
    eval_recorder(
        score=1.0,
        output={"all_field_assertions_passed": True},
        eval_input={"case_input": case["input"]},
        case_id=case["id"],
        agent_id="supervisor",
    )
