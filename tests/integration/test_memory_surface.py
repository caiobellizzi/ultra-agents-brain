"""MEM-01 / MEM-02 integration tests — drive the same POST shape that the
Telegram adapter uses, but bypass the adapter so the routing/timeout fix in
plan 11-02 is not on this test's critical path.

Empirical baseline: see `.planning/phases/11-memory-surface-activation/evidence/experiment-2026-05-22.md`.
"""
from __future__ import annotations

import os
import time
import uuid

import httpx
import pytest

pytestmark = pytest.mark.live

BASE_URL = os.environ.get("UAB_AGENTOS_URL", "http://31.97.130.253:7000")
SLA_SECONDS = 5
POLL_INTERVAL = 0.5
POLL_MAX = 30  # max 30s — covers a slow first run after deploy


def _post_chat(message: str, user_id: str) -> dict:
    with httpx.Client(timeout=httpx.Timeout(connect=10, read=90, write=10, pool=90)) as client:
        resp = client.post(
            f"{BASE_URL}/agents/chat/runs",
            data={
                "message": message,
                "session_id": f"mem-test-{uuid.uuid4()}",
                "user_id": user_id,
                "stream": "false",
            },
        )
    resp.raise_for_status()
    return resp.json()


def _list_memories(user_id: str) -> list[dict]:
    with httpx.Client(timeout=10) as client:
        resp = client.get(f"{BASE_URL}/memories", params={"user_id": user_id, "limit": 50})
    resp.raise_for_status()
    return resp.json().get("data", [])


def test_mem_01_chat_run_persists_memory_within_5s():
    """MEM-01: a chat-agent run with memory-worthy content must produce
    at least one new memory row keyed by the supplied user_id within the
    SLA window."""
    user_id = f"mem-test-{uuid.uuid4().hex[:8]}"  # unique per run, avoids contamination
    baseline = _list_memories(user_id)
    assert baseline == [], f"unique user_id {user_id} should start with no memories"

    post_started = time.monotonic()
    _post_chat(
        message="My favorite color is teal and I bike to work every Tuesday.",
        user_id=user_id,
    )

    deadline = post_started + POLL_MAX
    memories: list[dict] = []
    first_seen_at = None
    while time.monotonic() < deadline:
        memories = _list_memories(user_id)
        if memories:
            first_seen_at = time.monotonic()
            break
        time.sleep(POLL_INTERVAL)

    elapsed = (first_seen_at or time.monotonic()) - post_started
    assert memories, f"No memory row appeared within {POLL_MAX}s for user_id={user_id}"
    assert elapsed <= SLA_SECONDS, (
        f"MEM-01 SLA violation: memory appeared after {elapsed:.1f}s (budget {SLA_SECONDS}s). "
        f"Row count = {len(memories)}."
    )

    # MEM-02 implicit: the row's user_id should match what we sent.
    assert all(m["user_id"] == user_id for m in memories), \
        f"Unexpected user_id in memory rows: {[m['user_id'] for m in memories]}"


def test_mem_02_db_id_is_pinned():
    """MEM-02: AgentOS reports the pinned db_id from DIAG-BL-01."""
    with httpx.Client(timeout=10) as client:
        resp = client.get(f"{BASE_URL}/config")
    resp.raise_for_status()
    config = resp.json()
    assert config["os_database"] == "ultra-brain-main", (
        f"Expected pinned db_id 'ultra-brain-main', got {config['os_database']!r}"
    )
    assert "ultra-brain-main" in config["databases"], (
        f"databases array missing pin: {config['databases']}"
    )
