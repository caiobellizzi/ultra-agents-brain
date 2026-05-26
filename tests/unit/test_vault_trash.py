from __future__ import annotations

import subprocess
from datetime import date

import scripts.inbox_sweep as inbox_sweep
from ultra_brain import monitor
from ultra_brain import vault as vault_mod


def test_trash_paths_uses_batched_finder_delete_on_macos(tmp_path, monkeypatch) -> None:
    source = tmp_path / 'quoted "note".md'
    source.write_text("# Note\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        assert kwargs == {"check": True, "capture_output": True, "text": True, "timeout": 30}
        source.unlink()
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(vault_mod.sys, "platform", "darwin")
    monkeypatch.setattr(vault_mod.subprocess, "run", fake_run)

    vault_mod.trash_paths([source])

    assert not source.exists()
    assert calls[0][0:2] == ["osascript", "-e"]
    assert "repeat with targetPath in argv" in calls[0][2]
    assert calls[0][-1] == str(source.resolve())


def test_inbox_sweep_uses_trash_for_promote_and_archive(tmp_path, monkeypatch) -> None:
    vault_root = tmp_path / "vault"
    inbox = vault_root / "Inbox"
    inbox.mkdir(parents=True)
    (inbox / "agent-note.md").write_text("# Agent Tools\n\nAI agents llm codex.\n", encoding="utf-8")
    (inbox / "pasta-note.md").write_text("# Pasta\n\npasta gluten food.\n", encoding="utf-8")
    trashed: list[str] = []

    def fake_trash_paths(paths):
        trashed.extend(path.name for path in paths)
        for path in paths:
            path.unlink()

    monkeypatch.setattr(inbox_sweep, "trash_paths", fake_trash_paths)

    assert inbox_sweep.sweep(vault_root) == 0

    archive_month = date.today().strftime("%Y-%m")
    assert sorted(trashed) == ["agent-note.md", "pasta-note.md"]
    assert (vault_root / "02-Resources" / "articles" / "agent-note.md").exists()
    assert (vault_root / "03-Archives" / f"inbox-sweep-{archive_month}" / "pasta-note.md").exists()
    assert not (inbox / "agent-note.md").exists()
    assert not (inbox / "pasta-note.md").exists()


def test_inbox_sweep_reuses_identical_dest_after_interrupted_run(tmp_path, monkeypatch) -> None:
    vault_root = tmp_path / "vault"
    inbox = vault_root / "Inbox"
    inbox.mkdir(parents=True)
    source = inbox / "pasta-note.md"
    source.write_text("# Pasta\n\npasta gluten food.\n", encoding="utf-8")
    inbox_sweep._update_frontmatter_telos(source, 0.0)
    archive_month = date.today().strftime("%Y-%m")
    archive_dir = vault_root / "03-Archives" / f"inbox-sweep-{archive_month}"
    archive_dir.mkdir(parents=True)
    existing = archive_dir / source.name
    existing.write_bytes(source.read_bytes())

    def fake_trash_paths(paths):
        for path in paths:
            path.unlink()

    monkeypatch.setattr(inbox_sweep, "trash_paths", fake_trash_paths)

    assert inbox_sweep.sweep(vault_root) == 0

    assert existing.exists()
    assert not (archive_dir / "pasta-note-1.md").exists()
    assert not source.exists()


def test_monitor_scored_moves_use_trash(tmp_path, monkeypatch) -> None:
    feeds = tmp_path / "feeds.txt"
    feeds.write_text("https://example.test/feed.xml\n", encoding="utf-8")
    vault_root = tmp_path / "vault"
    trashed: list[str] = []

    def fake_fetch_feed(_url: str) -> list[monitor.FeedItem]:
        return [
            monitor.FeedItem("AI agents LLM Codex", "https://example.test/agent"),
            monitor.FeedItem("Pasta gluten food", "https://example.test/food"),
        ]

    def fake_move_to_trash(path):
        trashed.append(path.name)
        path.unlink()

    monkeypatch.setattr(monitor, "fetch_feed", fake_fetch_feed)
    monkeypatch.setattr(monitor, "move_to_trash", fake_move_to_trash)

    assert len(monitor.run_poll(feeds, vault_root)) == 2

    today = date.today().isoformat()
    agent_file = f"{today}-ai-agents-llm-codex.md"
    pasta_file = f"{today}-pasta-gluten-food.md"
    assert sorted(trashed) == [agent_file, pasta_file]
    assert (vault_root / "02-Resources" / "articles" / agent_file).exists()
    assert (vault_root / "03-Archives" / "auto-culled" / pasta_file).exists()
