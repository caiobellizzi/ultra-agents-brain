"""Shared SqliteDb for all Agno agents.

Wave 1 finding: Agno 2.x requires `db=` on every Agent. One shared db keeps
session memory consistent across agents and survives systemd restarts.
"""

from __future__ import annotations

import os
from pathlib import Path

from agno.db.sqlite import SqliteDb

DB_PATH = Path(os.environ.get("UAB_DB_PATH", "~/Documents/uab-state/agno.db")).expanduser()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

db = SqliteDb(db_file=str(DB_PATH))
