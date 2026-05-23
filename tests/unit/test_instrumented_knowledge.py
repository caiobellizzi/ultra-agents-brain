"""Unit tests for the InstrumentedKnowledge subclass (plan 13-02).

Covers D-03 / D-03c / D-05 + RESEARCH R-05 / R-06 / R-07.
"""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from agno.knowledge.knowledge import Knowledge


# --------------------------------------------------------------------------- helpers


def fake_doc(content_id: str, content: str = "snippet"):
    return SimpleNamespace(
        meta_data={"content_id": content_id},
        content=content,
        name=f"chunk-{content_id}",
    )


class FakeContentsDb:
    def __init__(self, id_: str = "ultra-brain-main"):
        self.id = id_
        self.rows: dict[str, SimpleNamespace] = {}
        self.upsert_calls: list = []

    def get_knowledge_content(self, content_id):
        return self.rows.get(content_id)

    def upsert_knowledge_content(self, row):
        self.upsert_calls.append(row)
        self.rows[row.id] = row
        return row


def _ik(vector_db=None, contents_db=None):
    """Build InstrumentedKnowledge bypassing PgVector type coercions."""
    from agentos.instrumented_knowledge import InstrumentedKnowledge

    return InstrumentedKnowledge(
        name="ultra-brain-vault-test",
        vector_db=vector_db or MagicMock(),
        contents_db=contents_db or FakeContentsDb(),
    )


# --------------------------------------------------------------------------- tests


def test_subclass_relationship():
    """R-07: InstrumentedKnowledge IS-A Knowledge."""
    from agentos.instrumented_knowledge import InstrumentedKnowledge

    assert issubclass(InstrumentedKnowledge, Knowledge)


def test_search_subclass_returns_documents(monkeypatch):
    """D-03: happy path returns the documents from super().search() unchanged."""
    contents_db = FakeContentsDb()
    contents_db.rows = {
        "c1": SimpleNamespace(id="c1", name="a.md", access_count=0),
        "c2": SimpleNamespace(id="c2", name="b.md", access_count=0),
    }
    ik = _ik(contents_db=contents_db)

    monkeypatch.setattr(
        Knowledge, "search", lambda self, *a, **kw: [fake_doc("c1"), fake_doc("c2")]
    )

    out = ik.search("hello")
    assert len(out) == 2
    assert out[0].meta_data["content_id"] == "c1"
    assert out[1].meta_data["content_id"] == "c2"


def test_search_bumps_access_count_per_unique_hit(monkeypatch):
    """D-03 + R-05 dedup: c1 appears twice, c2 once → 2 upsert calls, +1 each."""
    contents_db = FakeContentsDb()
    contents_db.rows = {
        "c1": SimpleNamespace(id="c1", name="a.md", access_count=3, updated_at=0),
        "c2": SimpleNamespace(id="c2", name="b.md", access_count=7, updated_at=0),
    }
    ik = _ik(contents_db=contents_db)

    monkeypatch.setattr(
        Knowledge,
        "search",
        lambda self, *a, **kw: [fake_doc("c1"), fake_doc("c1"), fake_doc("c2")],
    )

    ik.search("query")

    assert len(contents_db.upsert_calls) == 2
    assert contents_db.rows["c1"].access_count == 4
    assert contents_db.rows["c2"].access_count == 8


def test_search_swallows_exception_and_returns_empty(monkeypatch, caplog):
    """D-03 log-and-swallow: vector_db raises → wrapper returns [] + ERROR log."""
    contents_db = FakeContentsDb()
    ik = _ik(contents_db=contents_db)

    def _boom(self, *a, **kw):
        raise RuntimeError("vector db dead")

    monkeypatch.setattr(Knowledge, "search", _boom)

    with caplog.at_level(logging.ERROR, logger="agentos.knowledge"):
        out = ik.search("query")

    assert out == []
    assert contents_db.upsert_calls == []
    err_records = [
        r for r in caplog.records
        if r.levelno == logging.ERROR and r.name == "agentos.knowledge"
    ]
    assert len(err_records) >= 1
    msg = err_records[-1].message
    payload = json.loads(msg[msg.index("{"):])
    assert payload["status"] == "error"
    assert payload["error_type"] == "RuntimeError"
    assert payload["op"] == "search"


def test_search_emits_obs01_log(monkeypatch, caplog):
    """D-05 access schema: structured JSON suffix with all required fields."""
    contents_db = FakeContentsDb()
    contents_db.rows = {"c1": SimpleNamespace(id="c1", name="a.md", access_count=0, updated_at=0)}
    ik = _ik(contents_db=contents_db)

    monkeypatch.setattr(Knowledge, "search", lambda self, *a, **kw: [fake_doc("c1")])

    long_query = "test query" + ("x" * 300)
    with caplog.at_level(logging.INFO, logger="agentos.knowledge"):
        ik.search(long_query)

    obs_records = [
        r for r in caplog.records
        if r.name == "agentos.knowledge" and r.message.startswith("OBS-01 knowledge search")
    ]
    assert len(obs_records) >= 1
    msg = obs_records[0].message
    payload = json.loads(msg[msg.index("{"):])

    assert payload["path"] == "knowledge"
    assert payload["agent_id"] is None
    assert payload["db_id"] == "ultra-brain-main"
    assert payload["op"] == "search"
    assert len(payload["query"]) == 200  # truncated
    assert payload["hit_count"] == 1
    assert isinstance(payload["latency_ms"], int) and payload["latency_ms"] >= 0
    assert payload["status"] == "ok"
    assert payload["row_id"] is None


@pytest.mark.asyncio
async def test_asearch_emits_log_and_bumps_access_count(monkeypatch, caplog):
    """D-03c sync + async parity: asearch logs + bumps just like search."""
    contents_db = FakeContentsDb()
    contents_db.rows = {"c1": SimpleNamespace(id="c1", name="a.md", access_count=0, updated_at=0)}
    ik = _ik(contents_db=contents_db)

    async def _fake_asearch(self, *a, **kw):
        return [fake_doc("c1")]

    monkeypatch.setattr(Knowledge, "asearch", _fake_asearch)

    with caplog.at_level(logging.INFO, logger="agentos.knowledge"):
        out = await ik.asearch("hi")

    assert len(out) == 1
    assert len(contents_db.upsert_calls) == 1
    assert contents_db.rows["c1"].access_count == 1
    obs_records = [
        r for r in caplog.records
        if r.name == "agentos.knowledge" and "OBS-01 knowledge search" in r.message
    ]
    assert len(obs_records) >= 1
    payload = json.loads(obs_records[0].message[obs_records[0].message.index("{"):])
    assert payload["op"] == "search"


def test_make_knowledge_returns_instrumented(monkeypatch):
    """R-07 wiring: make_knowledge() success branch returns InstrumentedKnowledge."""
    monkeypatch.setenv("POSTGRES_DSN_KNOWLEDGE", "postgresql://fake")
    monkeypatch.setenv("POSTGRES_DSN_SESSIONS", "postgresql://fake-sessions")

    import agentos.knowledge as kmod
    from agentos.instrumented_knowledge import InstrumentedKnowledge

    monkeypatch.setattr(kmod, "PgVector", MagicMock(return_value=MagicMock(name="pgvector")))
    fake_pg_db = MagicMock(name="postgres_db")
    fake_pg_db.id = "ultra-brain-main"
    monkeypatch.setattr(kmod, "POSTGRES_DB", fake_pg_db)

    out = kmod.make_knowledge()
    assert isinstance(out, InstrumentedKnowledge)
    assert out.name == "ultra-brain-vault"
