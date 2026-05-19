"""Curator agent — periodic vault maintenance: digest, review, lint, feed polling.

Invoked by systemd timers via curl POST. Each invocation passes a `task` field
selecting which curator behaviour to run; the agent dispatches to the matching tool.
"""

from __future__ import annotations

from agno.agent import Agent

from agentos.db import db
from agentos.model import chat_model
from agentos.tools.vault import lint_vault, poll_feeds, run_digest, run_review

curator_agent = Agent(
    name="curator",
    db=db,
    model=chat_model("cheap-worker"),
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
