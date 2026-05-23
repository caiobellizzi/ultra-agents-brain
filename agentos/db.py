"""Shared DB handles for all Agno agents.

Wave 1 finding: Agno 2.x requires `db=` on every Agent. One shared db keeps
session memory consistent across agents and survives systemd restarts.

Phase 13: also exposes ``POSTGRES_DB`` — the singleton PostgresDb(id='ultra-brain-main')
used as ``contents_db`` for the knowledge surface. ``None`` when
POSTGRES_DSN_SESSIONS is unset (local/test environments).
"""

from __future__ import annotations

import os
from pathlib import Path

from agno.db.sqlite import SqliteDb

DB_PATH = Path(os.environ.get("UAB_DB_PATH", "~/Documents/uab-state/agno.db")).expanduser()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

db = SqliteDb(db_file=str(DB_PATH))


POSTGRES_DSN_SESSIONS = os.getenv("POSTGRES_DSN_SESSIONS")
POSTGRES_DB = None
if POSTGRES_DSN_SESSIONS:
    try:
        from agno.db.postgres import PostgresDb

        POSTGRES_DB = PostgresDb(
            id="ultra-brain-main",
            db_url=POSTGRES_DSN_SESSIONS,
            create_schema=True,
        )
    except Exception:
        # Local/test environments may set POSTGRES_DSN_SESSIONS without having
        # psycopg2 installed or a reachable DB. Leave POSTGRES_DB=None; the
        # knowledge surface emits its own WARNING via stub-fallback path.
        POSTGRES_DB = None
