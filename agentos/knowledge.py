"""Knowledge layer for ultra-brain — write path.

Plan 13-01 surface:

- ``make_knowledge()`` — singleton-style factory returning a wired Agno Knowledge
  (``name='ultra-brain-vault'``, ``vector_db=PgVector(...)``, ``contents_db=POSTGRES_DB``).
  Falls back to a stub Knowledge (no vector_db, no contents_db) with a loud
  WARNING log line when ``POSTGRES_DSN_KNOWLEDGE`` is unset or PgVector init
  raises. The wired ``contents_db`` is the actual RC-knowledge-not-registered
  fix — without it, AgentOS's ``/knowledge/config`` Available IDs stays empty.

- ``reindex(vault_path, knowledge)`` — pure function. Walks the vault, sha256s
  each file, skips files whose recorded sha256 in
  ``contents_db.get_knowledge_contents()`` matches, and calls
  ``Knowledge.insert(...)`` for the rest. Per-file errors are isolated. Emits
  one OBS-01 structured log line per file action (indexed/skipped/error).

- ``cli_main(argv)`` — ``python -m agentos.knowledge --reindex`` entry point.
  Prints per-file ``[indexed]``/``[skipped]``/``[error]`` lines and a final
  summary; returns 0 iff ``errors == 0``.

OBS-01 log shape: see ``agentos/instrumented_memory.py`` for the memory side;
this module mirrors the structured-JSON-suffix convention on the
``agentos.knowledge`` logger.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder
from agno.knowledge.reranker.sentence_transformer import SentenceTransformerReranker
from agno.vectordb.pgvector import PgVector, SearchType

from agentos.db import POSTGRES_DB
from agentos.instrumented_knowledge import InstrumentedKnowledge


# --- logger boilerplate (mirrors agentos/instrumented_memory.py:13-22) ---
log = logging.getLogger("agentos.knowledge")
log.setLevel(logging.INFO)
if not log.handlers and not logging.getLogger().handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(_h)
    log.propagate = False


VAULT_PATH_DEFAULT = "vault"


@dataclass
class ReindexSummary:
    indexed: int
    skipped: int
    errors: int
    total: int
    duration_seconds: float


def _emit_obs01(
    *,
    action: str,
    status: str,
    rel_path: str,
    sha256: str,
    content_bytes: int,
    latency_ms: int,
    db_id: Optional[str],
    row_id: Optional[str],
    error_type: Optional[str] = None,
    error_msg: Optional[str] = None,
) -> None:
    payload: dict[str, Any] = {
        "path": "knowledge",
        "agent_id": None,
        "db_id": db_id,
        "op": "index",
        "rel_path": rel_path,
        "sha256": sha256,
        "action": action,
        "content_bytes": content_bytes,
        "latency_ms": latency_ms,
        "status": status,
        "row_id": row_id,
    }
    if error_type is not None:
        payload["error_type"] = error_type
    if error_msg is not None:
        payload["error_msg"] = error_msg[:200]
    level = logging.ERROR if status == "error" else logging.INFO
    log.log(level, "OBS-01 knowledge write: %s", json.dumps(payload))


def make_knowledge() -> Knowledge:
    """Build a wired Knowledge instance, or a stub on failure.

    Stub fallback emits a WARNING log line and returns ``Knowledge(name=...)``
    with neither ``vector_db`` nor ``contents_db`` set.
    """
    dsn = os.getenv("POSTGRES_DSN_KNOWLEDGE")
    if not dsn:
        log.warning(
            "agentos.knowledge stub-fallback: %s",
            json.dumps(
                {
                    "path": "knowledge",
                    "status": "stub-fallback",
                    "reason": "POSTGRES_DSN_KNOWLEDGE not set",
                    "db_id": None,
                }
            ),
        )
        return Knowledge(name="ultra-brain-vault")

    try:
        vector_db = PgVector(
            table_name="vault",
            db_url=dsn,
            embedder=SentenceTransformerEmbedder(
                id="BAAI/bge-small-en-v1.5"
            ),
            search_type=SearchType.hybrid,
            reranker=SentenceTransformerReranker(),
        )
    except Exception as exc:  # pragma: no cover — exercised via stub-fallback test variant
        log.warning(
            "agentos.knowledge stub-fallback: %s",
            json.dumps(
                {
                    "path": "knowledge",
                    "status": "stub-fallback",
                    "reason": str(exc),
                    "db_id": None,
                }
            ),
        )
        return Knowledge(name="ultra-brain-vault")

    return InstrumentedKnowledge(
        name="ultra-brain-vault",
        vector_db=vector_db,
        contents_db=POSTGRES_DB,
    )


def _existing_rows(knowledge: Knowledge) -> dict[str, dict[str, Any]]:
    """Best-effort fetch of recorded rows from contents_db; empty dict on any failure
    (graceful first-run on a fresh DB — table doesn't exist until first insert)."""
    contents_db = getattr(knowledge, "contents_db", None)
    if contents_db is None:
        return {}
    try:
        result = contents_db.get_knowledge_contents()
    except Exception as exc:
        log.error(
            "agentos.knowledge contents_db lookup failed: %s",
            json.dumps({"path": "knowledge", "status": "error", "reason": str(exc)}),
        )
        return {}
    # Agno's real signature returns Tuple[List[KnowledgeRow], int]; tests may also
    # return a plain list. Normalize.
    if isinstance(result, tuple) and len(result) == 2:
        rows = result[0]
    else:
        rows = result
    out: dict[str, dict[str, Any]] = {}
    for row in rows or []:
        name = getattr(row, "name", None)
        meta = getattr(row, "metadata", None) or {}
        if name is not None:
            out[name] = {**meta, "_row_id": getattr(row, "id", None)}
    return out


def reindex(
    vault_path: Path | None = None,
    knowledge: Knowledge | None = None,
    *,
    force: bool = False,
) -> ReindexSummary:
    """Walk ``vault_path/**/*.md``, sha256 each file, skip unchanged, insert changed.

    Pass ``force=True`` to re-embed all files regardless of stored sha256 (required
    after switching the embedder model, since content hashes won't detect the change).

    Per-file errors are isolated. Returns a populated ``ReindexSummary``.
    """
    vault_path = Path(vault_path or os.getenv("VAULT_PATH", VAULT_PATH_DEFAULT))
    knowledge = knowledge if knowledge is not None else make_knowledge()
    db_id = getattr(getattr(knowledge, "contents_db", None), "id", None)

    if knowledge.vector_db is None:
        log.error(
            "agentos.knowledge reindex-unavailable: %s",
            json.dumps(
                {
                    "path": "knowledge",
                    "status": "reindex-unavailable",
                    "reason": "knowledge stub — POSTGRES_DSN_KNOWLEDGE not set",
                    "db_id": db_id,
                }
            ),
        )
        return ReindexSummary(0, 0, 0, 0, 0.0)

    existing = {} if force else _existing_rows(knowledge)

    indexed = 0
    skipped = 0
    errors = 0
    started_total = time.monotonic()

    for file_path in sorted(vault_path.rglob("*.md")):
        rel_path = str(file_path.relative_to(vault_path))
        try:
            content_bytes = file_path.read_bytes()
        except Exception as exc:
            errors += 1
            _emit_obs01(
                action="error",
                status="error",
                rel_path=rel_path,
                sha256="",
                content_bytes=0,
                latency_ms=0,
                db_id=db_id,
                row_id=None,
                error_type=type(exc).__name__,
                error_msg=str(exc),
            )
            print(f"[error] {rel_path}: {exc}")
            continue

        sha256_hex = hashlib.sha256(content_bytes).hexdigest()
        prior = existing.get(rel_path, {})

        if prior.get("file_sha256") == sha256_hex:
            skipped += 1
            _emit_obs01(
                action="skipped",
                status="ok",
                rel_path=rel_path,
                sha256=sha256_hex,
                content_bytes=len(content_bytes),
                latency_ms=0,
                db_id=db_id,
                row_id=prior.get("_row_id"),
            )
            print(f"[skipped] {rel_path}")
            continue

        started = time.monotonic()
        try:
            knowledge.insert(
                path=str(file_path),
                name=rel_path,
                metadata={
                    "file_sha256": sha256_hex,
                    "rel_path": rel_path,
                    "size": len(content_bytes),
                    "indexed_at_ms": int(time.time() * 1000),
                },
                upsert=True,
                skip_if_exists=False,
            )
        except Exception as exc:
            errors += 1
            latency_ms = int((time.monotonic() - started) * 1000)
            _emit_obs01(
                action="error",
                status="error",
                rel_path=rel_path,
                sha256=sha256_hex,
                content_bytes=len(content_bytes),
                latency_ms=latency_ms,
                db_id=db_id,
                row_id=None,
                error_type=type(exc).__name__,
                error_msg=str(exc),
            )
            print(f"[error] {rel_path}: {exc}")
            continue

        indexed += 1
        latency_ms = int((time.monotonic() - started) * 1000)
        _emit_obs01(
            action="indexed",
            status="ok",
            rel_path=rel_path,
            sha256=sha256_hex,
            content_bytes=len(content_bytes),
            latency_ms=latency_ms,
            db_id=db_id,
            row_id=None,
        )
        print(f"[indexed] {rel_path}")

    return ReindexSummary(
        indexed=indexed,
        skipped=skipped,
        errors=errors,
        total=indexed + skipped + errors,
        duration_seconds=time.monotonic() - started_total,
    )


def cli_main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else []
    if "--reindex" not in argv:
        print("Usage: python -m agentos.knowledge --reindex [--force]")
        return 1
    force = "--force" in argv
    knowledge = make_knowledge()
    summary = reindex(knowledge=knowledge, force=force)
    print(
        f"Indexed {summary.indexed} files "
        f"({summary.skipped} skipped, {summary.errors} errors) "
        f"in {summary.duration_seconds:.2f}s"
    )
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    import sys

    sys.exit(cli_main(sys.argv[1:]))
