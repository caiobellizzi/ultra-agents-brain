"""EVAL-02 live integration test — writes one accuracy row to the real
ai.agno_eval_runs table, verifies it appears, then cleans up.

Skipped unless POSTGRES_DSN_SESSIONS is set (the `eval_db` fixture returns
None otherwise). Marked @pytest.mark.live so it is not collected in regular
unit-test runs.

Run explicitly with:
    POSTGRES_DSN_SESSIONS=... pytest tests/integration/test_eval_suite_surface.py -m live -q
"""
from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from agno.db.schemas.evals import EvalRunRecord, EvalType


pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def _live_eval_db():
    """Standalone eval_db so the live test never depends on the evals/
    conftest tree. Skips when POSTGRES_DSN_SESSIONS is unset."""
    dsn = os.getenv("POSTGRES_DSN_SESSIONS")
    if not dsn:
        pytest.skip("POSTGRES_DSN_SESSIONS not set — live test requires real Postgres")
    from agno.db.postgres import PostgresDb
    return PostgresDb(id="live-eval-suite", db_url=dsn, create_schema=True)


def test_single_case_writes_row(_live_eval_db):
    """End-to-end: build an EvalRunRecord, write it through PostgresDb,
    verify the row exists in ai.agno_eval_runs, then DELETE for cleanup."""
    run_id = f"int-{uuid.uuid4()}"
    record = EvalRunRecord(
        run_id=run_id,
        eval_type=EvalType.ACCURACY,
        agent_id="integration-test",
        model_id="test/model",
        model_provider="test",
        eval_input={"user_message": "test input"},
        eval_data={
            "score": 0.5,
            "output": "test output",
            "latency_ms": 42,
            "model_id": "test/model",
            "model_provider": "test",
            "status": "ok",
        },
    )

    _live_eval_db.create_eval_run(record)

    dsn = os.environ["POSTGRES_DSN_SESSIONS"]
    engine = create_engine(dsn)
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "SELECT eval_type, run_id, agent_id FROM ai.agno_eval_runs "
                    "WHERE run_id = :rid"
                ),
                {"rid": run_id},
            ).first()
            assert row is not None, f"row with run_id={run_id} not found"
            assert row.eval_type == "accuracy"
            assert row.agent_id == "integration-test"
            conn.execute(
                text("DELETE FROM ai.agno_eval_runs WHERE run_id = :rid"),
                {"rid": run_id},
            )
    finally:
        engine.dispose()
