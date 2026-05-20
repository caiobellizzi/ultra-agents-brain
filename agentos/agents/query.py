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
        "Always call query_vault(question) first to retrieve evidence.",
        "If the tool reports no evidence, reply exactly: 'No vault evidence found for this query.' Do not invent.",
        "Write a detailed, thorough answer that synthesizes ALL evidence from the tool output. "
        "Do not truncate or be brief — the user wants a complete understanding of the topic.",
        "Do NOT include citation tokens, file paths, or [[...]] references anywhere in the response. "
        "The response must be pure readable prose with no markdown links or file references.",
        "Do not add information that is not in the tool output.",
    ],
)
