"""Unit tests for the EVAL-02 suite write hook in evals/conftest.py.

Validates the module-private helper `_record_eval_row` directly — pytest hook
mechanics are integration-tested by the suite itself in plan 12-03.
"""
from __future__ import annotations

import logging

import pytest
from sqlalchemy.exc import IntegrityError


class _FakeDb:
    def __init__(self, id_="test-db"):
        self.id = id_
        self.captured = []
        self._calls = 0
        self._raise_after = None  # None | int (number of OK calls before raise)
        self._raise_exc = None

    def create_eval_run(self, record):
        self._calls += 1
        if self._raise_after is not None and self._calls > self._raise_after:
            raise self._raise_exc
        self.captured.append(record)
        return record


def test_hook_swallows_duplicate(caplog):
    """First call writes a row + emits status=ok; second call with the same
    run_id raises IntegrityError inside the helper, which swallows it and
    emits status=duplicate. Mirrors plan 12-01 swallow semantics."""
    from evals.conftest import _record_eval_row

    db = _FakeDb()
    db._raise_after = 1
    db._raise_exc = IntegrityError("duplicate key", None, Exception("orig"))

    common = dict(
        run_id="suite-test-1",
        agent_id="chat",
        case_id="case-0",
        score=0.8,
        output="hi",
        eval_input={"user_message": "ping"},
        model_id="openai/gpt-4o",
        model_provider="litellm",
    )

    with caplog.at_level(logging.INFO, logger="agentos.eval"):
        _record_eval_row(db, **common)
        _record_eval_row(db, **common)

    ok_msgs = [r for r in caplog.records if "OBS-01 eval suite write:" in r.message]
    dup_msgs = [r for r in caplog.records if "OBS-01 eval suite write duplicate" in r.message]
    assert len(ok_msgs) == 1, f"expected 1 ok line, got {len(ok_msgs)}"
    assert len(dup_msgs) == 1, f"expected 1 duplicate line, got {len(dup_msgs)}"
    assert db._calls == 2  # both attempts hit the DB; only first inserted


def test_hook_skips_when_db_none(caplog):
    """eval_db=None short-circuits — no DB call, no log line."""
    from evals.conftest import _record_eval_row

    with caplog.at_level(logging.DEBUG, logger="agentos.eval"):
        _record_eval_row(
            None,
            run_id="suite-test-2",
            agent_id="chat",
            case_id="case-0",
            score=0.8,
            output="hi",
            eval_input={"user_message": "ping"},
        )
    obs_records = [r for r in caplog.records if "OBS-01 eval suite write" in r.message]
    assert obs_records == [], f"expected zero log lines when db is None, got {obs_records}"
