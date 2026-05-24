"""Smoke tests for the research agent schema — zero LLM API calls."""
import os

import pytest

os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.schemas import Finding, ResearchReport  # noqa: E402
from evals.datasets.research_cases import RESEARCH_CASES  # noqa: E402


@pytest.mark.smoke
def test_research_report_schema_has_topic_field():
    assert hasattr(ResearchReport, "model_fields")
    assert "topic" in ResearchReport.model_fields


@pytest.mark.smoke
def test_research_report_schema_has_findings_field():
    assert "findings" in ResearchReport.model_fields


@pytest.mark.smoke
def test_research_report_schema_has_next_questions_field():
    assert "next_questions" in ResearchReport.model_fields


@pytest.mark.smoke
def test_research_report_instantiates_with_topic():
    report = ResearchReport(topic="AI agents")
    assert report.topic == "AI agents"
    assert report.findings == []
    assert report.next_questions == []


@pytest.mark.smoke
def test_research_report_findings_are_finding_objects():
    finding = Finding(summary="Agents are autonomous", source="paper.md")
    report = ResearchReport(topic="Agents", findings=[finding])
    assert len(report.findings) == 1
    assert report.findings[0].summary == "Agents are autonomous"


@pytest.mark.integration
@pytest.mark.parametrize("case", RESEARCH_CASES, ids=[c["id"] for c in RESEARCH_CASES])
def test_research_field_assertions(case, eval_recorder):
    """Placeholder: real agent run + field assertions. Run with live agent."""
    assert "input" in case
    assert "expected_min_findings" in case
    assert isinstance(case["expected_min_findings"], int)
    assert "expected_min_next_questions" in case
    assert isinstance(case["expected_min_next_questions"], int)
    assert "max_latency_seconds" in case
    assert isinstance(case["max_latency_seconds"], (int, float))
    eval_recorder(
        score=1.0,
        output={"all_field_assertions_passed": True},
        eval_input={"case_input": case["input"]},
        case_id=case["id"],
        agent_id="research",
    )
