"""Unit tests for TELOS-relevance heuristic scoring (RED → GREEN).

Tests verify that ultra_brain.telos_score.score_telos_relevance() correctly
classifies items by alignment with the TELOS mission.
"""

from __future__ import annotations

import pytest

from ultra_brain.telos_score import score_telos_relevance


def test_high_relevance_ai_article() -> None:
    """AI/agent-focused article should score >= 0.6."""
    score = score_telos_relevance(
        title="Claude Code MCP Integration",
        body="How to build agentic workflows using MCP and tool use with Claude.",
        tags=["llm", "agents"],
    )
    assert score >= 0.6, f"Expected >= 0.6 for AI article, got {score}"


def test_low_relevance_news() -> None:
    """General politics/security news should score < 0.3."""
    score = score_telos_relevance(
        title="US Lawmakers Demand Answers on CISA Data Leak",
        body="Congressional leaders are pushing the Cybersecurity and Infrastructure Security Agency for answers.",
        tags=[],
    )
    assert score < 0.3, f"Expected < 0.3 for news article, got {score}"


def test_low_relevance_esoterica() -> None:
    """CS esoterica (APL) is a negative prior and should score < 0.3."""
    score = score_telos_relevance(
        title="Mastering Dyalog APL",
        body="A comprehensive guide to array programming in APL, covering idioms and tacit style.",
        tags=[],
    )
    assert score < 0.3, f"Expected < 0.3 for APL esoterica, got {score}"


def test_medium_relevance_infra() -> None:
    """Off-thesis tech (deep learning performance, not directly agent-building) scores 0.3–0.7."""
    score = score_telos_relevance(
        title="Making deep learning go brrr from first principles",
        body="Performance engineering for neural network training: CUDA kernels, memory bandwidth, and batching.",
        tags=["performance", "python"],
    )
    assert 0.3 <= score <= 0.7, f"Expected 0.3–0.7 for infra article, got {score}"
