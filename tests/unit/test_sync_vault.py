"""Regression tests for ops/sync-vault-to-vps.sh — MON-02.

Proves the 2-pass rsync strategy protects VPS-generated Inbox items from
being deleted by the --delete flag in Pass 2.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


def test_pull_before_push_delete() -> None:
    """Script structure test: pull pass (no --delete) must precede push pass (--delete)."""
    script = Path("ops/sync-vault-to-vps.sh").read_text()
    rsync_lines = [
        line.strip()
        for line in script.splitlines()
        if line.strip().startswith("/usr/bin/rsync") or line.strip().startswith("rsync")
    ]
    assert len(rsync_lines) >= 2, "Expected at least 2 rsync invocations"

    pull_lines = [line for line in rsync_lines if "--delete" not in line]
    push_lines = [line for line in rsync_lines if "--delete" in line]

    assert pull_lines, "No pull pass found (rsync without --delete)"
    assert push_lines, "No push pass found (rsync with --delete)"

    pull_idx = rsync_lines.index(pull_lines[0])
    push_idx = rsync_lines.index(push_lines[0])
    assert pull_idx < push_idx, "Pull (no --delete) must precede push (--delete)"


class TestSyncDeleteSafety(unittest.TestCase):
    def test_vps_generated_items_survive_delete_sync(self) -> None:
        """Functional test: VPS-generated Inbox items must survive the --delete push pass."""
        if shutil.which("rsync") is None:
            self.skipTest("rsync not available")

        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "local"
            remote = Path(tmp) / "remote"
            local.mkdir()
            remote.mkdir()

            # Simulate a VPS-generated Inbox item (exists on remote only)
            (remote / "Inbox").mkdir()
            vps_item = remote / "Inbox" / "2026-05-27-vps-generated.md"
            vps_item.write_text("# VPS item\n")

            # Simulate a Mac-side file that exists on local only
            (local / "00-Projects").mkdir()
            local_item = local / "00-Projects" / "project.md"
            local_item.write_text("# Local project\n")

            # Pass 1: remote → local (no --delete)
            subprocess.run(
                ["rsync", "-a", "--update", f"{remote}/", f"{local}/"],
                check=True,
            )

            # Pass 2: local → remote (--delete)
            subprocess.run(
                ["rsync", "-a", "--update", "--delete", f"{local}/", f"{remote}/"],
                check=True,
            )

            # VPS-generated item must still exist on remote
            self.assertTrue(
                (remote / "Inbox" / "2026-05-27-vps-generated.md").exists(),
                "VPS-generated Inbox item was deleted by --delete sync",
            )
            # Local-only file must also exist on remote after push
            self.assertTrue(
                (remote / "00-Projects" / "project.md").exists(),
                "Mac-side file was not pushed to remote",
            )
