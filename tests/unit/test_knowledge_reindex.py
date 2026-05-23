"""Unit tests for the rewritten agentos/knowledge.py — make_knowledge wiring +
pure reindex() + cli_main + OBS-01 log shape + stub-fallback WARNING.

Locks plan 13-01 decisions D-01..D-05 + RESEARCH R-03/R-04.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from unittest.mock import MagicMock

import pytest


# --------------------------------------------------------------------------- fakes


class _FakeContentsDb:
    def __init__(self, id_: str = "ultra-brain-main"):
        self.id = id_
        self._rows: list = []
        self._return_count = True

    def get_knowledge_contents(self, *args, **kwargs):
        # Agno's real signature returns (List[KnowledgeRow], int); accept either shape.
        if self._return_count:
            return list(self._rows), len(self._rows)
        return list(self._rows)


class _FakeKnowledgeRow:
    """Minimal stand-in for agno.db.schemas.knowledge.KnowledgeRow."""

    def __init__(self, name: str, metadata: dict, id_: str = "row-1"):
        self.id = id_
        self.name = name
        self.metadata = metadata


class _FakeKnowledge:
    """In-process Knowledge stand-in.

    insert(**kw) records the call and upserts a row keyed by `name`.
    .contents_db.get_knowledge_contents() reflects current rows.
    """

    def __init__(self, contents_db=None, vector_db=None, name: str = "ultra-brain-vault"):
        self.name = name
        self.vector_db = vector_db or object()  # truthy so reindex doesn't bail to stub path
        self.contents_db = contents_db or _FakeContentsDb()
        self.insert_calls: list[dict] = []
        self.rows: dict[str, _FakeKnowledgeRow] = {}
        self._raise_on_call: int | None = None  # 1-indexed call number that raises

    def insert(self, **kw):
        self.insert_calls.append(kw)
        if self._raise_on_call is not None and len(self.insert_calls) == self._raise_on_call:
            raise RuntimeError("boom")
        # upsert semantics: replace by name
        self.rows[kw["name"]] = _FakeKnowledgeRow(
            name=kw["name"], metadata=kw.get("metadata", {})
        )
        # keep contents_db in sync so a second reindex pass sees the row
        self.contents_db._rows = list(self.rows.values())


# --------------------------------------------------------------------------- helpers


def _write(p, content: bytes) -> bytes:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return content


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------- tests


def test_make_knowledge_wires_contents_db_and_name(monkeypatch):
    """D/R-03: make_knowledge() returns Knowledge with name='ultra-brain-vault',
    contents_db wired (id='ultra-brain-main'), and vector_db set."""
    monkeypatch.setenv("POSTGRES_DSN_KNOWLEDGE", "postgresql://fake")
    monkeypatch.setenv("POSTGRES_DSN_SESSIONS", "postgresql://fake-sessions")

    import agentos.knowledge as kmod
    # Patch PgVector at the module attribute so the real network/embedder calls don't happen
    fake_pgvector_instance = MagicMock(name="pgvector_instance")
    fake_pgvector_ctor = MagicMock(return_value=fake_pgvector_instance)
    monkeypatch.setattr(kmod, "PgVector", fake_pgvector_ctor)
    # Patch the shared POSTGRES_DB symbol in the knowledge module's namespace
    fake_contents_db = MagicMock(name="postgres_db")
    fake_contents_db.id = "ultra-brain-main"
    monkeypatch.setattr(kmod, "POSTGRES_DB", fake_contents_db)

    k = kmod.make_knowledge()

    assert k.name == "ultra-brain-vault"
    assert k.vector_db is fake_pgvector_instance
    assert k.contents_db is fake_contents_db
    assert k.contents_db.id == "ultra-brain-main"


def test_stub_fallback_emits_warning(monkeypatch, caplog):
    """D-04: missing DSN → WARNING log line + stub Knowledge (no vector_db, no contents_db)."""
    monkeypatch.setenv("POSTGRES_DSN_KNOWLEDGE", "")

    import agentos.knowledge as kmod

    with caplog.at_level(logging.WARNING, logger="agentos.knowledge"):
        k = kmod.make_knowledge()

    assert k.name == "ultra-brain-vault"
    assert k.vector_db is None
    assert k.contents_db is None

    warns = [r for r in caplog.records if r.levelno == logging.WARNING and r.name == "agentos.knowledge"]
    assert len(warns) >= 1
    msg = warns[-1].message
    # JSON suffix is appended after a space
    payload = json.loads(msg[msg.index("{"):])
    assert payload["status"] == "stub-fallback"
    assert payload["db_id"] is None
    assert payload["reason"]  # non-empty
    assert payload["path"] == "knowledge"


def test_reindex_calls_insert_per_file(tmp_vault):
    """D-01: per-file Knowledge.insert(path, name, metadata, upsert=True, skip_if_exists=False)."""
    from agentos.knowledge import reindex

    _write(tmp_vault / "a.md", b"hello a")
    _write(tmp_vault / "nested" / "b.md", b"hello b")
    _write(tmp_vault / "c.md", b"hello c")

    fake = _FakeKnowledge()
    summary = reindex(vault_path=tmp_vault, knowledge=fake)

    assert len(fake.insert_calls) == 3
    seen_names = {call["name"] for call in fake.insert_calls}
    assert seen_names == {"a.md", "nested/b.md", "c.md"}
    for call in fake.insert_calls:
        assert set(["file_sha256", "rel_path", "size", "indexed_at_ms"]).issubset(call["metadata"].keys())
        assert call["upsert"] is True
        assert call["skip_if_exists"] is False
        assert call["path"]  # absolute path string
    assert summary.indexed == 3
    assert summary.skipped == 0
    assert summary.errors == 0
    assert summary.total == 3


def test_reindex_skips_unchanged_files(tmp_vault):
    """D-02 + R-04: file whose recorded sha256 matches is skipped (not re-inserted)."""
    from agentos.knowledge import reindex

    a = _write(tmp_vault / "a.md", b"hello a")
    _write(tmp_vault / "b.md", b"hello b")
    _write(tmp_vault / "c.md", b"hello c")

    fake = _FakeKnowledge()
    # pre-seed: a.md is already indexed with correct sha
    fake.contents_db._rows = [
        _FakeKnowledgeRow(name="a.md", metadata={"file_sha256": _sha256(a)}, id_="row-a")
    ]

    summary = reindex(vault_path=tmp_vault, knowledge=fake)

    assert len(fake.insert_calls) == 2
    inserted_names = {c["name"] for c in fake.insert_calls}
    assert inserted_names == {"b.md", "c.md"}
    assert summary.indexed == 2
    assert summary.skipped == 1
    assert summary.errors == 0
    assert summary.total == 3


def test_reindex_continues_on_per_file_error(tmp_vault):
    """D-01c: a bad file does not abort the rest of the run."""
    from agentos.knowledge import reindex

    _write(tmp_vault / "a.md", b"a")
    _write(tmp_vault / "b.md", b"b")
    _write(tmp_vault / "c.md", b"c")

    fake = _FakeKnowledge()
    fake._raise_on_call = 2  # second insert raises

    summary = reindex(vault_path=tmp_vault, knowledge=fake)

    assert len(fake.insert_calls) == 3
    assert summary.indexed == 2
    assert summary.errors == 1
    assert summary.total == 3


def test_reindex_twice_no_duplicate_rows(tmp_vault):
    """KNOW-03 / D-02c: second run inserts nothing; row count stable."""
    from agentos.knowledge import reindex

    _write(tmp_vault / "a.md", b"a")
    _write(tmp_vault / "b.md", b"b")
    _write(tmp_vault / "c.md", b"c")

    fake = _FakeKnowledge()

    s1 = reindex(vault_path=tmp_vault, knowledge=fake)
    assert s1.indexed == 3 and s1.skipped == 0

    s2 = reindex(vault_path=tmp_vault, knowledge=fake)
    assert s2.indexed == 0
    assert s2.skipped == 3
    assert len(fake.rows) == 3


def test_reindex_emits_obs01_log_per_file(tmp_vault, caplog):
    """D-05: one OBS-01 structured log line per indexed file."""
    from agentos.knowledge import reindex

    content = b"hello world"
    _write(tmp_vault / "a.md", content)

    fake = _FakeKnowledge()

    with caplog.at_level(logging.INFO, logger="agentos.knowledge"):
        reindex(vault_path=tmp_vault, knowledge=fake)

    obs_records = [
        r for r in caplog.records
        if r.name == "agentos.knowledge" and r.message.startswith("OBS-01 knowledge write")
    ]
    assert len(obs_records) >= 1
    msg = obs_records[0].message
    payload = json.loads(msg[msg.index("{"):])
    assert payload["path"] == "knowledge"
    assert payload["agent_id"] is None
    assert payload["db_id"] == "ultra-brain-main"
    assert payload["op"] == "index"
    assert payload["rel_path"] == "a.md"
    assert isinstance(payload["sha256"], str) and len(payload["sha256"]) == 64
    assert payload["action"] == "indexed"
    assert payload["content_bytes"] == len(content)
    assert isinstance(payload["latency_ms"], int) and payload["latency_ms"] >= 0
    assert payload["status"] == "ok"
    # row_id may be None for fresh inserts; key must exist
    assert "row_id" in payload


def test_reindex_cli_summary(tmp_vault, capsys, monkeypatch):
    """D-01b: CLI summary line + per-file [indexed] lines."""
    import agentos.knowledge as kmod

    _write(tmp_vault / "a.md", b"a")
    _write(tmp_vault / "b.md", b"b")

    fake = _FakeKnowledge()

    def _fake_make():
        return fake

    monkeypatch.setattr(kmod, "make_knowledge", _fake_make)

    exit_code = kmod.cli_main(["--reindex"])
    assert exit_code == 0

    out = capsys.readouterr().out
    indexed_lines = [ln for ln in out.splitlines() if ln.startswith("[indexed]")]
    assert len(indexed_lines) == 2
    assert re.search(r"^Indexed 2 files \(0 skipped, 0 errors\) in [0-9.]+s$", out, re.M)
