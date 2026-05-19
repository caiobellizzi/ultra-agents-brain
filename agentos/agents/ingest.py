"""Ingest agent — extracts content from URLs/files and writes to vault.

Vault writes are routed through the trust gate so medium-risk paths
(01-Areas, _system, 03-Archives) require Telegram approval before commit.
"""

from __future__ import annotations

from agno.agent import Agent

from agentos.db import db
from agentos.model import chat_model
from agentos.tools.trust_gate import trust_gate
from agentos.tools.vault import ingest_to_vault as _raw_ingest

ingest_to_vault = trust_gate("write note to vault", target_path_arg="source")(_raw_ingest)

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
