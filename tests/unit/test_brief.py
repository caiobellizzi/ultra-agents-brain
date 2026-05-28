"""Regression tests for MON-01: _read_inbox_items date-mismatch bug.

These tests verify that _read_inbox_items picks up items filed on the previous
calendar day (lookback_days=2), not only items dated exactly `day`.
"""
from __future__ import annotations

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from ultra_brain.brief import _filter_unseen, _read_inbox_items
from ultra_brain.monitor import DedupStore


TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def _make_vault(tmp: str) -> Path:
    vault = Path(tmp) / "vault"
    (vault / "Inbox").mkdir(parents=True)
    return vault


def _write_inbox_item(inbox_dir: Path, filename: str, url: str, title: str = "Test Item") -> None:
    content = f"# {title}\nsource:: {url}\npublished:: 2026-01-01\n"
    (inbox_dir / filename).write_text(content, encoding="utf-8")


def test_date_lookback_catches_yesterday_items() -> None:
    """Items filed yesterday must be returned when called with day=today."""
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(tmp)
        inbox_dir = vault / "Inbox"
        _write_inbox_item(inbox_dir, f"{YESTERDAY.isoformat()}-test-item.md", "https://example.com/a")

        items = _read_inbox_items(vault, day=TODAY)

        assert len(items) == 1
        assert items[0]["url"] == "https://example.com/a"


def test_today_items_still_returned() -> None:
    """Items filed today must still be returned (regression guard)."""
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(tmp)
        inbox_dir = vault / "Inbox"
        _write_inbox_item(inbox_dir, f"{TODAY.isoformat()}-test-item.md", "https://example.com/b")

        items = _read_inbox_items(vault, day=TODAY)

        assert len(items) == 1
        assert items[0]["url"] == "https://example.com/b"


def test_no_duplicates_across_days() -> None:
    """Same URL in both yesterday and today inbox files is deduplicated by _filter_unseen."""
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(tmp)
        inbox_dir = vault / "Inbox"
        shared_url = "https://example.com/shared"
        _write_inbox_item(inbox_dir, f"{YESTERDAY.isoformat()}-item-a.md", shared_url)
        _write_inbox_item(inbox_dir, f"{TODAY.isoformat()}-item-b.md", shared_url)

        # Pre-seed the dedup store with the shared URL already seen
        system_dir = vault / "_system"
        system_dir.mkdir(parents=True)
        dedup_path = system_dir / "brief-seen.json"
        dedup_path.write_text(
            json.dumps({"seen": [shared_url]}, indent=2) + "\n", encoding="utf-8"
        )
        store = DedupStore(dedup_path)

        items = _read_inbox_items(vault, day=TODAY)
        unseen = _filter_unseen(items, store)

        assert unseen == []


def test_lookback_only_reads_inbox_subdir() -> None:
    """Files outside the Inbox/ subdir must not be included even if they match the date pattern."""
    with tempfile.TemporaryDirectory() as tmp:
        vault = _make_vault(tmp)
        resources_dir = vault / "02-Resources" / "articles"
        resources_dir.mkdir(parents=True)
        _write_inbox_item(resources_dir, f"{YESTERDAY.isoformat()}-sneaky.md", "https://example.com/sneaky")

        items = _read_inbox_items(vault, day=TODAY)

        assert items == []
