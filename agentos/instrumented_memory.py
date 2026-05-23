"""OBS-01 instrumented MemoryManager — wraps Agno's create_user_memories
with structured logging."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, List, Optional

from agno.memory.manager import MemoryManager

log = logging.getLogger("agentos.memory")
# OBS-01 requires every memory write to emit a log line. Force the logger to
# INFO so the success path is visible even when the root logger is configured
# at WARNING (which is the default under uvicorn / systemd journal). Attach a
# StreamHandler iff no handlers exist on this logger or root, so the line is
# captured regardless of host logging setup.
log.setLevel(logging.INFO)
if not log.handlers and not logging.getLogger().handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(_h)
    log.propagate = False


class InstrumentedMemoryManager(MemoryManager):
    """Subclass of MemoryManager that emits an OBS-01 structured log line
    around every auto-extraction call. The log schema is the contract that
    ROADMAP OBS-01 specifies."""

    def create_user_memories(
        self,
        message: Optional[str] = None,
        messages: Optional[List[Any]] = None,
        agent_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        run_metrics: Optional[Any] = None,
    ) -> str:
        started = time.monotonic()
        db_id = getattr(self.db, "id", None) if self.db is not None else None
        status = "ok"
        error_type: Optional[str] = None
        error_msg: Optional[str] = None
        result_str = ""
        row_count_before = self._safe_count(user_id)
        try:
            result_str = super().create_user_memories(
                message=message,
                messages=messages,
                agent_id=agent_id,
                team_id=team_id,
                user_id=user_id,
                run_metrics=run_metrics,
            )
            return result_str
        except Exception as exc:
            status = "error"
            error_type = exc.__class__.__name__
            error_msg = str(exc)[:200]
            raise
        finally:
            row_count_after = self._safe_count(user_id)
            latency_ms = int((time.monotonic() - started) * 1000)
            self._emit(
                agent_id=agent_id,
                team_id=team_id,
                user_id=user_id,
                db_id=db_id,
                latency_ms=latency_ms,
                status=status,
                error_type=error_type,
                error_msg=error_msg,
                extracted_count=max(0, row_count_after - row_count_before),
            )

    async def acreate_user_memories(
        self,
        message: Optional[str] = None,
        messages: Optional[List[Any]] = None,
        agent_id: Optional[str] = None,
        team_id: Optional[str] = None,
        user_id: Optional[str] = None,
        run_metrics: Optional[Any] = None,
    ) -> str:
        started = time.monotonic()
        db_id = getattr(self.db, "id", None) if self.db is not None else None
        status = "ok"
        error_type: Optional[str] = None
        error_msg: Optional[str] = None
        result_str = ""
        row_count_before = self._safe_count(user_id)
        try:
            result_str = await super().acreate_user_memories(
                message=message,
                messages=messages,
                agent_id=agent_id,
                team_id=team_id,
                user_id=user_id,
                run_metrics=run_metrics,
            )
            return result_str
        except Exception as exc:
            status = "error"
            error_type = exc.__class__.__name__
            error_msg = str(exc)[:200]
            raise
        finally:
            row_count_after = self._safe_count(user_id)
            latency_ms = int((time.monotonic() - started) * 1000)
            self._emit(
                agent_id=agent_id,
                team_id=team_id,
                user_id=user_id,
                db_id=db_id,
                latency_ms=latency_ms,
                status=status,
                error_type=error_type,
                error_msg=error_msg,
                extracted_count=max(0, row_count_after - row_count_before),
            )

    def _safe_count(self, user_id: Optional[str]) -> int:
        """Best-effort row count for the OBS-01 extracted_count metric.
        Returns 0 on any error (counting is observability, not behavior)."""
        if self.db is None:
            return 0
        try:
            mems = self.db.get_user_memories(user_id=user_id) or []
            return len(mems)
        except Exception:
            return 0

    def _emit(
        self,
        *,
        agent_id: Optional[str],
        team_id: Optional[str],
        user_id: Optional[str],
        db_id: Optional[str],
        latency_ms: int,
        status: str,
        error_type: Optional[str],
        error_msg: Optional[str],
        extracted_count: int,
    ) -> None:
        record = {
            "path": "memory",
            "agent_id": agent_id,
            "team_id": team_id,
            "user_id": user_id,
            "db_id": db_id,
            "latency_ms": latency_ms,
            "status": status,
            "extracted_count": extracted_count,
        }
        if status == "error":
            record["error_type"] = error_type
            record["error_msg"] = error_msg
            log.error("OBS-01 memory write failed: %s", json.dumps(record))
        else:
            log.info("OBS-01 memory write: %s", json.dumps(record))
