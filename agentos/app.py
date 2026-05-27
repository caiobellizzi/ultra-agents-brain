"""AgentOS host — uses Agno's built-in AgentOS class.

Exposes the standard Agno route surface (agents, sessions, runs, memory,
knowledge, approvals) so the hosted dashboard at https://os.agno.com works,
plus any third-party tools that speak the AgentOS HTTP schema.

Channels (Telegram adapter, cron timers) call `POST /agents/{agent_id}/runs`
with a JSON body — not our previous `/v1/agents/<name>` shape.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
load_dotenv()

from agno.os.app import AgentOS

from agentos.knowledge import make_knowledge
from agentos.model import chat_model
from agentos.agents.chat import make_chat_agent
from agentos.agents.curator import make_curator_agent
from agentos.agents.ingest import make_ingest_agent
from agentos.agents.query import make_query_agent
from agentos.agents.research import make_research_agent
from agentos.agents.supervisor import make_supervisor_team
import agentos.cost  # noqa: F401 — registers litellm success_callback for cost ledger

# --- Database: PostgresDb in production, SqliteDb fallback for local/test environments ---
POSTGRES_DSN_SESSIONS = os.getenv("POSTGRES_DSN_SESSIONS")

if POSTGRES_DSN_SESSIONS:
    from agno.db.postgres import PostgresDb
    db = PostgresDb(id="ultra-brain-main", db_url=POSTGRES_DSN_SESSIONS, create_schema=True)
else:
    # Fallback for local development / testing (no POSTGRES_DSN_SESSIONS set)
    from pathlib import Path
    from agno.db.sqlite import SqliteDb
    _DB_PATH = Path(os.environ.get("UAB_DB_PATH", "~/Documents/uab-state/agno.db")).expanduser()
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = SqliteDb(db_file=str(_DB_PATH))

# --- Shared MemoryManager (one instance, all agents share it) ---
from agentos.instrumented_memory import InstrumentedMemoryManager
memory = InstrumentedMemoryManager(
    db=db,
    model=chat_model("cheap-worker"),
)

# --- Knowledge base (PgVector RAG, wired with contents_db for AgentOS routes) ---
# make_knowledge() returns a Knowledge with name='ultra-brain-vault', vector_db,
# and contents_db=POSTGRES_DB. Stub fallback (no DSN) emits a WARNING log.
kb = make_knowledge()

# --- Agent factory calls (all receive memory + knowledge) ---
chat_agent = make_chat_agent(memory_manager=memory, knowledge=kb, db=db)
curator_agent = make_curator_agent(memory_manager=memory, db=db)
ingest_agent = make_ingest_agent(memory_manager=memory, db=db)
query_agent = make_query_agent(memory_manager=memory, knowledge=kb, db=db)
research_agent = make_research_agent(memory_manager=memory, knowledge=kb, db=db)
supervisor_team = make_supervisor_team(memory_manager=memory, db=db)

# --- OBS-01 / EVAL-01: instrument every Agent/Team with the eval recorder ---
# Class-level patch — Agno's HTTP route calls agent.deep_copy() per request,
# which strips instance-set arun wrappers. The class-level patch survives
# deep_copy because fresh instances inherit the patched class methods, and
# the bound recorder is class-level (Agent._eval_recorder), so every Agent
# instance picks it up via attribute lookup.
from agentos.eval_recorder import patch_classes_for_recording
patch_classes_for_recording(db=db)
from agentos.approval_recorder import patch_db_for_approval_recording
patch_db_for_approval_recording(db=db)

# --- AgentOS: MCP + A2A + tracing ---
# NOTE: In this version of Agno, enable_mcp_server is set ONLY on AgentOS();
# get_app() reads from self.enable_mcp_server (no separate kwarg on get_app).
agent_os = AgentOS(
    name="ultra-brain",
    description="Second-brain agents over a markdown vault.",
    db=db,
    agents=[chat_agent, curator_agent, ingest_agent, query_agent, research_agent],
    teams=[supervisor_team],
    knowledge=[kb],
    cors_allowed_origins=["https://os.agno.com", "http://localhost:3000"],
    enable_mcp_server=True,
    a2a_interface=True,
    tracing=True,
)

app = agent_os.get_app()

# Localhost-only route for the Workshop pipeline to persist its repo registry.
# The registry lives in the vault's _system/ dir (owned by uabrain); the
# Workshop (uws) cannot write there, so it PUTs the computed document here.
from agentos.workshop_registry import register_workshop_routes

register_workshop_routes(app)
