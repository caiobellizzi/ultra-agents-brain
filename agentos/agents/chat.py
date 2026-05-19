"""Conversational agent — answers from the vault, falls back to general chat."""

from __future__ import annotations

from agno.agent import Agent

from agentos.db import db
from agentos.model import chat_model
from agentos.tools.vault import query_vault

chat_agent = Agent(
    name="chat",
    db=db,
    model=chat_model("default-worker"),
    tools=[query_vault],
    description="Conversational front-end. Cite the vault when relevant.",
    instructions=[
        "Prefer evidence from the vault (use query_vault) before answering.",
        "If the vault has no relevant content, say so and answer from general knowledge.",
        "Be concise. Cite note paths inline.",
    ],
    add_history_to_context=True,
)
