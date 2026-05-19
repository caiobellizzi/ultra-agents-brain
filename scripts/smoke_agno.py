"""Wave 1 smoke test: confirm Agno can reach the LiteLLM proxy on :4000.

Run:
    .venv/bin/python scripts/smoke_agno.py

Prereqs:
    - LM Studio loaded with a model and serving on http://localhost:1234
    - LiteLLM proxy running on http://127.0.0.1:4000 (deploy/litellm/config.yaml)

Expected: a one-sentence greeting via `cheap-worker` (LM Studio behind LiteLLM).
"""
from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.openai import OpenAIChat

agent = Agent(
    model=OpenAIChat(
        id="cheap-worker",
        base_url="http://127.0.0.1:4000/v1",
        api_key="sk-dev-local",  # matches LITELLM_MASTER_KEY in .env
    ),
    db=SqliteDb(db_file="/tmp/uab-smoke.db"),
)
agent.print_response("Say hello in one sentence.")
