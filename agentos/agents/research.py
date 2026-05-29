"""Research agent — research-worker tier multi-source research with ReasoningTools and vault RAG."""

from __future__ import annotations

import os

from agno.agent import Agent
from agno.tools.reasoning import ReasoningTools
from agno.memory.manager import MemoryManager
from agno.knowledge.knowledge import Knowledge

from agentos.db import db
from agentos.model import chat_model
from agentos.tools.vault import research_topic
from agentos.schemas import ResearchReport

EVAL_JUDGE_TIER = os.getenv("EVAL_JUDGE_TIER", "private-worker")


def make_research_agent(
    memory_manager: MemoryManager,
    knowledge: Knowledge,
    db=db,
) -> Agent:
    """Create a fully-configured research agent (research-worker tier)."""
    return Agent(
        name="research",
        id="research",
        model=chat_model("research-worker"),
        # Memory + session summaries (conversational)
        memory_manager=memory_manager,
        enable_agentic_memory=True,
        enable_agentic_culture=True,
        update_memory_on_run=True,
        add_history_to_context=True,
        enable_session_summaries=True,
        add_session_summary_to_context=True,
        search_past_sessions=True,
        num_past_sessions_to_search=3,
        # Agentic RAG
        knowledge=knowledge,
        search_knowledge=True,
        # Typed output
        output_schema=ResearchReport,
        # Reasoning + HITL research tool
        tools=[ReasoningTools(add_instructions=True), research_topic],
        db=db,
        description="Plan multi-angle research, summarize each angle, aggregate into a single vault note.",
        instructions=[
            "Use research_topic(topic) for any research request.",
            "Return the resulting note path and a 3-line summary.",
            "If approval is required, Agno will pause the run automatically — do not surface it manually.",
        ],
    )


# Module-level instance for backward-compatible imports (uses defaults / no memory/knowledge)
research_agent = Agent(
    name="research",
    db=db,
    model=chat_model("research-worker"),
    tools=[ReasoningTools(add_instructions=True), research_topic],
    output_schema=ResearchReport,
    description="Plan multi-angle research, summarize each angle, aggregate into a single vault note.",
    instructions=[
        "Use research_topic(topic) for any research request.",
        "Return the resulting note path and a 3-line summary.",
        "If approval is required, Agno will pause the run automatically — do not surface it manually.",
    ],
    add_history_to_context=True,
)
