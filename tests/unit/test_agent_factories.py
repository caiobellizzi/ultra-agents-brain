"""MEM-03 / D-06 unit assertions — verify per-factory update_memory_on_run."""
import os

# Required env var for agentos.model (transitively imported by every factory).
os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-tests")

from unittest.mock import MagicMock

import pytest

from agentos.agents.chat import make_chat_agent
from agentos.agents.curator import make_curator_agent
from agentos.agents.ingest import make_ingest_agent
from agentos.agents.query import make_query_agent
from agentos.agents.research import make_research_agent
from agentos.agents.supervisor import make_supervisor_team


@pytest.fixture
def mocks():
    return MagicMock(), MagicMock(), MagicMock()


def test_chat_agent_auto_extracts(mocks):
    memory_manager, knowledge, db = mocks
    agent = make_chat_agent(memory_manager=memory_manager, knowledge=knowledge, db=db)
    assert agent.update_memory_on_run is True
    assert agent.memory_manager is memory_manager
    assert agent.id == "chat"


def test_query_agent_auto_extracts(mocks):
    memory_manager, knowledge, db = mocks
    agent = make_query_agent(memory_manager=memory_manager, knowledge=knowledge, db=db)
    assert agent.update_memory_on_run is True
    assert agent.id == "query"


def test_research_agent_auto_extracts(mocks):
    memory_manager, knowledge, db = mocks
    agent = make_research_agent(memory_manager=memory_manager, knowledge=knowledge, db=db)
    assert agent.update_memory_on_run is True
    assert agent.id == "research"


def test_curator_agent_does_not_auto_extract(mocks):
    memory_manager, _, db = mocks
    agent = make_curator_agent(memory_manager=memory_manager, db=db)
    assert agent.update_memory_on_run is False
    assert agent.id == "curator"


def test_ingest_agent_does_not_auto_extract(mocks):
    memory_manager, _, db = mocks
    agent = make_ingest_agent(memory_manager=memory_manager, db=db)
    assert agent.update_memory_on_run is False
    assert agent.id == "ingest"


def test_supervisor_team_auto_extracts(mocks):
    memory_manager, _, db = mocks
    team = make_supervisor_team(memory_manager=memory_manager, db=db)
    assert team.update_memory_on_run is True
    assert team.id == "supervisor"
