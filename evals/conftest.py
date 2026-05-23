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


# --- EVAL-02 suite write path (phase 12 D-09, D-10) -----------------------

import json as _json
import logging as _logging
import uuid as _uuid
from typing import Any as _Any

from sqlalchemy.exc import IntegrityError as _IntegrityError

from agno.db.schemas.evals import EvalRunRecord as _EvalRunRecord, EvalType as _EvalType

_eval_log = _logging.getLogger("agentos.eval")
_eval_log.setLevel(_logging.INFO)


@pytest.fixture(scope="session")
def eval_test_run_id() -> str:
    return f"suite-{_uuid.uuid4()}"


@pytest.fixture
def eval_recorder(request, eval_test_run_id):
    """Per-test recorder. Tests call eval_recorder(score, output, eval_input).
    The pytest_runtest_makereport hook below reads the captured dict and
    writes a row when eval_db is set."""
    captured: dict = {}

    def record(score: float, output: _Any, eval_input: dict, *, case_id=None, agent_id=None) -> None:
        captured["score"] = score
        captured["output"] = output
        captured["eval_input"] = eval_input
        captured["run_id"] = f"{eval_test_run_id}-{request.node.nodeid}"
        captured["case_id"] = case_id
        captured["agent_id"] = agent_id

    request.node.captured_eval = captured
    return record


def _emit_obs01(*, status: str, eval_type: str, run_id, error_type=None, error_msg=None, **extras) -> None:
    record = {
        "path": "eval",
        "status": status,
        "eval_type": eval_type,
        "row_id": run_id if status == "ok" else None,
        "case_id": extras.get("case_id"),
        "score": extras.get("score"),
        "model_id": extras.get("model_id"),
        "model_provider": extras.get("model_provider"),
        "agent_id": extras.get("agent_id"),
        "db_id": extras.get("db_id"),
        "latency_ms": extras.get("latency_ms", 0),
    }
    if status in ("error", "duplicate"):
        record["error_type"] = error_type
        record["error_msg"] = error_msg
        _eval_log.error("OBS-01 eval suite write %s: %s", status, _json.dumps(record, default=str))
    else:
        _eval_log.info("OBS-01 eval suite write: %s", _json.dumps(record, default=str))


def _record_eval_row(
    eval_db,
    *,
    run_id,
    agent_id,
    case_id,
    score,
    output,
    eval_input,
    model_id=None,
    model_provider=None,
) -> None:
    """Module-private write helper. Exposed for unit tests."""
    if eval_db is None:
        return  # D-10: offline runs skip the write entirely
    db_id = getattr(eval_db, "id", None)
    record = _EvalRunRecord(
        run_id=run_id,
        eval_type=_EvalType.ACCURACY,
        agent_id=agent_id,
        model_id=model_id,
        model_provider=model_provider,
        eval_input=eval_input,
        eval_data={
            "score": score,
            "output": output,
            "case_id": case_id,
            "model_id": model_id,
            "model_provider": model_provider,
            "status": "ok",
        },
    )
    try:
        eval_db.create_eval_run(record)
        _emit_obs01(
            status="ok",
            eval_type=_EvalType.ACCURACY.value,
            run_id=run_id,
            agent_id=agent_id,
            db_id=db_id,
            case_id=case_id,
            score=score,
            model_id=model_id,
            model_provider=model_provider,
        )
    except _IntegrityError as exc:
        _emit_obs01(
            status="duplicate",
            eval_type=_EvalType.ACCURACY.value,
            run_id=run_id,
            agent_id=agent_id,
            db_id=db_id,
            case_id=case_id,
            score=score,
            error_type=exc.__class__.__name__,
            error_msg=str(exc)[:200],
        )
    except Exception as exc:
        _emit_obs01(
            status="error",
            eval_type=_EvalType.ACCURACY.value,
            run_id=run_id,
            agent_id=agent_id,
            db_id=db_id,
            case_id=case_id,
            score=score,
            error_type=exc.__class__.__name__,
            error_msg=str(exc)[:200],
        )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    outcome.get_result()
    if call.when != "call":
        return
    captured = getattr(item, "captured_eval", None)
    if not captured:
        return
    if item.config.getoption("--write-baseline") or item.config.getoption("--update-baseline"):
        return  # baseline mode owns scoring; do not double-write
    eval_db_val = item.funcargs.get("eval_db")
    agent_id = (
        captured.get("agent_id")
        or item.nodeid.split("::")[0].split("/")[-1].replace("test_", "").replace(".py", "")
    )
    _record_eval_row(
        eval_db_val,
        run_id=captured["run_id"],
        agent_id=agent_id,
        case_id=captured.get("case_id"),
        score=captured["score"],
        output=captured["output"],
        eval_input=captured["eval_input"],
    )
