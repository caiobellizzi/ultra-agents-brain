"""Live end-to-end integration test for the InstrumentedKnowledge read path.

Marker: ``@pytest.mark.live`` — default-skipped in CI. To run locally export
``POSTGRES_DSN_KNOWLEDGE`` and ``POSTGRES_DSN_SESSIONS`` pointing at a
throwaway local Postgres with the ``vector`` extension installed.

Verifies KNOW-02 + OBS-01 access path end-to-end:
1. Reindex one note via the 13-01 ``reindex()`` function.
2. Issue a real semantic search.
3. Confirm the row's ``access_count`` increments.
4. Confirm the OBS-01 ``op='search'`` log line emits with the expected schema.
5. Drop the test tables on teardown.
"""
from __future__ import annotations

import json
import logging
import time

import pytest


@pytest.mark.live
def test_live_reindex_search_bumps_access_count(
    tmp_vault,
    live_postgres_dsn_knowledge,
    live_postgres_dsn_sessions,
    caplog,
):
    from agno.db.postgres import PostgresDb
    from agno.knowledge.embedder.sentence_transformer import (
        SentenceTransformerEmbedder,
    )
    from agno.knowledge.reranker.sentence_transformer import (
        SentenceTransformerReranker,
    )
    from agno.vectordb.pgvector import PgVector, SearchType
    from sqlalchemy import create_engine, text

    from agentos.instrumented_knowledge import InstrumentedKnowledge
    from agentos.knowledge import reindex

    # 1. Seed tmp_vault with one recognizable note.
    (tmp_vault / "eiffel.md").write_text(
        "The Eiffel Tower is a wrought-iron lattice tower in Paris, France. "
        "It was completed in 1889."
    )

    # 2. Build a fresh InstrumentedKnowledge against unique per-run tables.
    table_suffix = f"test_{int(time.time())}"
    pg = PgVector(
        table_name=f"vault_{table_suffix}",
        db_url=live_postgres_dsn_knowledge,
        embedder=SentenceTransformerEmbedder(
            id="sentence-transformers/all-MiniLM-L6-v2"
        ),
        search_type=SearchType.hybrid,
        reranker=SentenceTransformerReranker(),
    )
    contents_db = PostgresDb(
        db_url=live_postgres_dsn_sessions,
        id="ultra-brain-main-test",
        knowledge_table=f"agno_knowledge_{table_suffix}",
    )
    ik = InstrumentedKnowledge(
        name="ultra-brain-vault-test",
        vector_db=pg,
        contents_db=contents_db,
    )

    try:
        # 3. Reindex.
        summary = reindex(vault_path=tmp_vault, knowledge=ik)
        assert summary.indexed == 1
        assert summary.errors == 0

        # 4. Confirm the row landed in ai.agno_knowledge_<suffix>.
        rows_result = contents_db.get_knowledge_contents()
        rows = rows_result[0] if isinstance(rows_result, tuple) else rows_result
        eiffel_row = next((r for r in rows if r.name == "eiffel.md"), None)
        assert eiffel_row is not None
        starting_count = getattr(eiffel_row, "access_count", 0) or 0

        # 5. Issue a search; capture log.
        with caplog.at_level(logging.INFO, logger="agentos.knowledge"):
            hits = ik.search("Where is the Eiffel Tower located?")
        assert len(hits) >= 1

        # 6. access_count incremented.
        rows_after_result = contents_db.get_knowledge_contents()
        rows_after = rows_after_result[0] if isinstance(rows_after_result, tuple) else rows_after_result
        eiffel_after = next((r for r in rows_after if r.name == "eiffel.md"), None)
        assert eiffel_after is not None
        assert (getattr(eiffel_after, "access_count", 0) or 0) == starting_count + 1

        # 7. OBS-01 log present.
        search_log = next(
            (
                r for r in caplog.records
                if r.name == "agentos.knowledge"
                and "OBS-01 knowledge search" in r.message
            ),
            None,
        )
        assert search_log is not None
        payload = json.loads(search_log.message[search_log.message.index("{"):])
        assert payload["op"] == "search"
        assert payload["hit_count"] >= 1
        assert payload["status"] == "ok"

    finally:
        # 8. Teardown: drop the per-run tables.
        try:
            with create_engine(live_postgres_dsn_knowledge).begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS ai.vault_{table_suffix} CASCADE"))
        except Exception:
            pass
        try:
            with create_engine(live_postgres_dsn_sessions).begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS ai.agno_knowledge_{table_suffix} CASCADE"))
        except Exception:
            pass
