import json
import logging
from types import SimpleNamespace

import pytest

from agentos.eval_recorder import InstrumentedEvalRecorder


class _FakeDb:
    def __init__(self, id_="test-db", raise_exc=None):
        self.id = id_
        self.captured = []
        self._raise_exc = raise_exc

    def create_eval_run(self, record):
        if self._raise_exc is not None:
            raise self._raise_exc
        self.captured.append(record)
        return record


class _StubAgent:
    """Stand-in for an Agno Agent exposing the run / arun surface the
    wrapper expects."""

    def __init__(self, agent_id="chat-test"):
        self.id = agent_id
        self.name = agent_id
        self._response_factory = self._default_response

    @staticmethod
    def _default_response():
        return SimpleNamespace(
            run_id="r1",
            content="hello",
            metrics={"input_tokens": 4, "output_tokens": 6},
            model=SimpleNamespace(id="openai/gpt-4o", provider="litellm"),
        )

    def run(self, *args, **kwargs):
        return self._response_factory()

    async def arun(self, *args, **kwargs):
        return self._response_factory()


def _wrap(agent=None, db=None):
    agent = agent or _StubAgent()
    db = db or _FakeDb()
    recorder = InstrumentedEvalRecorder(db=db)
    recorder.wrap(agent)
    return agent, db


def _parse_obs01_record(message: str) -> dict:
    """Extract the JSON suffix from an OBS-01 log line."""
    for prefix in ("OBS-01 eval write: ", "OBS-01 eval write failed: "):
        if prefix in message:
            return json.loads(message.split(prefix, 1)[1])
    raise AssertionError(f"no OBS-01 eval payload in message: {message!r}")


def test_wrap_writes_row_on_success(caplog):
    from agno.db.schemas.evals import EvalType

    agent, db = _wrap()

    # Sync path
    with caplog.at_level(logging.INFO, logger="agentos.eval"):
        out = agent.run("hi")
    assert out.content == "hello"
    assert len(db.captured) == 1
    rec = db.captured[0]
    assert rec.eval_type == EvalType.PERFORMANCE
    assert rec.name == "live:chat-test"
    assert rec.evaluated_component_name == "chat-test"
    assert rec.run_id == "r1"
    assert rec.agent_id == "chat-test"
    assert rec.eval_data["score"] is None
    assert rec.eval_data["latency_ms"] >= 0
    assert rec.eval_data["model_id"] == "openai/gpt-4o"
    assert rec.eval_data["model_provider"] == "litellm"
    assert rec.eval_data["status"] == "ok"
    assert rec.eval_input == {"user_message": "hi"}


@pytest.mark.asyncio
async def test_wrap_writes_row_on_success_async(caplog):
    from agno.db.schemas.evals import EvalType

    agent, db = _wrap()
    with caplog.at_level(logging.INFO, logger="agentos.eval"):
        out = await agent.arun("hi")
    assert out.content == "hello"
    assert len(db.captured) == 1
    assert db.captured[0].eval_type == EvalType.PERFORMANCE
    assert db.captured[0].name == "live:chat-test"
    assert db.captured[0].eval_data["status"] == "ok"


@pytest.mark.asyncio
async def test_wrap_swallows_db_error(caplog):
    agent, db = _wrap(db=_FakeDb(raise_exc=RuntimeError("boom")))
    with caplog.at_level(logging.ERROR, logger="agentos.eval"):
        out = await agent.arun("hi")
    assert out.content == "hello"  # agent reply still returned
    error_recs = [r for r in caplog.records if "OBS-01 eval write failed" in r.message]
    assert len(error_recs) == 1
    payload = _parse_obs01_record(error_recs[0].message)
    assert payload["path"] == "eval"
    assert payload["status"] == "error"
    assert payload["error_type"] == "RuntimeError"
    assert payload["error_msg"].startswith("boom")


def test_wrap_emits_obs01_schema(caplog):
    agent, _ = _wrap()
    with caplog.at_level(logging.INFO, logger="agentos.eval"):
        agent.run("hi")
    info_recs = [r for r in caplog.records if "OBS-01 eval write:" in r.message]
    assert len(info_recs) == 1
    payload = _parse_obs01_record(info_recs[0].message)
    # D-15 required keys (eval path)
    assert payload["path"] == "eval"
    assert isinstance(payload["agent_id"], str)
    assert payload["db_id"] == "test-db"
    assert isinstance(payload["row_id"], str)
    assert isinstance(payload["latency_ms"], int) and payload["latency_ms"] >= 0
    assert payload["status"] == "ok"
    assert payload["eval_type"] == "performance"
    assert isinstance(payload["model_provider"], str)
    assert isinstance(payload["model_id"], str)
    assert payload["score"] is None
    assert payload["case_id"] is None


def test_wrap_handles_string_model_name():
    agent, db = _wrap()
    agent._response_factory = lambda: SimpleNamespace(
        run_id="r2",
        content="hello",
        metrics={},
        model="private-worker",
    )

    agent.run("hi")

    rec = db.captured[0]
    assert rec.model_id == "private-worker"
    assert rec.eval_data["model_id"] == "private-worker"
    assert rec.model_provider is None


def test_wrap_adds_pending_live_judge_metadata_when_policy_allows(monkeypatch):
    monkeypatch.setenv("EVAL_LIVE_JUDGE_ENABLED", "true")
    monkeypatch.setenv("EVAL_LIVE_SAMPLE_RATE", "1.0")

    agent, db = _wrap()
    agent.run("hi")

    rec = db.captured[0]
    assert rec.eval_data["judge_status"] == "pending"
    assert rec.eval_data["judge_attempts"] == 0
    assert rec.eval_data["judge_rubric_ids"]


def test_wrap_omits_live_judge_metadata_by_default(monkeypatch):
    monkeypatch.delenv("EVAL_LIVE_JUDGE_ENABLED", raising=False)
    monkeypatch.delenv("EVAL_LIVE_SAMPLE_RATE", raising=False)

    agent, db = _wrap()
    agent.run("hi")

    rec = db.captured[0]
    assert "judge_status" not in rec.eval_data


def test_app_wires_all_six_recorders():
    """Importing agentos.app must wire the InstrumentedEvalRecorder onto
    every one of the 6 agents/team handed to AgentOS."""
    from agentos import app as app_module

    objs = (
        app_module.chat_agent,
        app_module.curator_agent,
        app_module.ingest_agent,
        app_module.query_agent,
        app_module.research_agent,
        app_module.supervisor_team,
    )
    for obj in objs:
        assert hasattr(obj, "_eval_recorder"), f"{obj!r} missing _eval_recorder"
        assert isinstance(obj._eval_recorder, InstrumentedEvalRecorder)
        assert obj._eval_recorder.db is app_module.db
