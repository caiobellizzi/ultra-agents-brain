"""OBS-01 instrumented approval recorder — wraps three Agno DB approval methods.

Intercepts db.create_approval, db.update_approval, and
db.update_approval_run_status on the shared db *instance* and writes one
structured JSON log line per call via the agentos.approval logger.

Covers:
  APPR-01  — approval row creation is observable via OBS log
  APPR-03  — tool_name / tool_call_id visible in approval data
  OBS-01   — structured log lines on every approval lifecycle event

Threat mitigations:
  T-14-01  — idempotency guard prevents double-wrapping (_approval_recorder_patched)
  T-14-02  — OBS emit failures are swallowed; DB calls always proceed
  T-14-03  — tool_args truncated to str(args)[:120]; raw args never logged
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

log = logging.getLogger("agentos.approval")
log.setLevel(logging.INFO)
if not log.handlers and not logging.getLogger().handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(_h)
    log.propagate = False


class ApprovalRecorder:
    """Instance-level wrapper. Attach to a shared db object with .patch().

    Replaces db.create_approval, db.update_approval, and
    db.update_approval_run_status with closures that call the original then
    emit a JSON OBS-01 log line.  Failures inside _emit are swallowed so the
    underlying DB call is never blocked.
    """

    def __init__(self, db: Any) -> None:
        self.db = db

    def patch(self) -> None:
        """Patch db instance in-place.  Idempotent — subsequent calls are no-ops."""
        db = self.db
        if getattr(db, "_approval_recorder_patched", None) is True:
            return

        original_create = db.create_approval
        original_update = db.update_approval
        original_run_status = db.update_approval_run_status
        recorder = self

        def wrapped_create_approval(approval_data: dict) -> Any:
            started = time.monotonic()
            result = original_create(approval_data)
            latency_ms = int((time.monotonic() - started) * 1000)
            try:
                # Extract fields from approval_data
                tool_name = approval_data.get("tool_name")
                tool_call_id = approval_data.get("tool_call_id") or (
                    approval_data.get("tool_execution", {}) or {}
                ).get("tool_call_id")
                run_id = approval_data.get("run_id")
                agent_id = approval_data.get("agent_id")
                approval_id = (result or {}).get("approval_id") or approval_data.get("approval_id")
                # Structural summary — log key names + value shapes, never raw values (T-14-03)
                _raw_args = approval_data.get("tool_args") or {}
                if isinstance(_raw_args, dict):
                    tool_args_summary = "{" + ", ".join(
                        f"{k}: {type(v).__name__}[{len(str(v))}]"
                        for k, v in _raw_args.items()
                    ) + "}"
                else:
                    tool_args_summary = f"{type(_raw_args).__name__}[{len(str(_raw_args))}]"
                recorder._emit(
                    op="create",
                    approval_id=approval_id,
                    tool_name=tool_name,
                    tool_call_id=tool_call_id,
                    run_id=run_id,
                    agent_id=agent_id,
                    status_from=None,
                    status_to=approval_data.get("status"),
                    run_status=None,
                    resolved_by=None,
                    latency_ms=latency_ms,
                    status="ok",
                    tool_args_summary=tool_args_summary,
                )
            except Exception as exc:  # pragma: no cover — swallow OBS failures (D-16)
                try:
                    log.error(
                        "OBS-01 approval emit failed: %s",
                        json.dumps({"path": "approval", "op": "create", "error": str(exc)}, default=str),
                    )
                except Exception:
                    pass
            return result

        def wrapped_update_approval(approval_id: str, expected_status: Optional[str] = None, **kwargs: Any) -> Any:
            started = time.monotonic()
            result = original_update(approval_id, expected_status=expected_status, **kwargs)
            latency_ms = int((time.monotonic() - started) * 1000)
            try:
                status_to = kwargs.get("status") or (
                    (result or {}).get("status") if result else None
                )
                recorder._emit(
                    op="resolve",
                    approval_id=approval_id,
                    tool_name=None,
                    tool_call_id=None,
                    run_id=kwargs.get("run_id"),
                    agent_id=None,
                    status_from=expected_status,
                    status_to=status_to,
                    run_status=None,
                    resolved_by=kwargs.get("resolved_by"),
                    latency_ms=latency_ms,
                    status="ok",
                )
            except Exception as exc:  # pragma: no cover
                try:
                    log.error(
                        "OBS-01 approval emit failed: %s",
                        json.dumps({"path": "approval", "op": "resolve", "error": str(exc)}, default=str),
                    )
                except Exception:
                    pass
            return result

        def wrapped_update_approval_run_status(run_id: str, run_status: Any) -> Any:
            started = time.monotonic()
            result = original_run_status(run_id, run_status)
            latency_ms = int((time.monotonic() - started) * 1000)
            try:
                # run_status may be a RunStatus enum or a plain string
                run_status_str = run_status.value if hasattr(run_status, "value") else str(run_status)
                recorder._emit(
                    op="run_status",
                    approval_id=None,
                    tool_name=None,
                    tool_call_id=None,
                    run_id=run_id,
                    agent_id=None,
                    status_from=None,
                    status_to=None,
                    run_status=run_status_str,
                    resolved_by=None,
                    latency_ms=latency_ms,
                    status="ok",
                )
            except Exception as exc:  # pragma: no cover
                try:
                    log.error(
                        "OBS-01 approval emit failed: %s",
                        json.dumps({"path": "approval", "op": "run_status", "error": str(exc)}, default=str),
                    )
                except Exception:
                    pass
            return result

        db.create_approval = wrapped_create_approval
        db.update_approval = wrapped_update_approval
        db.update_approval_run_status = wrapped_update_approval_run_status
        db._approval_recorder_patched = True

    def _emit(
        self,
        *,
        op: str,
        approval_id: Optional[str],
        tool_name: Optional[str],
        tool_call_id: Optional[str],
        run_id: Optional[str],
        agent_id: Optional[str],
        status_from: Optional[str],
        status_to: Optional[str],
        run_status: Optional[str],
        resolved_by: Optional[str],
        latency_ms: int,
        status: str,
        error_type: Optional[str] = None,
        error_msg: Optional[str] = None,
        tool_args_summary: Optional[str] = None,
    ) -> None:
        record: dict = {
            "path": "approval",
            "op": op,
            "approval_id": approval_id,
            "tool_name": tool_name,
            "tool_call_id": tool_call_id,
            "run_id": run_id,
            "agent_id": agent_id,
            "status_from": status_from,
            "status_to": status_to,
            "run_status": run_status,
            "resolved_by": resolved_by,
            "latency_ms": latency_ms,
            "status": status,
        }
        if tool_args_summary is not None:
            record["tool_args_summary"] = tool_args_summary
        if error_type is not None:
            record["error_type"] = error_type
        if error_msg is not None:
            record["error_msg"] = error_msg

        if status == "error":
            log.error("OBS-01 approval write failed: %s", json.dumps(record, default=str))
        else:
            log.info("OBS-01 approval write: %s", json.dumps(record, default=str))


def patch_db_for_approval_recording(db: Any) -> None:
    """Module-level entry point. Idempotent instance-level patch of db approval methods.

    Call once after db is constructed (mirrors patch_classes_for_recording in
    eval_recorder.py).  Re-calls on the same db object are no-ops.
    """
    ApprovalRecorder(db=db).patch()
