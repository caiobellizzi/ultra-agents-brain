"""AgentOS host — uses Agno's built-in AgentOS class.

Exposes the standard Agno route surface (agents, sessions, runs, memory,
knowledge, approvals) so the hosted dashboard at https://os.agno.com works,
plus any third-party tools that speak the AgentOS HTTP schema.

Channels (Telegram adapter, cron timers) call `POST /agents/{agent_id}/runs`
with a JSON body — not our previous `/v1/agents/<name>` shape.
"""

from __future__ import annotations

from agno.os.app import AgentOS

from agentos.agents.chat import chat_agent
from agentos.agents.curator import curator_agent
from agentos.agents.ingest import ingest_agent
from agentos.agents.query import query_agent
from agentos.agents.research import research_agent
from agentos.db import db
from agentos.knowledge import kb

agent_os = AgentOS(
    name="ultra-brain",
    description="Second-brain agents over a markdown vault.",
    db=db,
    agents=[chat_agent, ingest_agent, query_agent, research_agent, curator_agent],
    knowledge=[kb.knowledge],
    cors_allowed_origins=["https://os.agno.com", "http://localhost:3000"],
)

app = agent_os.get_app()
