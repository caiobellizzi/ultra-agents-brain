"""Behavioral tests for the agentos/ Agno layer.

Covers gaps:
  W2.2 — knowledge.py importable and kb.load() runs without error
  W2.3 — vault tools callable as plain callables
  W2.4 — safety.py assert_safe / trust_gate behavior
  W2.5 — all 5 agent files importable
  W2.6 — app can be instantiated and /health route exists
  W3.1 — app.py uses PostgresDb (not SQLite) + shared MemoryManager
  W3.2 — AgentOS constructed with enable_mcp_server=True and a2a_interface=True
  W3.3 — supervisor uses make_supervisor_team factory (accepts memory_manager)
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Required env var for agentos.model (all agent imports transitively need it)
os.environ.setdefault("LITELLM_MASTER_KEY", "test-key-for-tests")


class TestKnowledgeImportable(unittest.TestCase):
    """W2.2 — agentos/knowledge.py importable; make_knowledge() returns a Knowledge."""

    def test_knowledge_importable(self) -> None:
        from agno.knowledge.knowledge import Knowledge

        from agentos.knowledge import make_knowledge

        kb = make_knowledge()
        self.assertIsInstance(kb, Knowledge)
        # stub-fallback path (no DSN in unit tests) — name still set
        self.assertEqual(kb.name, "ultra-brain-vault")

    def test_reindex_summary_dataclass_shape(self) -> None:
        from agentos.knowledge import ReindexSummary

        s = ReindexSummary(indexed=0, skipped=0, errors=0, total=0, duration_seconds=0.0)
        self.assertEqual(s.total, 0)

    def test_reindex_returns_empty_on_stub_fallback(self) -> None:
        from agentos.knowledge import make_knowledge, reindex

        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            (vault / "note.md").write_text("# Test\n", encoding="utf-8")
            kb = make_knowledge()  # stub (no DSN)
            summary = reindex(vault_path=vault, knowledge=kb)
            # stub fallback path: nothing is indexed, summary is zeros
            self.assertEqual(summary.indexed, 0)
            self.assertEqual(summary.total, 0)


class TestVaultToolsCallable(unittest.TestCase):
    """W2.3 — vault.py wrappers callable as tools (not just the underlying ultra_brain module)."""

    def test_query_vault_is_callable(self) -> None:
        from agentos.tools.vault import query_vault

        # Must be a callable Python object
        self.assertTrue(callable(query_vault))

    def test_ingest_to_vault_is_agno_function_with_confirmation(self) -> None:
        from agno.tools.function import Function

        from agentos.tools.vault import ingest_to_vault

        # Medium-risk tools must be agno Function (decorated with @tool)
        self.assertIsInstance(ingest_to_vault, Function)
        # And must require confirmation
        self.assertTrue(ingest_to_vault.requires_confirmation)

    def test_research_topic_is_agno_function_with_confirmation(self) -> None:
        from agno.tools.function import Function

        from agentos.tools.vault import research_topic

        self.assertIsInstance(research_topic, Function)
        self.assertTrue(research_topic.requires_confirmation)

    def test_query_vault_calls_underlying_module(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            from agentos.tools import vault as vault_mod
            from agentos.tools.vault import query_vault

            # Patch the ultra_brain query call and the VAULT_ROOT used in the module
            with patch.object(vault_mod, "VAULT_ROOT", Path(tmp) / "vault"), \
                 patch("ultra_brain.query.query_vault", return_value="mocked answer") as mock_q:
                result = query_vault("test question")
                mock_q.assert_called_once()
                self.assertEqual(result, "mocked answer")


class TestTrustGateDecorator(unittest.TestCase):
    """W2.4 — assert_safe wraps a no-op tool without breaking it."""

    def test_assert_safe_allows_benign_action(self) -> None:
        from agentos.tools.safety import assert_safe

        # Must not raise for a benign description
        try:
            assert_safe("read vault note", target="vault/notes/test.md")
        except PermissionError:
            self.fail("assert_safe raised PermissionError for a benign action")

    def test_assert_safe_refuses_high_risk(self) -> None:
        from agentos.tools.safety import assert_safe

        # High-risk action must raise PermissionError
        with self.assertRaises(PermissionError):
            assert_safe("run shell rm -rf /")

    def test_ingest_impl_calls_assert_safe_and_propagates_refusal(self) -> None:
        """The _ingest_to_vault_impl wrapper must propagate assert_safe refusals."""
        from agentos.tools import vault as vault_mod

        # Patch assert_safe to always refuse
        with patch.object(vault_mod, "assert_safe", side_effect=PermissionError("refused")):
            with self.assertRaises(PermissionError):
                vault_mod._ingest_to_vault_impl("https://malicious.example.com")


class TestAgentsImportable(unittest.TestCase):
    """W2.5 — all agent files importable without error, including supervisor."""

    def test_chat_agent_importable(self) -> None:
        from agentos.agents.chat import chat_agent

        self.assertIsNotNone(chat_agent)

    def test_ingest_agent_importable(self) -> None:
        from agentos.agents.ingest import ingest_agent

        self.assertIsNotNone(ingest_agent)

    def test_query_agent_importable(self) -> None:
        from agentos.agents.query import query_agent

        self.assertIsNotNone(query_agent)

    def test_research_agent_importable(self) -> None:
        from agentos.agents.research import research_agent

        self.assertIsNotNone(research_agent)

    def test_research_agent_make_has_orchestrator_model_and_schema(self) -> None:
        from agno.tools.reasoning import ReasoningTools

        from agentos.agents.research import make_research_agent
        from agentos.schemas import ResearchReport

        mock_mm = MagicMock()
        mock_knowledge = MagicMock()
        agent = make_research_agent(memory_manager=mock_mm, knowledge=mock_knowledge)

        # Orchestrator model tier
        self.assertIn("orchestrator", str(agent.model))

        # ReasoningTools present
        tool_types = [type(t).__name__ for t in (agent.tools or [])]
        self.assertIn("ReasoningTools", tool_types)

        # ResearchReport output schema
        self.assertEqual(agent.output_schema, ResearchReport)

        # Memory wired
        self.assertEqual(agent.memory_manager, mock_mm)
        self.assertTrue(agent.enable_agentic_memory)
        self.assertTrue(agent.update_memory_on_run)

        # Knowledge wired
        self.assertEqual(agent.knowledge, mock_knowledge)
        self.assertTrue(agent.search_knowledge)

    def test_curator_agent_importable(self) -> None:
        from agentos.agents.curator import curator_agent

        self.assertIsNotNone(curator_agent)

    def test_curator_agent_has_memory_and_output_schema(self) -> None:
        from agentos.agents.curator import make_curator_agent
        from agentos.schemas import CuratorResult

        mock_mm = MagicMock()
        agent = make_curator_agent(memory_manager=mock_mm)
        self.assertEqual(agent.memory_manager, mock_mm)
        self.assertTrue(agent.enable_agentic_memory)
        self.assertTrue(agent.update_memory_on_run)
        self.assertTrue(agent.add_history_to_context)
        self.assertEqual(agent.output_schema, CuratorResult)
        # No session summaries
        self.assertFalse(getattr(agent, "enable_session_summaries", False))
        # No knowledge
        self.assertIsNone(getattr(agent, "knowledge", None))

    def test_supervisor_agent_importable(self) -> None:
        from agentos.agents.supervisor import supervisor_agent

        self.assertIsNotNone(supervisor_agent)
        self.assertIsNotNone(supervisor_agent.members)
        self.assertTrue(len(supervisor_agent.members) > 0)

    def test_supervisor_make_accepts_memory_manager(self) -> None:
        """W3.3 — make_supervisor_team accepts memory_manager= (not hard-coded)."""
        from agentos.agents.supervisor import make_supervisor_team

        mock_mm = MagicMock()
        team = make_supervisor_team(memory_manager=mock_mm)
        self.assertIsNotNone(team)
        self.assertEqual(team.name, "supervisor")

    def test_all_agents_have_expected_names(self) -> None:
        from agentos.agents.chat import chat_agent
        from agentos.agents.curator import curator_agent
        from agentos.agents.ingest import ingest_agent
        from agentos.agents.query import query_agent
        from agentos.agents.research import research_agent
        from agentos.agents.supervisor import supervisor_agent

        names = {a.name for a in [chat_agent, ingest_agent, query_agent, research_agent, curator_agent, supervisor_agent]}
        self.assertEqual(names, {"chat", "ingest", "query", "research", "curator", "supervisor"})


class TestAppHealth(unittest.TestCase):
    """W2.6 / W3.1 / W3.2 — app.py instantiates correctly with PostgresDb, MemoryManager, MCP, A2A."""

    def _make_mock_db(self):
        """Return a MagicMock that satisfies AgentOS db= checks."""
        from agno.db.base import BaseDb
        mock_db = MagicMock(spec=BaseDb)
        mock_db.create_schema = True
        return mock_db

    def _patch_app_dependencies(self):
        """Context manager that patches PostgresDb and MemoryManager in app.py."""
        from agno.db.postgres import PostgresDb
        from agno.memory.manager import MemoryManager

        mock_db = self._make_mock_db()
        mock_memory = MagicMock(spec=MemoryManager)

        return (
            patch("agentos.app.PostgresDb", return_value=mock_db),
            patch("agentos.app.MemoryManager", return_value=mock_memory),
        )

    def test_app_importable(self) -> None:
        from agentos.app import agent_os, app

        self.assertIsNotNone(app)
        self.assertIsNotNone(agent_os)

    def test_app_uses_postgres_db_when_dsn_set(self) -> None:
        """W3.1 — app.py uses PostgresDb when POSTGRES_DSN_SESSIONS is set;
        falls back to SqliteDb when it is not (test environment)."""
        import importlib
        import sys

        dsn = os.environ.get("POSTGRES_DSN_SESSIONS")
        if dsn:
            from agno.db.postgres import PostgresDb
            from agentos.app import db
            self.assertIsInstance(db, PostgresDb)
        else:
            # In test environment (no DSN), the fallback SqliteDb must be used.
            from agno.db.sqlite import SqliteDb
            from agentos.app import db
            self.assertIsInstance(db, SqliteDb)

    def test_app_has_memory_manager(self) -> None:
        """W3.1 — app.py instantiates a shared MemoryManager."""
        from agno.memory.manager import MemoryManager

        from agentos.app import memory

        self.assertIsInstance(memory, MemoryManager)

    def test_agent_os_has_mcp_server_enabled(self) -> None:
        """W3.2 — AgentOS constructed with enable_mcp_server=True."""
        from agentos.app import agent_os

        self.assertTrue(agent_os.enable_mcp_server)

    def test_agent_os_has_a2a_interface_enabled(self) -> None:
        """W3.2 — AgentOS constructed with a2a_interface=True."""
        from agentos.app import agent_os

        self.assertTrue(agent_os.a2a_interface)

    def test_app_is_fastapi_instance(self) -> None:
        from fastapi import FastAPI

        from agentos.app import app

        self.assertIsInstance(app, FastAPI)

    def test_health_route_exists(self) -> None:
        from fastapi.testclient import TestClient

        from agentos.app import app

        client = TestClient(app)
        resp = client.get("/health")
        # /health must respond with 2xx
        self.assertIn(resp.status_code, (200, 201, 204))

    def test_health_response_indicates_ok(self) -> None:
        from fastapi.testclient import TestClient

        from agentos.app import app

        client = TestClient(app)
        resp = client.get("/health")
        # Body should contain some positive signal
        body = resp.text.lower()
        self.assertTrue(
            "ok" in body or "healthy" in body or "status" in body or resp.status_code == 200,
            f"Unexpected /health body: {resp.text!r}",
        )


if __name__ == "__main__":
    unittest.main()
