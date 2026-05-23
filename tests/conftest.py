"""Shared pytest fixtures for ultra-agents-brain tests."""
from __future__ import annotations

import os

import pytest

# Required env var for agentos.model (transitively imported by many tests)
os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-tests")


@pytest.fixture
def tmp_vault(tmp_path, monkeypatch):
    """Empty tmp vault dir with VAULT_PATH env var set to it."""
    v = tmp_path / "vault"
    v.mkdir()
    monkeypatch.setenv("VAULT_PATH", str(v))
    return v


@pytest.fixture
def live_postgres_dsn_knowledge():
    """Live POSTGRES_DSN_KNOWLEDGE; skip test if unset."""
    dsn = os.getenv("POSTGRES_DSN_KNOWLEDGE")
    if not dsn:
        pytest.skip("POSTGRES_DSN_KNOWLEDGE not set; skipping live test.")
    return dsn


@pytest.fixture
def live_postgres_dsn_sessions():
    """Live POSTGRES_DSN_SESSIONS; skip test if unset."""
    dsn = os.getenv("POSTGRES_DSN_SESSIONS")
    if not dsn:
        pytest.skip("POSTGRES_DSN_SESSIONS not set; skipping live test.")
    return dsn
