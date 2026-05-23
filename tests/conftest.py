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
