import logging

import pytest

from agentos.instrumented_memory import InstrumentedMemoryManager


class _FakeDb:
    def __init__(self, id_="ultra-brain-main"):
        self.id = id_
        self._rows = {}

    def get_user_memories(self, user_id=None):
        return list(self._rows.get(user_id, []))


def _mgr(db=None):
    m = InstrumentedMemoryManager.__new__(InstrumentedMemoryManager)
    m.db = db or _FakeDb()
    return m


def test_update_memory_task_emits_obs01_on_success(monkeypatch, caplog):
    mgr = _mgr()
    monkeypatch.setattr(
        "agno.memory.manager.MemoryManager.update_memory_task",
        lambda self, task, user_id=None: "ok",
    )
    with caplog.at_level(logging.INFO, logger="agentos.memory"):
        out = mgr.update_memory_task(task="remember teal", user_id="u1")
    assert out == "ok"
    msgs = [r.message for r in caplog.records if "OBS-01 memory write" in r.message]
    assert len(msgs) == 1
    assert '"path": "memory"' in msgs[0]
    assert '"user_id": "u1"' in msgs[0]
    assert '"db_id": "ultra-brain-main"' in msgs[0]
    assert '"status": "ok"' in msgs[0]


def test_update_memory_task_emits_obs01_on_error(monkeypatch, caplog):
    mgr = _mgr()

    def _boom(self, task, user_id=None):
        raise RuntimeError("boom")

    monkeypatch.setattr("agno.memory.manager.MemoryManager.update_memory_task", _boom)
    with caplog.at_level(logging.ERROR, logger="agentos.memory"):
        with pytest.raises(RuntimeError):
            mgr.update_memory_task(task="x", user_id="u1")
    msgs = [r.message for r in caplog.records if "OBS-01 memory write failed" in r.message]
    assert len(msgs) == 1
    assert '"status": "error"' in msgs[0]
    assert '"error_type": "RuntimeError"' in msgs[0]


@pytest.mark.asyncio
async def test_aupdate_memory_task_emits_obs01_on_success(monkeypatch, caplog):
    mgr = _mgr()

    async def _ok(self, task, user_id=None):
        return "ok"

    monkeypatch.setattr("agno.memory.manager.MemoryManager.aupdate_memory_task", _ok)
    with caplog.at_level(logging.INFO, logger="agentos.memory"):
        out = await mgr.aupdate_memory_task(task="t", user_id="u1")
    assert out == "ok"
    assert any("OBS-01 memory write" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_aupdate_memory_task_emits_obs01_on_error(monkeypatch, caplog):
    mgr = _mgr()

    async def _boom(self, task, user_id=None):
        raise ValueError("nope")

    monkeypatch.setattr("agno.memory.manager.MemoryManager.aupdate_memory_task", _boom)
    with caplog.at_level(logging.ERROR, logger="agentos.memory"):
        with pytest.raises(ValueError):
            await mgr.aupdate_memory_task(task="t", user_id="u1")
    assert any("OBS-01 memory write failed" in r.message for r in caplog.records)
