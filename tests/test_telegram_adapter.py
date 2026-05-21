"""Behavioral tests for channels/telegram_adapter.py.

Covers gaps:
  W3.1  — routing logic: text → chat, /ingest → ingest, /query → query, /research → research
  SEC.1 — fails fast when TELEGRAM_ALLOWED_CHAT_IDS is empty (no OPEN_TO_ALL escape)
  SEC.2 — callback_data validation: approve/deny:{uuid} accepted, arbitrary strings rejected
"""
from __future__ import annotations

import importlib
import os
import re
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers to import the module under controlled env
# ---------------------------------------------------------------------------

def _import_adapter_with_env(**env_overrides):
    """Import (or re-import) telegram_adapter with the given env vars set."""
    # Remove cached module so module-level code re-runs
    for key in list(sys.modules):
        if "telegram_adapter" in key:
            del sys.modules[key]

    env = {
        "TELEGRAM_BOT_TOKEN": "fake-token",
        "TELEGRAM_ALLOWED_CHAT_IDS": "123456",
        **env_overrides,
    }
    with patch.dict(os.environ, env, clear=False):
        import channels.telegram_adapter as mod
    return mod


class TestRoutingLogic(unittest.TestCase):
    """W3.1 — text → chat, /ingest → ingest, /query → query, /research → research."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _import_adapter_with_env()

    def test_plain_text_routes_to_supervisor(self):
        agent = self.mod._agent_id_for("Hello, how are you?")
        self.assertEqual(agent, "supervisor")

    def test_ingest_command_routes_to_ingest(self):
        agent = self.mod._agent_id_for("/ingest https://example.com/page")
        self.assertEqual(agent, "ingest")

    def test_query_command_routes_to_query(self):
        agent = self.mod._agent_id_for("/query what is consciousness?")
        self.assertEqual(agent, "query")

    def test_research_command_routes_to_research(self):
        agent = self.mod._agent_id_for("/research AI agent observability")
        self.assertEqual(agent, "research")

    def test_unknown_command_falls_back_to_supervisor(self):
        agent = self.mod._agent_id_for("/unknown something")
        self.assertEqual(agent, "supervisor")

    def test_command_prefix_stripped_from_body(self):
        body = self.mod._message_body("/ingest https://example.com", "ingest")
        self.assertEqual(body, "https://example.com")

    def test_chat_body_unchanged(self):
        body = self.mod._message_body("tell me something", "chat")
        self.assertEqual(body, "tell me something")

    def test_query_prefix_stripped(self):
        body = self.mod._message_body("/query what is X?", "query")
        self.assertEqual(body, "what is X?")

    def test_research_prefix_stripped(self):
        body = self.mod._message_body("/research some topic", "research")
        self.assertEqual(body, "some topic")


class TestEmptyAllowlistRaises(unittest.TestCase):
    """SEC.1 — module-level import raises when TELEGRAM_ALLOWED_CHAT_IDS is empty
    and TELEGRAM_OPEN_TO_ALL is not set."""

    def _reimport(self, **env):
        for key in list(sys.modules):
            if "telegram_adapter" in key:
                del sys.modules[key]
        # Patch out dotenv load so it doesn't pick up .env file
        with patch("dotenv.load_dotenv"), patch.dict(os.environ, env, clear=True):
            import channels.telegram_adapter  # noqa: F401

    def test_empty_allowlist_without_open_flag_raises(self):
        with self.assertRaises((RuntimeError, KeyError)):
            self._reimport(
                TELEGRAM_BOT_TOKEN="fake-token",
                TELEGRAM_ALLOWED_CHAT_IDS="",
                # TELEGRAM_OPEN_TO_ALL not set
            )

    def test_empty_allowlist_with_open_flag_does_not_raise(self):
        # TELEGRAM_OPEN_TO_ALL=1 is the documented escape hatch — must not raise
        try:
            self._reimport(
                TELEGRAM_BOT_TOKEN="fake-token",
                TELEGRAM_ALLOWED_CHAT_IDS="",
                TELEGRAM_OPEN_TO_ALL="1",
            )
        except (RuntimeError, KeyError) as exc:
            self.fail(f"Should not raise when TELEGRAM_OPEN_TO_ALL=1, got: {exc}")

    def test_populated_allowlist_does_not_raise(self):
        try:
            self._reimport(
                TELEGRAM_BOT_TOKEN="fake-token",
                TELEGRAM_ALLOWED_CHAT_IDS="111222333",
            )
        except (RuntimeError, KeyError) as exc:
            self.fail(f"Should not raise for valid allowlist, got: {exc}")


class TestCallbackDataValidation(unittest.TestCase):
    """SEC.2 — callback_data validation: approve/deny:{uuid} accepted, arbitrary strings rejected."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _import_adapter_with_env()

    def _make_callback_query(self, data: str, chat_id: int = 123456) -> dict:
        return {
            "id": "cq-1",
            "message": {"chat": {"id": chat_id}},
            "from": {"id": chat_id},
            "data": data,
        }

    def _run_handle_callback(self, data: str) -> tuple[bool, str | None]:
        """Run handle_callback with a mocked HTTP client.

        Returns (network_call_made, warning_logged).
        The continue endpoint call is the signal that validation passed.
        """
        import asyncio

        client = AsyncMock()
        # answerCallbackQuery — always succeeds
        client.post = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"content": "done"},
        ))

        query = self._make_callback_query(data)
        log_warnings = []

        original_warning = self.mod.log.warning

        def capture_warning(msg, *args):
            log_warnings.append(msg % args if args else msg)

        self.mod.log.warning = capture_warning
        try:
            asyncio.run(self.mod.handle_callback(client, query))
        finally:
            self.mod.log.warning = original_warning

        # Count how many times client.post was called with the /continue URL
        continue_calls = [
            call for call in client.post.call_args_list
            if "continue" in str(call)
        ]
        return len(continue_calls) > 0, log_warnings

    def test_valid_approve_with_uuid_is_accepted(self):
        valid_uuid = "12345678-1234-1234-1234-123456789abc"
        data = f"approve:{valid_uuid}:chat:abcdef01-abcd-abcd-abcd-abcdef012345"
        continued, warnings = self._run_handle_callback(data)
        # No warning about invalid shape or unknown agent
        shape_warnings = [w for w in warnings if "Unexpected callback_data shape" in w or "invalid run_id" in w]
        self.assertEqual(shape_warnings, [], f"Unexpected validation rejection: {warnings}")

    def test_valid_deny_with_uuid_is_accepted(self):
        valid_uuid = "12345678-1234-1234-1234-123456789abc"
        data = f"deny:{valid_uuid}:ingest:abcdef01-abcd-abcd-abcd-abcdef012345"
        continued, warnings = self._run_handle_callback(data)
        shape_warnings = [w for w in warnings if "Unexpected callback_data shape" in w or "invalid run_id" in w]
        self.assertEqual(shape_warnings, [], f"Unexpected validation rejection: {warnings}")

    def test_arbitrary_string_is_rejected(self):
        data = "click-me-for-free-coins"
        continued, warnings = self._run_handle_callback(data)
        # Must log a warning about unexpected shape
        shape_warnings = [w for w in warnings if "Unexpected callback_data shape" in w]
        self.assertTrue(len(shape_warnings) > 0, f"Expected shape warning, got: {warnings}")
        # Must NOT proceed to the continue endpoint
        self.assertFalse(continued, "Should not have called /continue for arbitrary data")

    def test_non_uuid_run_id_is_rejected(self):
        data = "approve:not-a-uuid:chat:not-a-uuid-either"
        continued, warnings = self._run_handle_callback(data)
        invalid_warnings = [w for w in warnings if "invalid run_id" in w]
        self.assertTrue(len(invalid_warnings) > 0, f"Expected invalid run_id warning, got: {warnings}")
        self.assertFalse(continued, "Should not have called /continue for non-UUID run_id")

    def test_unknown_agent_id_is_rejected(self):
        valid_uuid = "12345678-1234-1234-1234-123456789abc"
        data = f"approve:{valid_uuid}:EVIL_AGENT:{valid_uuid}"
        continued, warnings = self._run_handle_callback(data)
        agent_warnings = [w for w in warnings if "unknown agent_id" in w]
        self.assertTrue(len(agent_warnings) > 0, f"Expected unknown agent_id warning, got: {warnings}")
        self.assertFalse(continued, "Should not have called /continue for unknown agent_id")

    def test_five_part_data_rejected_as_wrong_shape(self):
        # Too many colons
        data = "approve:uuid:chat:tool_id:extra"
        continued, warnings = self._run_handle_callback(data)
        shape_warnings = [w for w in warnings if "Unexpected callback_data shape" in w]
        self.assertTrue(len(shape_warnings) > 0, f"Expected shape warning, got: {warnings}")


class TestExtractReplyText(unittest.TestCase):
    """Tests for extract_reply_text() and format_citations() typed response extraction."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _import_adapter_with_env()

    def test_extract_chat_reply_text_field(self):
        response = {"output": {"text": "Here is what I found.", "citations": [{"title": "Note 1", "path": "vault/note1.md", "tags": []}]}}
        self.assertEqual(self.mod.extract_reply_text(response), "Here is what I found.")

    def test_extract_query_answer_field(self):
        response = {"output": {"answer": "42", "citations": [], "confidence": 0.9}}
        self.assertEqual(self.mod.extract_reply_text(response), "42")

    def test_extract_research_report_findings(self):
        response = {"output": {"findings": [{"summary": "Finding 1"}, {"summary": "Finding 2"}], "next_questions": ["Q1?"]}}
        result = self.mod.extract_reply_text(response)
        self.assertIn("Finding 1", result)
        self.assertIn("Finding 2", result)
        self.assertIn("Q1?", result)

    def test_extract_ingest_result_note_path(self):
        response = {"output": {"note_path": "vault/note.md", "actions_taken": []}}
        result = self.mod.extract_reply_text(response)
        self.assertIn("vault/note.md", result)

    def test_extract_curator_result_actions_taken(self):
        response = {"output": {"actions_taken": ["archived note", "tagged entry"]}}
        result = self.mod.extract_reply_text(response)
        self.assertIn("archived note", result)

    def test_fallback_string_output(self):
        response = {"output": "plain string"}
        self.assertEqual(self.mod.extract_reply_text(response), "plain string")

    def test_format_citations_empty_returns_empty_string(self):
        self.assertEqual(self.mod.format_citations([]), "")

    def test_format_citations_with_titles(self):
        citations = [{"title": "My Note", "path": "vault/my-note.md"}]
        result = self.mod.format_citations(citations)
        self.assertIn("My Note", result)
        self.assertIn("_Sources:_", result)

    def test_format_citations_caps_at_three(self):
        citations = [{"title": f"Note {i}"} for i in range(6)]
        result = self.mod.format_citations(citations)
        self.assertIn("Note 0", result)
        self.assertNotIn("Note 3", result)


if __name__ == "__main__":
    unittest.main()
