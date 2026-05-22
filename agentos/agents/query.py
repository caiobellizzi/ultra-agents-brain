"""Query agent — pure vault retrieval, no fallback."""

from __future__ import annotations

import os

from agno.agent import Agent
from agno.eval.agent_as_judge import AgentAsJudgeEval
from agno.knowledge import Knowledge
from agno.memory.manager import MemoryManager
from agno.tools.reasoning import ReasoningTools

from agentos.db import db
from agentos.model import chat_model
from agentos.schemas import QueryAnswer
from agentos.tools.vault import query_vault

EVAL_JUDGE_TIER = os.getenv("EVAL_JUDGE_TIER", "private-worker")


def make_query_agent(
    memory_manager: MemoryManager,
    knowledge: Knowledge,
    db=db,
) -> Agent:
    citation_judge = AgentAsJudgeEval(
        name="query-must-cite",
        criteria=(
            "The answer MUST cite at least one vault source. "
            "If no relevant vault content exists, say so explicitly rather than answering without citations."
        ),
        scoring_strategy="binary",
        model=chat_model(EVAL_JUDGE_TIER),
        db=db,
        run_in_background=True,
    )

    agent = Agent(
        name="query",
        id="query",
        model=chat_model("default-worker"),
        # Memory
        memory_manager=memory_manager,
        enable_agentic_memory=True,
        update_memory_on_run=True,
        add_history_to_context=True,
        # Session summaries
        enable_session_summaries=True,
        add_session_summary_to_context=True,
        search_past_sessions=True,
        num_past_sessions_to_search=3,
        # Agentic RAG
        knowledge=knowledge,
        search_knowledge=True,
        # Typed output
        output_schema=QueryAnswer,
        # Tools
        tools=[ReasoningTools(add_instructions=True), query_vault],
        description="Answer strictly from vault contents with citations.",
        instructions=[
            "Always call query_vault(question) first to retrieve evidence.",
            "If the tool reports no evidence, reply exactly: 'No vault evidence found for this query.' Do not invent.",
            "Write a detailed, thorough answer that synthesizes ALL evidence from the tool output. "
            "Do not truncate or be brief — the user wants a complete understanding of the topic.",
            "Do NOT include citation tokens, file paths, or [[...]] references anywhere in the response. "
            "The response must be pure readable prose with no markdown links or file references.",
            "Do not add information that is not in the tool output.",
        ],
        db=db,
    )
    # NOTE: citation_judge (AgentAsJudgeEval) is defined above for future use.
    # The current Agno version does not accept an `evals=` kwarg on Agent.
    # Wire it when the Agno API exposes evaluation support.
    _ = citation_judge

    return agent


# Module-level instance for backward compatibility (app.py, tests).
# memory_manager and knowledge are wired in Wave 3; until then they are None.
query_agent = make_query_agent(memory_manager=None, knowledge=None)
