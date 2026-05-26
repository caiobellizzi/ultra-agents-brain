"""Vault layout helpers shared by skills."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


VAULT_DIRS = [
    "00-Projects",
    "01-Areas/engineering-knowledge",
    "01-Areas/ai-tooling-landscape",
    "01-Areas/personal-finance",
    "01-Areas/relationships",
    "02-Resources/articles",
    "02-Resources/papers",
    "02-Resources/books",
    "02-Resources/prompts",
    "03-Archives",
    "Inbox",
    "_system/telos",
]

SYSTEM_FILES = {
    "_system/log.md": "# Operations Log\n\n",
    "_system/cost-ledger.md": "# Cost Ledger\n\n| timestamp | scope | operation | model | cost_usd | notes |\n|---|---|---|---|---:|---|\n",
    "_system/lint-report.md": "# Lint Report\n\nNo lint run yet.\n",
    "_system/index.md": "# Vault Index\n\n",
    "_system/telos.md": "# TELOS\n\nStatus: draft placeholder.\n",
}

_MACOS_TRASH_SCRIPT = """
on run argv
    tell application "Finder"
        repeat with targetPath in argv
            delete POSIX file targetPath
        end repeat
    end tell
end run
""".strip()


def ensure_vault(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel in VAULT_DIRS:
        (root / rel).mkdir(parents=True, exist_ok=True)
    for rel, content in SYSTEM_FILES.items():
        path = root / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def trash_paths(paths: list[Path], *, timeout: int = 120) -> None:
    """Remove files in a way iCloud Drive treats as intentional trash moves."""
    resolved_paths = [path.expanduser().resolve() for path in paths if path.exists()]
    if not resolved_paths:
        return

    if sys.platform != "darwin":
        for path in resolved_paths:
            path.unlink()
        return

    for path in resolved_paths:
        try:
            subprocess.run(
                ["osascript", "-e", _MACOS_TRASH_SCRIPT, str(path)],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("osascript not found; cannot move file to Finder Trash") from exc
        except subprocess.TimeoutExpired:
            # iCloud placeholder not materialized — fall back to unlink
            path.unlink(missing_ok=True)
        except subprocess.CalledProcessError:
            # Finder can't reach file (iCloud cloud-only or already gone) — unlink directly
            path.unlink(missing_ok=True)


def move_to_trash(path: Path) -> None:
    """Remove one file in a way iCloud Drive treats as an intentional trash move."""
    trash_paths([path])
