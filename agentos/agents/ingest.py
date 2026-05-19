"""Ingest agent — extracts content from URLs/files and writes to vault.

ingest_to_vault is decorated with @tool(requires_confirmation=True) so Agno
pauses the run and returns status=paused with active_requirements. The Telegram
adapter resumes via POST /runs/{run_id}/continue.
"""

from __future__ import annotations

from agno.agent import Agent

from agentos.db import db
from agentos.model import chat_model
from agentos.tools.vault import ingest_to_vault

ingest_agent = Agent(
    name="ingest",
    db=db,
    model=chat_model("cheap-worker"),
    tools=[ingest_to_vault],
    description="Ingest URLs and files into the second-brain vault.",
    instructions=[
        "When given a URL or file path, call ingest_to_vault.",
        "Report the resulting note path back to the user.",
    ],
)
