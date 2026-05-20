"""Supervisor agent — central orchestrator for the Second Brain agent team using Agno Team."""

from __future__ import annotations

from agno.memory.manager import MemoryManager
from agno.team import Team

from agentos.agents.curator import curator_agent
from agentos.agents.ingest import ingest_agent
from agentos.agents.query import query_agent
from agentos.agents.research import research_agent
from agentos.db import db
from agentos.model import chat_model


def make_supervisor_team(
    memory_manager: MemoryManager,
    db=db,
) -> Team:
    """Create a fully-wired supervisor team accepting a shared MemoryManager."""
    return Team(
        name="supervisor",
        db=db,
        model=chat_model("orchestrator"),
        members=[ingest_agent, query_agent, research_agent, curator_agent],
        description="Central orchestrator. Coordinates specialized agents to handle user requests.",
        instructions=[
            "You are the Supervisor Agent (Team Leader) of the Second Brain system.",
            "Your task is to analyze user requests, break them down, delegate tasks to specialized team members, and synthesize the results.",
            "",
            "SPECIALIST TEAM MEMBERS:",
            "1. 'query' agent: Answers questions strictly using evidence from the vault.",
            "   - Use this agent for any questions about vault contents, notes, concepts, or past entries.",
            "2. 'ingest' agent: Extracts and files URLs, files, or pasted text into the vault.",
            "   - Use this agent when the user wants to save, store, ingest, or file a web page, file, or note.",
            "3. 'research' agent: Performs multi-angle web research and aggregates findings into a vault note.",
            "   - Use this agent when the user wants deep research, web searches, or summaries of external topics.",
            "4. 'curator' agent: Runs periodic maintenance routines (digest, review, lint, poll_feeds).",
            "   - Use this agent when the user asks to run vault maintenance tasks like linting, feeds, daily digest, or weekly reviews.",
            "",
            "COORDINATION INSTRUCTIONS:",
            "- Analyze the user's intent. If it's a multi-step request, decompose it into sequential steps and call the appropriate agents.",
            "- For example, to research a topic and check if we already have files on it, first delegate to the 'query' agent, then delegate to the 'research' agent, and synthesize the result.",
            "- Do not call any tools directly; always delegate to your specialized team members.",
            "- If a team member requires Human-in-the-Loop confirmation (e.g. for ingesting or researching), the run will pause automatically. Do not try to bypass this.",
            "- Synthesize the final response for the user clearly. Do not output raw markdown links or file reference citation tokens (like [[...]]) unless explicitly requested or returned by the team member.",
        ],
        add_history_to_context=True,
        enable_agentic_memory=True,
        update_memory_on_run=True,
        enable_session_summaries=True,
        add_session_summary_to_context=True,
        search_past_sessions=True,
        num_past_sessions_to_search=3,
        add_team_history_to_members=True,
        share_member_interactions=True,
        reasoning=True,
    )


# Module-level instance for backward compatibility (tests, direct imports).
# memory_manager is wired in Wave 3 via app.py; until then it is None.
supervisor_agent = make_supervisor_team(memory_manager=None)
