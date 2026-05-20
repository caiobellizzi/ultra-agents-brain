"""Conversational agent — answers from the vault, falls back to general chat."""

from __future__ import annotations

import os

from agno.agent import Agent
from agno.eval.agent_as_judge import AgentAsJudgeEval
from agno.knowledge import Knowledge
from agno.memory.manager import MemoryManager

from agentos.db import db
from agentos.model import chat_model
from agentos.schemas import ChatReply
from agentos.tools.vault import query_vault

EVAL_JUDGE_TIER = os.getenv("EVAL_JUDGE_TIER", "private-worker")


def make_chat_agent(
    memory_manager: MemoryManager,
    knowledge: Knowledge,
    db=db,
) -> Agent:
    citation_judge = AgentAsJudgeEval(
        name="chat-must-cite",
        criteria=(
            "If the user's message references something likely in their vault (notes, articles, ideas), "
            "the response MUST include at least one vault citation. "
            "If purely conversational or unrelated to vault content, pass."
        ),
        scoring_strategy="binary",
        model=chat_model(EVAL_JUDGE_TIER),
        db=db,
        run_in_background=True,
    )

    return Agent(
        name="chat",
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
        # Knowledge / agentic RAG
        knowledge=knowledge,
        search_knowledge=True,
        # Typed output
        output_schema=ChatReply,
        # Tools, instructions, storage
        tools=[query_vault],
        description="Conversational front-end. Cite the vault when relevant.",
        instructions=[
            "Prefer evidence from the vault (use query_vault) before answering.",
            "If the vault has no relevant content, say so and answer from general knowledge — but mark such replies with the prefix '(general knowledge)' so the user knows it is not vault-sourced.",
            "When citing vault evidence, copy the EXACT [[path/to/file.md:NNN]] token from the tool output. "
            "Do not paraphrase, summarise, or invent citations. The formats [vault:page_X_line_Y], [page N], "
            "and [file N] are FORBIDDEN — only [[...md:N]] is allowed.",
            "Be concise.",
        ],
        db=db,
    )
    # NOTE: citation_judge (AgentAsJudgeEval) is defined above for future use.
    # The current Agno version does not accept an `evals=` kwarg on Agent.
    # Wire it when the Agno API exposes evaluation support.
    _ = citation_judge


# Module-level instance for backward compatibility (app.py, tests).
# memory_manager and knowledge are wired in Wave 3; until then they are None.
chat_agent = make_chat_agent(memory_manager=None, knowledge=None)
