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
        "If the vault has no relevant content, say so and answer from general knowledge — but mark such replies with the prefix '(general knowledge)' so the user knows it is not vault-sourced.",
        "When citing vault evidence, copy the EXACT [[path/to/file.md:NNN]] token from the tool output. "
        "Do not paraphrase, summarise, or invent citations. The formats [vault:page_X_line_Y], [page N], "
        "and [file N] are FORBIDDEN — only [[...md:N]] is allowed.",
        "Be concise.",
    ],
    add_history_to_context=True,
)
