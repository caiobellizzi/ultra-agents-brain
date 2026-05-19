"""Query agent — pure vault retrieval, no fallback."""

from __future__ import annotations

from agno.agent import Agent

from agentos.db import db
from agentos.model import chat_model
from agentos.tools.vault import query_vault

query_agent = Agent(
    name="query",
    db=db,
    model=chat_model("cheap-worker"),
    tools=[query_vault],
    description="Answer strictly from vault contents with citations.",
    instructions=[
        "Always call query_vault first.",
        "If no hits, reply 'No vault evidence found for this query.' — do not invent answers.",
        "Cite note paths and line ranges for each claim.",
    ],
)
