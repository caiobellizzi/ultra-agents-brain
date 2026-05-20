"""Ingest agent — extracts content from URLs/files and writes to vault.

ingest_to_vault is decorated with @tool(requires_confirmation=True) so Agno
pauses the run and returns status=paused with active_requirements. The Telegram
adapter resumes via POST /runs/{run_id}/continue.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.memory.manager import MemoryManager
from agno.tools.reasoning import ReasoningTools

from agentos.db import db
from agentos.model import chat_model
from agentos.schemas import IngestResult
from agentos.tools.vault import ingest_to_vault


def make_ingest_agent(
    memory_manager: MemoryManager,
    db=db,
) -> Agent:
    return Agent(
        name="ingest",
        model=chat_model("default-worker"),
        # Memory — no session summaries (one-shot bulk agent)
        memory_manager=memory_manager,
        enable_agentic_memory=True,
        update_memory_on_run=True,
        add_history_to_context=True,
        # Typed output
        output_schema=IngestResult,
        # Reasoning + HITL vault tool (NO knowledge= — writes TO vault, not reads)
        tools=[ReasoningTools(add_instructions=True), ingest_to_vault],
        description="Ingest URLs and files into the second-brain vault.",
        instructions=[
            "When given a URL or file path, call ingest_to_vault.",
            "Report the resulting note path back to the user.",
        ],
        db=db,
    )


# Module-level instance for backward compatibility (app.py, tests).
# memory_manager is wired in Wave 3; until then it is None.
ingest_agent = make_ingest_agent(memory_manager=None)
