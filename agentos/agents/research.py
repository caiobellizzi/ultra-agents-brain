"""Research agent — multi-source web research, files aggregated note to vault."""

from __future__ import annotations

from agno.agent import Agent

from agentos.db import db
from agentos.model import chat_model
from agentos.tools.trust_gate import trust_gate
from agentos.tools.vault import research_topic as _raw_research

research_topic = trust_gate("file research note to vault")(_raw_research)

research_agent = Agent(
    name="research",
    db=db,
    model=chat_model("default-worker"),
    tools=[research_topic],
    description="Plan multi-angle research, summarize each angle, aggregate into a single vault note.",
    instructions=[
        "Use research_topic(topic) for any research request.",
        "Return the resulting note path and a 3-line summary.",
        "Respect the trust gate — if approval is required, surface the prompt and stop.",
    ],
    add_history_to_context=True,
)
