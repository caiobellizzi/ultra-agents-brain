"""Shared fixtures for the evals/ test suite.

judge_model is driven by EVAL_JUDGE_TIER (default: private-worker = LM Studio,
offline / free). Override per run: EVAL_JUDGE_TIER=orchestrator pytest evals/

eval_db returns None when POSTGRES_DSN_SESSIONS is not set so smoke tests
run without a live Postgres connection.
"""
import os

import pytest

# Required by agentos.model at import time; set before any agentos import.
os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.model import chat_model  # noqa: E402  (must come after env setdefault)

EVAL_JUDGE_TIER = os.getenv("EVAL_JUDGE_TIER", "private-worker")
POSTGRES_DSN_SESSIONS = os.getenv("POSTGRES_DSN_SESSIONS")


@pytest.fixture(scope="session")
def judge_model():
    return chat_model(EVAL_JUDGE_TIER)


@pytest.fixture(scope="session")
def eval_db():
    if POSTGRES_DSN_SESSIONS:
        from agno.storage.postgres import PostgresDb
        return PostgresDb(db_url=POSTGRES_DSN_SESSIONS, create_schema=True)
    return None
