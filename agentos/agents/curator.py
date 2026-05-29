"""Curator agent — periodic vault maintenance: digest, review, lint, feed polling.

Invoked by systemd timers via curl POST. Each invocation passes a `task` field
selecting which curator behaviour to run; the agent dispatches to the matching tool.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.memory.manager import MemoryManager

from agentos.db import db
from agentos.model import chat_model
from agentos.schemas import CuratorResult
from agentos.tools.vault import lint_vault, poll_feeds, run_digest, run_review


def make_curator_agent(memory_manager: MemoryManager, db=db) -> Agent:
    return Agent(
        name="curator",
        id="curator",
        db=db,
        model=chat_model("cheap-worker"),
        # Memory
        memory_manager=memory_manager,
        enable_agentic_memory=True,
        enable_agentic_culture=True,
        update_memory_on_run=False,  # phase 11 D-06: background/bulk agents don't auto-extract memory
        add_history_to_context=True,
        # NO session summaries — one-shot bulk agent
        # NO knowledge= — writes TO vault, not reads
        # Typed output
        output_schema=CuratorResult,
        tools=[run_digest, run_review, lint_vault, poll_feeds],
        description="Vault maintenance: daily digest, weekly review, lint, RSS polling.",
        instructions=[
            "When the user message is 'digest', call run_digest.",
            "When 'review', call run_review.",
            "When 'lint', call lint_vault.",
            "When 'poll_feeds', call poll_feeds.",
            "Return the tool's result verbatim.",
        ],
    )


# Module-level instance for backward compatibility (app.py, tests).
# memory_manager is wired in Wave 3; until then it is None.
curator_agent = make_curator_agent(memory_manager=None)
