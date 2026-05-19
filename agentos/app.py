"""FastAPI host exposing all Agno agents over HTTP.

Channels (Telegram adapter, cron timers) call these endpoints. There is no
auth — the service binds to 127.0.0.1 only; channel adapters are responsible
for upstream authentication.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from agentos.agents.chat import chat_agent
from agentos.agents.curator import curator_agent
from agentos.agents.ingest import ingest_agent
from agentos.agents.query import query_agent
from agentos.agents.research import research_agent

log = logging.getLogger("agentos")

app = FastAPI(title="ultra-brain AgentOS", version="0.1.0")


class AgentRequest(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None
    metadata: dict[str, Any] | None = None


class AgentResponse(BaseModel):
    content: str
    session_id: str | None = None
    agent: str


_AGENTS = {
    "chat": chat_agent,
    "ingest": ingest_agent,
    "query": query_agent,
    "research": research_agent,
    "curator": curator_agent,
}


def _run(agent_name: str, req: AgentRequest) -> AgentResponse:
    agent = _AGENTS[agent_name]
    run_response = agent.run(
        req.message,
        session_id=req.session_id,
        user_id=req.user_id,
    )
    return AgentResponse(
        content=run_response.content or "",
        session_id=run_response.session_id,
        agent=agent_name,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/agents/chat", response_model=AgentResponse)
def chat(req: AgentRequest) -> AgentResponse:
    return _run("chat", req)


@app.post("/v1/agents/ingest", response_model=AgentResponse)
def ingest(req: AgentRequest) -> AgentResponse:
    return _run("ingest", req)


@app.post("/v1/agents/query", response_model=AgentResponse)
def query(req: AgentRequest) -> AgentResponse:
    return _run("query", req)


@app.post("/v1/agents/research", response_model=AgentResponse)
def research(req: AgentRequest) -> AgentResponse:
    return _run("research", req)


@app.post("/v1/agents/curator", response_model=AgentResponse)
def curator(req: AgentRequest) -> AgentResponse:
    return _run("curator", req)
