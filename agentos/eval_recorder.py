"""OBS-01 instrumented eval recorder — wraps Agent/Team run() / arun()
and writes one EvalRunRecord per run via db.create_eval_run."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional

from agno.db.schemas.evals import EvalRunRecord, EvalType

log = logging.getLogger("agentos.eval")
log.setLevel(logging.INFO)
if not log.handlers and not logging.getLogger().handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(_h)
    log.propagate = False


class InstrumentedEvalRecorder:
    """Post-run wrapper. Attach to an Agent or Team with .wrap(agent).

    Replaces agent.run and agent.arun with closures that call the original
    then write an EvalRunRecord (eval_type=AGENT_AS_JUDGE, score=null —
    live traffic is metadata-only at write time; suite scoring is plan 12-02).
    """

    def __init__(self, db: Any) -> None:
        self.db = db

    def wrap(self, agent: Any) -> Any:
        original_run = agent.run
        original_arun = agent.arun
        agent_id = getattr(agent, "id", None) or getattr(agent, "name", None)
        recorder = self

        def instrumented_run(*args, **kwargs):
            started = time.monotonic()
            try:
                response = original_run(*args, **kwargs)
            except Exception:
                recorder._record(None, args, kwargs, agent_id, started, error=None)
                raise
            recorder._record(response, args, kwargs, agent_id, started, error=None)
            return response

        async def instrumented_arun(*args, **kwargs):
            started = time.monotonic()
            try:
                response = await original_arun(*args, **kwargs)
            except Exception:
                raise
            await asyncio.to_thread(
                recorder._record, response, args, kwargs, agent_id, started, None
            )
            return response

        agent.run = instrumented_run
        agent.arun = instrumented_arun
        agent._eval_recorder = self
        return agent

    # internal -----------------------------------------------------------

    def _record(self, response, args, kwargs, agent_id, started, error):
        latency_ms = int((time.monotonic() - started) * 1000)
        record = self._build_eval_record(response, args, kwargs, agent_id, latency_ms, error)

        status = "ok"
        error_type: Optional[str] = None
        error_msg: Optional[str] = None
        try:
            self.db.create_eval_run(record)
        except Exception as exc:
            status = "error"
            error_type = exc.__class__.__name__
            error_msg = str(exc)[:200]
            # swallow — OBS-01 captures the failure; agent reply still returns.

        self._emit(
            agent_id=agent_id,
            db_id=getattr(self.db, "id", None),
            row_id=record.run_id if status == "ok" else None,
            latency_ms=latency_ms,
            status=status,
            eval_type=EvalType.AGENT_AS_JUDGE.value,
            model_provider=record.model_provider,
            model_id=record.model_id,
            score=None,
            case_id=None,
            error_type=error_type,
            error_msg=error_msg,
        )

    def _build_eval_record(self, response, args, kwargs, agent_id, latency_ms, error) -> EvalRunRecord:
        run_id = getattr(response, "run_id", None) or str(uuid.uuid4())
        model_id, model_provider = self._extract_model(response)
        return EvalRunRecord(
            run_id=run_id,
            eval_type=EvalType.AGENT_AS_JUDGE,
            agent_id=agent_id,
            model_id=model_id,
            model_provider=model_provider,
            eval_input=self._extract_input(args, kwargs),
            eval_data={
                "output": self._dump_output(response),
                "latency_ms": latency_ms,
                "model_id": model_id,
                "model_provider": model_provider,
                "status": "ok" if error is None else "error",
                "score": None,
            },
        )

    def _extract_model(self, response) -> tuple[Optional[str], Optional[str]]:
        model = getattr(response, "model", None)
        if model is None:
            return None, None
        return getattr(model, "id", None), getattr(model, "provider", None)

    def _extract_input(self, args, kwargs) -> dict:
        user_message: Any = None
        if args:
            user_message = args[0]
        elif "message" in kwargs:
            user_message = kwargs["message"]
        return {"user_message": str(user_message) if user_message is not None else None}

    def _dump_output(self, response) -> Any:
        if response is None:
            return None
        content = getattr(response, "content", None)
        if hasattr(content, "model_dump"):
            return content.model_dump()
        return content

    def _emit(self, **fields) -> None:
        record = {"path": "eval"}
        record.update(fields)
        if fields.get("status") == "error":
            log.error("OBS-01 eval write failed: %s", json.dumps(record, default=str))
        else:
            log.info("OBS-01 eval write: %s", json.dumps(record, default=str))


def patch_classes_for_recording(db: Any) -> None:
    """Class-level patch of Agent.run / Agent.arun / Team.run / Team.arun
    so eval rows are written even when Agno deep_copies instances per HTTP
    request. Instance-level wrap() (above) does NOT survive Agno's
    `agent.deep_copy()` call in the HTTP route — fresh copies lose
    the instance-set arun. This patch is class-level, so deep_copy clones
    inherit the instrumentation automatically. Idempotent — re-calls are
    no-ops.

    Streaming and background paths are pure pass-through (no row write):
    Agno returns an async-iterator when stream=True/background=True, which
    the wrapper cannot await + instrument without consuming the stream
    twice. Non-streaming (stream=False, the AgentOS standard for
    /agents/{id}/runs with stream form-field unset or false) is the
    instrumented path."""
    from agno.agent.agent import Agent
    from agno.team.team import Team

    recorder = InstrumentedEvalRecorder(db=db)

    for cls in (Agent, Team):
        if getattr(cls, "_eval_recorder_patched", False):
            continue

        original_run = cls.run
        original_arun = cls.arun

        def make_run(orig):
            def patched_run(self, *args, **kwargs):
                if kwargs.get("stream", False) or kwargs.get("background", False):
                    return orig(self, *args, **kwargs)
                started = time.monotonic()
                try:
                    response = orig(self, *args, **kwargs)
                except Exception:
                    raise
                recorder._record(response, args, kwargs, getattr(self, "id", None), started, None)
                return response

            return patched_run

        def make_arun(orig):
            def patched_arun(self, *args, **kwargs):
                if kwargs.get("stream", False) or kwargs.get("background", False):
                    return orig(self, *args, **kwargs)

                async def _wrapped():
                    started = time.monotonic()
                    response = await orig(self, *args, **kwargs)
                    await asyncio.to_thread(
                        recorder._record,
                        response,
                        args,
                        kwargs,
                        getattr(self, "id", None),
                        started,
                        None,
                    )
                    return response

                return _wrapped()

            return patched_arun

        cls.run = make_run(original_run)
        cls.arun = make_arun(original_arun)
        cls._eval_recorder_patched = True
        cls._eval_recorder = recorder
