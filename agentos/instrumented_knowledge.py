"""OBS-01 instrumented Knowledge — wraps Agno's Knowledge.search()/asearch()
with structured logging + per-hit access_count bump.

Plan 13-02: completes the read-path observability story. Every RAG search
emits one OBS-01 log line on the ``agentos.knowledge`` logger and bumps
``ai.agno_knowledge.access_count`` once per unique ``content_id`` so the UI
Knowledge tab shows live traffic.

Mirrors ``agentos/instrumented_memory.py`` (subclass + logger boilerplate) and
``agentos/eval_recorder.py:60-65`` (``asyncio.to_thread`` for the sync DB call
inside the async path).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from agno.knowledge.knowledge import Knowledge


# --- logger boilerplate (mirrors agentos/instrumented_memory.py:13-22) ---
log = logging.getLogger("agentos.knowledge")
log.setLevel(logging.INFO)
if not log.handlers and not logging.getLogger().handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(_h)
    log.propagate = False


_QUERY_TRUNCATE = 200


class InstrumentedKnowledge(Knowledge):
    """Subclass of Knowledge that emits a structured OBS-01 log line and bumps
    ``access_count`` per unique ``content_id`` on every ``search()`` /
    ``asearch()`` call. Exceptions in the underlying search are log-and-swallowed
    so a flaky vector DB never crashes an agent reply."""

    def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        filters: Optional[Any] = None,
        search_type: Optional[str] = None,
    ) -> List[Any]:
        started = time.monotonic()
        db_id = getattr(self.contents_db, "id", None) if self.contents_db is not None else None
        try:
            results = super().search(
                query,
                max_results=max_results,
                filters=filters,
                search_type=search_type,
            )
        except Exception as exc:
            self._emit(
                query=query,
                hit_count=0,
                latency_ms=int((time.monotonic() - started) * 1000),
                status="error",
                db_id=db_id,
                error_type=exc.__class__.__name__,
                error_msg=str(exc)[:200],
            )
            return []
        self._bump_access_counts(results)
        self._emit(
            query=query,
            hit_count=len(results or []),
            latency_ms=int((time.monotonic() - started) * 1000),
            status="ok",
            db_id=db_id,
        )
        return results

    async def asearch(
        self,
        query: str,
        max_results: Optional[int] = None,
        filters: Optional[Any] = None,
        search_type: Optional[str] = None,
    ) -> List[Any]:
        started = time.monotonic()
        db_id = getattr(self.contents_db, "id", None) if self.contents_db is not None else None
        try:
            results = await super().asearch(
                query,
                max_results=max_results,
                filters=filters,
                search_type=search_type,
            )
        except Exception as exc:
            self._emit(
                query=query,
                hit_count=0,
                latency_ms=int((time.monotonic() - started) * 1000),
                status="error",
                db_id=db_id,
                error_type=exc.__class__.__name__,
                error_msg=str(exc)[:200],
            )
            return []
        # Sync DB call from async path -> off-thread (mirrors eval_recorder).
        await asyncio.to_thread(self._bump_access_counts, results)
        self._emit(
            query=query,
            hit_count=len(results or []),
            latency_ms=int((time.monotonic() - started) * 1000),
            status="ok",
            db_id=db_id,
        )
        return results

    def _bump_access_counts(self, documents: List[Any]) -> None:
        if not self.contents_db or not documents:
            return
        seen: set[str] = set()
        for doc in documents:
            meta = getattr(doc, "meta_data", None) or {}
            content_id = meta.get("content_id")
            if not content_id or content_id in seen:
                continue
            seen.add(content_id)
            try:
                current = self.contents_db.get_knowledge_content(content_id)
                if current is None:
                    continue
                current.access_count = (getattr(current, "access_count", 0) or 0) + 1
                current.updated_at = int(time.time())
                self.contents_db.upsert_knowledge_content(current)
            except Exception:
                # Observability bugs must never crash a real agent reply.
                log.exception("access_count bump failed for %s", content_id)

    def _emit(
        self,
        *,
        query: str,
        hit_count: int,
        latency_ms: int,
        status: str,
        db_id: Optional[str],
        error_type: Optional[str] = None,
        error_msg: Optional[str] = None,
    ) -> None:
        record: Dict[str, Any] = {
            "path": "knowledge",
            "agent_id": None,
            "db_id": db_id,
            "op": "search",
            "query": (query or "")[:_QUERY_TRUNCATE],
            "hit_count": hit_count,
            "latency_ms": latency_ms,
            "status": status,
            "row_id": None,
        }
        if status == "error":
            record["error_type"] = error_type
            record["error_msg"] = error_msg
            log.error("OBS-01 knowledge search failed: %s", json.dumps(record))
        else:
            log.info("OBS-01 knowledge search: %s", json.dumps(record))
