#!/usr/bin/env python3
"""OBS-02 smoke checker — query row counts for all 4 AgentOS surfaces.

Usage:
    PYTHONPATH=. .venv/bin/python scripts/check_surfaces.py

With POSTGRES_DSN_SESSIONS unset: prints local-mode warning and exits 0.
With POSTGRES_DSN_SESSIONS set: queries memory, evals, approvals, knowledge
and exits 0 if all surfaces have rows, 1 if any surface has 0 or is missing.
"""

from __future__ import annotations

import os
import sys


def check_surfaces() -> int:
    dsn_sessions = os.getenv("POSTGRES_DSN_SESSIONS")
    if not dsn_sessions:
        print(
            "[local mode] POSTGRES_DSN_SESSIONS not set"
            " — skipping memory/evals/approvals check"
        )
        return 0

    # Import here so local mode never needs psycopg2/sqlalchemy.
    try:
        from agno.db.postgres import PostgresDb
    except ImportError as exc:
        print(f"[error] cannot import agno.db.postgres: {exc}", file=sys.stderr)
        return 1

    try:
        import psycopg2
        import psycopg2.sql
    except ImportError as exc:
        print(f"[error] cannot import psycopg2: {exc}", file=sys.stderr)
        return 1

    db = PostgresDb(
        id="ultra-brain-main",
        db_url=dsn_sessions,
        create_schema=False,
    )

    failures = 0

    def count_table(conn_str: str, table_name: str, label: str) -> None:
        nonlocal failures
        try:
            conn = psycopg2.connect(conn_str)
            cur = conn.cursor()
            cur.execute(psycopg2.sql.SQL("SELECT COUNT(*) FROM {}").format(psycopg2.sql.Identifier(table_name)))
            row = cur.fetchone()
            count = row[0] if row else 0
            cur.close()
            conn.close()
            status = "✓" if count > 0 else "✗"
            if count == 0:
                failures += 1
            print(f"{label:<10} {status}  {count} rows   ({table_name})")
        except psycopg2.errors.UndefinedTable:
            print(f"{label:<10} ✗  TABLE MISSING   ({table_name})")
            failures += 1
        except Exception as exc:  # noqa: BLE001
            print(f"{label:<10} ✗  ERROR: {exc}   ({table_name})")
            failures += 1

    # memory, evals, approvals all use POSTGRES_DSN_SESSIONS
    count_table(dsn_sessions, db.memory_table_name, "memory:")
    count_table(dsn_sessions, db.eval_table_name, "evals:")
    count_table(dsn_sessions, db.approvals_table_name, "approvals:")

    # knowledge uses a separate DSN (pgvector table "vault")
    dsn_knowledge = os.getenv("POSTGRES_DSN_KNOWLEDGE", dsn_sessions)
    count_table(dsn_knowledge, "vault", "knowledge:")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(check_surfaces())
