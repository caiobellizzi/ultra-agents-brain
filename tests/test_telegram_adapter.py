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

    def test_plain_text_routes_to_chat(self):
        agent = self.mod._agent_id_for("Hello, how are you?")
        self.assertEqual(agent, "chat")

    def test_ingest_command_routes_to_ingest(self):
        agent = self.mod._agent_id_for("/ingest https://example.com/page")
        self.assertEqual(agent, "ingest")

    def test_query_command_routes_to_query(self):
        agent = self.mod._agent_id_for("/query what is consciousness?")
        self.assertEqual(agent, "query")

    def test_research_command_routes_to_research(self):
        agent = self.mod._agent_id_for("/research AI agent observability")
        self.assertEqual(agent, "research")

    def test_unknown_command_falls_back_to_chat(self):
        agent = self.mod._agent_id_for("/unknown something")
        self.assertEqual(agent, "chat")

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
        client.get = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"data": [{"id": "ap-cv", "tool_execution": {"tool_call_id": ""}, "status": "pending"}]},
        ))
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


class TestApproveDoubleTap(unittest.TestCase):
    """Regression — duplicate Approve callbacks must only POST once and must
    not surface AgentOS 409 'already continued' to the user."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _import_adapter_with_env()

    def setUp(self):
        # Clear module-level state between tests
        self.mod._RESOLVED_RUNS.clear()
        self.mod._PAUSED_TOOLS.clear()

    def _query(self, run_id: str, action: str = "approve") -> dict:
        tool_call_id = "abcdef01-abcd-abcd-abcd-abcdef012345"
        return {
            "id": "cq-dup",
            "message": {"chat": {"id": 999}},
            "from": {"id": 999},
            "data": f"{action}:{run_id}:ingest:{tool_call_id}",
        }

    def test_second_callback_skips_post_entirely(self):
        """First callback POSTs; second is silently dropped by _RESOLVED_RUNS guard."""
        import asyncio

        run_id = "11111111-2222-3333-4444-555555555555"
        client = AsyncMock()
        client.get = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"data": [{"id": "ap-x", "tool_execution": {"tool_call_id": "abcdef01-abcd-abcd-abcd-abcdef012345"}, "status": "pending"}]},
        ))
        client.post = AsyncMock(return_value=MagicMock(
            status_code=200, json=lambda: {"content": "ok"}, text=""
        ))

        asyncio.run(self.mod.handle_callback(client, self._query(run_id)))
        asyncio.run(self.mod.handle_callback(client, self._query(run_id)))

        continue_calls = [c for c in client.post.call_args_list if "continue" in str(c)]
        self.assertEqual(len(continue_calls), 1, "Second callback must not POST /continue again")
        self.assertIn(run_id, self.mod._RESOLVED_RUNS)

    def test_409_already_continued_is_swallowed(self):
        """If the POST itself returns 409 'already continued' (race won by another callback),
        the user must NOT see an 'AgentOS error resuming run' message."""
        import asyncio

        run_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        # 1st call to client.post = answerCallbackQuery (200)
        # 2nd call = /continue (409 with "already continued" body)
        client = AsyncMock()
        client.get = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"data": [{"id": "ap-y", "tool_execution": {"tool_call_id": "abcdef01-abcd-abcd-abcd-abcdef012345"}, "status": "pending"}]},
        ))

        async def _post(url, *args, **kwargs):
            if "continue" in url:
                return MagicMock(
                    status_code=409,
                    text='{"detail":"run is already continued"}',
                    json=lambda: {"detail": "run is already continued"},
                )
            return MagicMock(status_code=200, json=lambda: {})

        client.post = AsyncMock(side_effect=_post)

        # Capture send_message calls — must not include an "error resuming" line
        sent: list[str] = []
        original_send = self.mod.send_message

        async def fake_send(c, chat_id, text):
            sent.append(text)

        self.mod.send_message = fake_send
        try:
            asyncio.run(self.mod.handle_callback(client, self._query(run_id)))
        finally:
            self.mod.send_message = original_send

        error_msgs = [m for m in sent if "error resuming" in m.lower()]
        self.assertEqual(error_msgs, [], f"409 'already continued' should be silent; got: {sent}")

    def test_non_409_error_releases_resolved_marker_for_retry(self):
        """If /continue fails with a real (non-409) error, the run_id must be
        removed from _RESOLVED_RUNS so the user can tap again to retry."""
        import asyncio

        run_id = "99999999-8888-7777-6666-555555555555"
        client = AsyncMock()
        client.get = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"data": [{"id": "ap-z", "tool_execution": {"tool_call_id": "abcdef01-abcd-abcd-abcd-abcdef012345"}, "status": "pending"}]},
        ))

        async def _post(url, *args, **kwargs):
            if "continue" in url:
                return MagicMock(status_code=500, text="boom", json=lambda: {})
            return MagicMock(status_code=200, json=lambda: {})

        client.post = AsyncMock(side_effect=_post)

        original_send = self.mod.send_message
        self.mod.send_message = AsyncMock()
        try:
            asyncio.run(self.mod.handle_callback(client, self._query(run_id)))
        finally:
            self.mod.send_message = original_send

        self.assertNotIn(run_id, self.mod._RESOLVED_RUNS,
                          "Non-409 errors must release the marker so retry works")


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


class TestApprovalBridge(unittest.TestCase):
    """APPR-02 — _resolve_approval_row wired into handle_callback.

    Tests:
      14-02-01: approve callback calls POST /approvals/{id}/resolve with status='approved' BEFORE /continue
      14-02-02: deny callback calls POST /approvals/{id}/resolve with status='rejected' BEFORE /continue
      14-02-03: resolve failure (500) releases _RESOLVED_RUNS guard, sends Telegram error, skips /continue
      14-02-04: 409 on resolve is treated as idempotent success — /continue IS called
    """

    RUN_ID = "aaaabbbb-cccc-dddd-eeee-ffffffffffff"
    AGENT_ID = "ingest"
    TOOL_CALL_ID = "00010002-0003-0004-0005-000600070008"
    APPROVAL_ID = "ap-001"
    CHAT_ID = 123456
    TG_USER_ID = 123456

    @classmethod
    def setUpClass(cls):
        cls.mod = _import_adapter_with_env()

    def setUp(self):
        self.mod._RESOLVED_RUNS.clear()
        self.mod._PAUSED_TOOLS.clear()
        # Pre-populate _PAUSED_TOOLS so handle_callback has a cached tool
        self.mod._PAUSED_TOOLS[self.RUN_ID] = [
            {
                "tool_call_id": self.TOOL_CALL_ID,
                "tool_name": "save_note",
                "tool_args": {},
                "run_id": self.RUN_ID,
                "requires_confirmation": True,
            }
        ]

    def _query(self, action: str = "approve") -> dict:
        return {
            "id": "cq-bridge",
            "message": {"chat": {"id": self.CHAT_ID}},
            "from": {"id": self.TG_USER_ID},
            "data": f"{action}:{self.RUN_ID}:{self.AGENT_ID}:{self.TOOL_CALL_ID}",
        }

    def _make_client(self, resolve_status: int = 200) -> tuple:
        """Return (client, call_log) where call_log tracks (method, url) pairs in order."""
        import asyncio

        call_log: list[tuple[str, str]] = []

        approvals_get_response = MagicMock(
            status_code=200,
            json=lambda: {
                "data": [
                    {
                        "id": self.APPROVAL_ID,
                        "tool_execution": {"tool_call_id": self.TOOL_CALL_ID},
                        "status": "pending",
                    }
                ]
            },
        )

        def _resolve_response():
            return MagicMock(
                status_code=resolve_status,
                text='{"detail":"already resolved"}' if resolve_status == 409 else "{}",
                json=lambda: {},
            )

        continue_response = MagicMock(
            status_code=200,
            text="{}",
            json=lambda: {"run_status": "completed", "content": []},
        )

        tg_response = MagicMock(status_code=200, json=lambda: {})

        async def _get(url, **kwargs):
            call_log.append(("GET", url))
            if "approvals" in url:
                return approvals_get_response
            return MagicMock(status_code=200, json=lambda: {})

        async def _post(url, **kwargs):
            call_log.append(("POST", url))
            if "answerCallbackQuery" in url:
                return tg_response
            if "sendMessage" in url:
                return tg_response
            if f"approvals/{self.APPROVAL_ID}/resolve" in url:
                return _resolve_response()
            if "continue" in url:
                return continue_response
            return MagicMock(status_code=200, json=lambda: {})

        client = MagicMock()
        client.get = AsyncMock(side_effect=_get)
        client.post = AsyncMock(side_effect=_post)
        return client, call_log

    def test_approve_resolves_then_continues(self):
        """14-02-01: approve calls POST /approvals/ap-001/resolve(status=approved) then /continue."""
        import asyncio

        client, call_log = self._make_client(resolve_status=200)

        # Capture resolve body
        resolve_bodies: list[dict] = []
        original_post = client.post.side_effect

        async def _post_capturing(url, **kwargs):
            if f"approvals/{self.APPROVAL_ID}/resolve" in url:
                resolve_bodies.append(kwargs.get("json", {}))
            return await original_post(url, **kwargs)

        client.post.side_effect = _post_capturing

        asyncio.run(self.mod.handle_callback(client, self._query("approve")))

        # Assert resolve was called with status='approved'
        self.assertTrue(
            len(resolve_bodies) > 0,
            "POST /approvals/{id}/resolve was never called",
        )
        self.assertEqual(resolve_bodies[0].get("status"), "approved")

        # Assert /continue was called
        continue_calls = [url for method, url in call_log if "continue" in url]
        self.assertTrue(len(continue_calls) > 0, "/continue was not called after resolve")

        # Assert resolve came BEFORE continue (call order check)
        resolve_idx = next(
            (i for i, (m, u) in enumerate(call_log) if f"approvals/{self.APPROVAL_ID}/resolve" in u),
            None,
        )
        continue_idx = next(
            (i for i, (m, u) in enumerate(call_log) if "continue" in u),
            None,
        )
        self.assertIsNotNone(resolve_idx, "resolve call not found in call_log")
        self.assertIsNotNone(continue_idx, "/continue call not found in call_log")
        self.assertLess(resolve_idx, continue_idx, "resolve must happen BEFORE /continue")

    def test_deny_resolves_rejected(self):
        """14-02-02: deny calls POST /approvals/ap-001/resolve(status=rejected) then /continue."""
        import asyncio

        client, call_log = self._make_client(resolve_status=200)

        resolve_bodies: list[dict] = []
        original_post = client.post.side_effect

        async def _post_capturing(url, **kwargs):
            if f"approvals/{self.APPROVAL_ID}/resolve" in url:
                resolve_bodies.append(kwargs.get("json", {}))
            return await original_post(url, **kwargs)

        client.post.side_effect = _post_capturing

        asyncio.run(self.mod.handle_callback(client, self._query("deny")))

        self.assertTrue(len(resolve_bodies) > 0, "POST /approvals/{id}/resolve was never called")
        self.assertEqual(resolve_bodies[0].get("status"), "rejected")

        # /continue must still be called even on deny
        continue_calls = [url for method, url in call_log if "continue" in url]
        self.assertTrue(len(continue_calls) > 0, "/continue must be called even on deny")

    def test_resolve_failure_releases_guard(self):
        """14-02-03: resolve 500 → skip /continue, release _RESOLVED_RUNS, send Telegram error."""
        import asyncio

        client, call_log = self._make_client(resolve_status=500)

        sent_messages: list[str] = []
        original_send = self.mod.send_message

        async def _fake_send(c, chat_id, text):
            sent_messages.append(text)

        self.mod.send_message = _fake_send
        try:
            asyncio.run(self.mod.handle_callback(client, self._query("approve")))
        finally:
            self.mod.send_message = original_send

        # /continue must NOT have been called
        continue_calls = [url for method, url in call_log if "continue" in url]
        self.assertEqual(continue_calls, [], "/continue must NOT be called when resolve fails")

        # _RESOLVED_RUNS guard must be released
        self.assertNotIn(
            self.RUN_ID,
            self.mod._RESOLVED_RUNS,
            "_RESOLVED_RUNS guard must be released on resolve failure for retry",
        )

        # Telegram error message must be sent
        self.assertTrue(
            len(sent_messages) > 0,
            "Telegram error message must be sent when resolve fails",
        )

    def test_resolve_409_is_ok(self):
        """14-02-04: 409 on resolve is idempotent success — /continue IS called."""
        import asyncio

        client, call_log = self._make_client(resolve_status=409)

        asyncio.run(self.mod.handle_callback(client, self._query("approve")))

        # /continue must be called (409 treated as success)
        continue_calls = [url for method, url in call_log if "continue" in url]
        self.assertTrue(
            len(continue_calls) > 0,
            "/continue must be called when resolve returns 409 (idempotent)",
        )


class TestRouteMessageReplyExtraction(unittest.TestCase):
    """Regression — current Agno run payloads use content, not output."""

    @classmethod
    def setUpClass(cls):
        cls.mod = _import_adapter_with_env()

    def _run_route_message(self, payload: dict) -> list[str]:
        import asyncio

        client = AsyncMock()
        client.post = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: payload))

        sent: list[str] = []
        original_send = self.mod.send_message

        async def fake_send(c, chat_id, text, reply_markup=None):
            sent.append(text)

        self.mod.send_message = fake_send
        try:
            asyncio.run(self.mod.route_message(client, "hello", 123, 456))
        finally:
            self.mod.send_message = original_send
        return sent

    def test_route_message_sends_current_agno_content_text(self):
        sent = self._run_route_message({"content": {"text": "hello from content"}, "status": "COMPLETED"})
        self.assertEqual(sent, ["hello from content"])

    def test_route_message_never_sends_literal_empty_object(self):
        sent = self._run_route_message({"content": {}, "status": "COMPLETED"})
        self.assertEqual(sent, ["AgentOS completed but returned no reply text."])


if __name__ == "__main__":
    unittest.main()
