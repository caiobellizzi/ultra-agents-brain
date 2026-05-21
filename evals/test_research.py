"""Smoke tests for the research agent schema — zero LLM API calls."""
import os

import pytest

os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.schemas import Finding, ResearchReport  # noqa: E402


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
