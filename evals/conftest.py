"""Shared fixtures for the evals/ test suite.

judge_model is driven by EVAL_JUDGE_TIER (default: private-worker = LM Studio,
offline / free). Override per run: EVAL_JUDGE_TIER=orchestrator pytest evals/

eval_db returns None when POSTGRES_DSN_SESSIONS is not set so smoke tests
run without a live Postgres connection.
"""
import json
import os
from pathlib import Path

import pytest

# Required by agentos.model at import time; set before any agentos import.
os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-evals")

from agentos.model import chat_model  # noqa: E402  (must come after env setdefault)

EVAL_JUDGE_TIER = os.getenv("EVAL_JUDGE_TIER", "private-worker")
POSTGRES_DSN_SESSIONS = os.getenv("POSTGRES_DSN_SESSIONS")
BASELINES_DIR = Path(__file__).parent / "baselines"


def pytest_addoption(parser):
    parser.addoption(
        "--write-baseline",
        action="store_true",
        default=False,
        help="Write eval results to baselines/ instead of asserting against them.",
    )
    parser.addoption(
        "--update-baseline",
        action="store_true",
        default=False,
        help="Update existing baseline entries with new scores.",
    )


@pytest.fixture(scope="session")
def write_baseline(request):
    return request.config.getoption("--write-baseline")


@pytest.fixture(scope="session")
def update_baseline(request):
    return request.config.getoption("--update-baseline")


def load_baseline(name: str) -> dict:
    path = BASELINES_DIR / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_baseline(name: str, data: dict) -> None:
    BASELINES_DIR.mkdir(exist_ok=True)
    path = BASELINES_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2))


@pytest.fixture(scope="session")
def judge_model():
    return chat_model(EVAL_JUDGE_TIER)


@pytest.fixture(scope="session")
def eval_db():
    if POSTGRES_DSN_SESSIONS:
        from agno.db.postgres import PostgresDb
        return PostgresDb(db_url=POSTGRES_DSN_SESSIONS, create_schema=True)
    return None
