"""Unit tests for agentos/approval_recorder.py (OBS-01 approval lifecycle wrapper).

TDD RED phase — all tests import from agentos.approval_recorder which does not
exist yet.  Running this file MUST produce ImportError / ModuleNotFoundError.
"""
from __future__ import annotations

import json
import logging
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch as mock_patch


class TestApprovalRecorder(unittest.TestCase):
    """Tests for patch_db_for_approval_recording and the wrapping behaviour."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _make_mock_db(self):
        """Return a MagicMock that looks like a minimal Agno DB object."""
        db = MagicMock()
        db.create_approval = MagicMock(return_value={"approval_id": "ap-new"})
        db.update_approval = MagicMock(return_value={"approval_id": "ap-1"})
        db.update_approval_run_status = MagicMock(return_value=1)
        return db

    def _approval_data(self) -> dict:
        return {
            "tool_name": "ingest_to_vault",
            "tool_call_id": "tc-123",
            "run_id": "run-abc",
            "agent_id": "ingest",
            "tool_args": {"path": "/vault/test.md"},
        }

    # ------------------------------------------------------------------
    # 1. create_approval emits OBS log with op='create', path='approval', status='ok'
    # ------------------------------------------------------------------
    def test_create_approval_logs_ok(self):
        from agentos.approval_recorder import patch_db_for_approval_recording  # noqa: F401 (RED: will fail here)

        db = self._make_mock_db()
        with self.assertLogs("agentos.approval", level="INFO") as cm:
            patch_db_for_approval_recording(db)
            db.create_approval(self._approval_data())

        log_text = " ".join(cm.output)
        self.assertIn("approval", log_text)
        # find the JSON record
        record = None
        for line in cm.output:
            idx = line.find("{")
            if idx != -1:
                try:
                    record = json.loads(line[idx:])
                    break
                except json.JSONDecodeError:
                    pass
        self.assertIsNotNone(record, "No JSON record found in log output")
        self.assertEqual(record.get("path"), "approval")
        self.assertEqual(record.get("op"), "create")
        self.assertEqual(record.get("status"), "ok")

    # ------------------------------------------------------------------
    # 2. OBS log record contains tool_name and tool_call_id
    # ------------------------------------------------------------------
    def test_obs_log_on_create(self):
        from agentos.approval_recorder import patch_db_for_approval_recording  # noqa: F401

        db = self._make_mock_db()
        with self.assertLogs("agentos.approval", level="INFO") as cm:
            patch_db_for_approval_recording(db)
            db.create_approval(self._approval_data())

        record = None
        for line in cm.output:
            idx = line.find("{")
            if idx != -1:
                try:
                    record = json.loads(line[idx:])
                    break
                except json.JSONDecodeError:
                    pass
        self.assertIsNotNone(record)
        self.assertEqual(record.get("tool_name"), "ingest_to_vault")
        self.assertEqual(record.get("tool_call_id"), "tc-123")

    # ------------------------------------------------------------------
    # 3. tool_name and tool_args pass through to underlying DB call (APPR-03)
    # ------------------------------------------------------------------
    def test_tool_name_in_approval_data(self):
        from agentos.approval_recorder import patch_db_for_approval_recording  # noqa: F401

        db = self._make_mock_db()
        original_create = db.create_approval
        patch_db_for_approval_recording(db)

        data = self._approval_data()
        with self.assertLogs("agentos.approval", level="INFO"):
            db.create_approval(data)

        # The underlying original was called with the same data object
        original_create.assert_called_once_with(data)

    # ------------------------------------------------------------------
    # 4. update_approval emits OBS log with op='resolve', status_to value
    # ------------------------------------------------------------------
    def test_update_approval_logs_resolve(self):
        from agentos.approval_recorder import patch_db_for_approval_recording  # noqa: F401

        db = self._make_mock_db()
        with self.assertLogs("agentos.approval", level="INFO") as cm:
            patch_db_for_approval_recording(db)
            db.update_approval("ap-1", status="approved")

        record = None
        for line in cm.output:
            idx = line.find("{")
            if idx != -1:
                try:
                    record = json.loads(line[idx:])
                    break
                except json.JSONDecodeError:
                    pass
        self.assertIsNotNone(record)
        self.assertEqual(record.get("op"), "resolve")
        self.assertEqual(record.get("status_to"), "approved")

    # ------------------------------------------------------------------
    # 5. update_approval_run_status emits OBS log with op='run_status'
    # ------------------------------------------------------------------
    def test_update_run_status_logs(self):
        from agentos.approval_recorder import patch_db_for_approval_recording  # noqa: F401

        db = self._make_mock_db()
        with self.assertLogs("agentos.approval", level="INFO") as cm:
            patch_db_for_approval_recording(db)
            db.update_approval_run_status("run-abc", "completed")

        record = None
        for line in cm.output:
            idx = line.find("{")
            if idx != -1:
                try:
                    record = json.loads(line[idx:])
                    break
                except json.JSONDecodeError:
                    pass
        self.assertIsNotNone(record)
        self.assertEqual(record.get("op"), "run_status")
        self.assertEqual(record.get("run_status"), "completed")

    # ------------------------------------------------------------------
    # 6. OBS emit failure is non-fatal — underlying call still returns
    # ------------------------------------------------------------------
    def test_log_failure_nonfatal(self):
        from agentos.approval_recorder import patch_db_for_approval_recording  # noqa: F401

        db = self._make_mock_db()
        patch_db_for_approval_recording(db)

        # Simulate _emit raising an error by patching log.info to raise
        import agentos.approval_recorder as ar_mod
        with mock_patch.object(ar_mod.log, "info", side_effect=RuntimeError("log boom")):
            with mock_patch.object(ar_mod.log, "error"):  # swallow the error log too
                # Must not raise even though logging failed
                try:
                    db.create_approval(self._approval_data())
                except RuntimeError:
                    self.fail("RuntimeError from log should have been swallowed")

    # ------------------------------------------------------------------
    # 7. SqliteDb probe — patch_db_for_approval_recording works on real SqliteDb
    # ------------------------------------------------------------------
    def test_sqlite_fallback_no_503(self):
        from agentos.approval_recorder import patch_db_for_approval_recording  # noqa: F401
        from agno.db.sqlite.sqlite import SqliteDb

        db_path = tempfile.mktemp(suffix=".db")
        sqlite_db = SqliteDb(db_path=db_path)

        # Must not raise AttributeError or anything else
        try:
            patch_db_for_approval_recording(sqlite_db)
        except Exception as exc:
            self.fail(f"patch_db_for_approval_recording raised {exc!r} on SqliteDb")

        self.assertTrue(
            getattr(sqlite_db, "_approval_recorder_patched", False),
            "_approval_recorder_patched sentinel not set on SqliteDb",
        )

    # ------------------------------------------------------------------
    # 8. Idempotent — double-patching does not double-wrap
    # ------------------------------------------------------------------
    def test_idempotent_patch(self):
        from agentos.approval_recorder import patch_db_for_approval_recording  # noqa: F401

        db = self._make_mock_db()
        original_create = db.create_approval

        patch_db_for_approval_recording(db)
        wrapped_once = db.create_approval

        patch_db_for_approval_recording(db)  # second call must be a no-op

        # The second call must not have replaced the wrapper again
        self.assertIs(db.create_approval, wrapped_once,
                      "double-patch should not replace the already-patched method")


if __name__ == "__main__":
    unittest.main()
