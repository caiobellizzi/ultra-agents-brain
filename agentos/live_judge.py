"""Optional worker for judging live performance eval rows."""
from __future__ import annotations

import argparse
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable

from agno.db.schemas.evals import EvalRunRecord, EvalType

from agentos.eval_live_policy import EvalLivePolicy, normalize_score
from agentos.eval_rubrics import EvalRubric, rubric_by_id, rubrics_for_agent


@dataclass(frozen=True)
class JudgeInput:
    input_text: str
    output_text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class JudgeDecision:
    score: float | None
    passed: bool
    reason: str


@dataclass(frozen=True)
class LiveJudgeRunResult:
    scanned: int = 0
    judged: int = 0
    skipped: int = 0
    failed: int = 0


class DefaultLiveJudge:
    """LLM-backed judge used by the CLI worker."""

    def __init__(self, tier: str = "private-worker") -> None:
        from agentos.model import chat_model

        self.model = chat_model(tier)
        self.model_id = getattr(self.model, "id", tier)
        self.model_provider = getattr(self.model, "provider", None)

    def evaluate(self, *, rubric: EvalRubric, judge_input: JudgeInput) -> JudgeDecision:
        from agno.eval.agent_as_judge import AgentAsJudgeEval

        evaluator = AgentAsJudgeEval(
            criteria=rubric.criteria,
            scoring_strategy="numeric" if rubric.scoring_strategy == "numeric" else "binary",
            threshold=max(1, min(10, int(round(rubric.threshold * 10)))),
            model=self.model,
            telemetry=False,
            db=None,
        )
        result = evaluator.run(input=judge_input.input_text, output=judge_input.output_text)
        if not result or not result.results:
            return JudgeDecision(score=None, passed=False, reason="judge returned no result")
        first = result.results[0]
        raw_score = {"score": first.score} if first.score is not None else {"passed": first.passed}
        return JudgeDecision(
            score=normalize_score(raw_score),
            passed=bool(first.passed),
            reason=first.reason,
        )


def run_live_judge_once(
    db: Any,
    *,
    judge: Any | None = None,
    limit: int = 10,
    policy: EvalLivePolicy | None = None,
) -> LiveJudgeRunResult:
    policy = policy or EvalLivePolicy.from_env()
    judge = judge or DefaultLiveJudge()
    rows = _get_performance_rows(db, limit=limit)

    scanned = judged = skipped = failed = 0
    for parent in rows:
        scanned += 1
        if (parent.eval_data or {}).get("judge_status") != "pending":
            skipped += 1
            continue
        if int((parent.eval_data or {}).get("judge_attempts") or 0) >= policy.max_attempts:
            _update_parent_judge_status(db, parent, "failed_max_attempts")
            skipped += 1
            continue

        privacy = policy.privacy_allows({"input": parent.eval_input, "data": parent.eval_data})
        if not privacy.allowed:
            _update_parent_judge_status(db, parent, "skipped_privacy", judge_skip_reason=privacy.reason)
            skipped += 1
            continue

        rubrics = _selected_rubrics(parent)
        if not rubrics:
            _update_parent_judge_status(db, parent, "skipped_no_rubric")
            skipped += 1
            continue

        parent_judged = False
        completed_decisions: list[tuple] = []  # (rubric, decision) pairs
        for rubric in rubrics:
            if rubric.requires_content_read and not policy.can_read_full_content(parent.agent_id):
                if not rubric.metadata_only_supported:
                    skipped += 1
                    continue
            try:
                judge_input = build_judge_input(parent, rubric=rubric, policy=policy)
                decision = judge.evaluate(rubric=rubric, judge_input=judge_input)
                child = _build_child_eval(parent, rubric=rubric, judge=judge, decision=decision, judge_input=judge_input)
                db.create_eval_run(child)
                completed_decisions.append((rubric, decision))
                parent_judged = True
                judged += 1
            except Exception as exc:
                attempts = int((parent.eval_data or {}).get("judge_attempts") or 0) + 1
                _update_parent_judge_status(
                    db,
                    parent,
                    "retry_pending" if attempts < policy.max_attempts else "failed",
                    judge_attempts=attempts,
                    judge_error_type=exc.__class__.__name__,
                    judge_error_msg=str(exc)[:200],
                )
                failed += 1

        if parent_judged:
            _update_parent_judge_status(db, parent, "judged")
            vault_path = os.environ.get("SECOND_BRAIN_DIR", "vault")
            try:
                _write_experience_note(parent, decisions=completed_decisions, vault_path=vault_path)
            except Exception as exc:
                logging.getLogger("agentos.live_judge").warning("experience note write failed: %s", exc)

    return LiveJudgeRunResult(scanned=scanned, judged=judged, skipped=skipped, failed=failed)


def build_judge_input(parent: EvalRunRecord, *, rubric: EvalRubric, policy: EvalLivePolicy) -> JudgeInput:
    eval_data = parent.eval_data or {}
    eval_input = parent.eval_input or {}
    output = eval_data.get("output")
    if rubric.requires_content_read and not policy.can_read_full_content(parent.agent_id):
        output = _metadata_only(output)
    return JudgeInput(
        input_text=_stringify(eval_input),
        output_text=_stringify(output),
        metadata={
            "parent_run_id": parent.run_id,
            "agent_id": parent.agent_id,
            "rubric_id": rubric.rubric_id,
            "model_id": eval_data.get("model_id") or parent.model_id,
            "latency_ms": eval_data.get("latency_ms"),
        },
    )


def _get_performance_rows(db: Any, *, limit: int) -> list[EvalRunRecord]:
    try:
        raw_rows = db.get_eval_runs(limit=limit, eval_type=[EvalType.PERFORMANCE])
    except TypeError:
        raw_rows = db.get_eval_runs(limit=limit)
    if isinstance(raw_rows, tuple):
        raw_rows = raw_rows[0]
    return [_coerce_record(row) for row in raw_rows]


def _coerce_record(row: Any) -> EvalRunRecord:
    if isinstance(row, EvalRunRecord):
        return row
    return EvalRunRecord.model_validate(row)


def _selected_rubrics(parent: EvalRunRecord) -> tuple[EvalRubric, ...]:
    requested = (parent.eval_data or {}).get("judge_rubric_ids")
    if requested:
        return tuple(rubric for rubric in (rubric_by_id(rid) for rid in requested) if rubric is not None)
    return rubrics_for_agent(parent.agent_id)


def _build_child_eval(
    parent: EvalRunRecord,
    *,
    rubric: EvalRubric,
    judge: Any,
    decision: JudgeDecision,
    judge_input: JudgeInput,
) -> EvalRunRecord:
    judge_model_id = getattr(judge, "model_id", None) or getattr(getattr(judge, "model", None), "id", None) or "unknown"
    judge_model_provider = getattr(judge, "model_provider", None) or getattr(getattr(judge, "model", None), "provider", None)
    return EvalRunRecord(
        run_id=f"judge:{parent.run_id}:{rubric.rubric_id}:{judge_model_id}",
        eval_type=EvalType.AGENT_AS_JUDGE,
        agent_id=parent.agent_id,
        name=f"eval-live:{parent.agent_id}:{rubric.rubric_id}",
        evaluated_component_name=parent.evaluated_component_name or parent.agent_id,
        model_id=judge_model_id,
        model_provider=judge_model_provider,
        eval_input={
            "parent_run_id": parent.run_id,
            "rubric_id": rubric.rubric_id,
            "input": judge_input.input_text,
            "metadata": judge_input.metadata,
        },
        eval_data={
            "parent_run_id": parent.run_id,
            "rubric_id": rubric.rubric_id,
            "score": decision.score,
            "passed": decision.passed,
            "reason": decision.reason,
            "judge_model_id": judge_model_id,
            "judge_model_provider": judge_model_provider,
            "status": "ok",
        },
    )


def _update_parent_judge_status(db: Any, parent: EvalRunRecord, status: str, **metadata: Any) -> None:
    parent.eval_data = dict(parent.eval_data or {})
    parent.eval_data["judge_status"] = status
    parent.eval_data.update(metadata)
    _persist_parent_eval_data(db, parent)


def _persist_parent_eval_data(db: Any, parent: EvalRunRecord) -> None:
    """Isolated SQL helper until Agno exposes an eval-run update API."""
    if not hasattr(db, "Session") or not hasattr(db, "_get_table"):
        return
    try:
        from sqlalchemy import update

        table = db._get_table(table_type="evals")
        if table is None:
            return
        with db.Session() as sess, sess.begin():
            sess.execute(
                update(table)
                .where(table.c.run_id == parent.run_id)
                .values(eval_data=parent.eval_data, updated_at=int(time.time()))
            )
    except Exception:
        raise


def _metadata_only(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            "type": "dict",
            "keys": sorted(str(key) for key in value.keys()),
            "content_redacted": True,
        }
    if isinstance(value, list):
        return {"type": "list", "count": len(value), "content_redacted": True}
    return {"type": type(value).__name__, "content_redacted": True}


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        import json

        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def _write_experience_note(
    parent: EvalRunRecord,
    *,
    decisions: list[tuple[EvalRubric, JudgeDecision]],
    vault_path: str = "vault",
) -> None:
    """Write a structured experience note to vault/_system/experiences/{agent_id}/."""
    from datetime import datetime, timezone
    from pathlib import Path

    if not decisions:
        return

    agent_id = parent.agent_id or "unknown"
    run_id = (parent.run_id or "").replace(":", "-").replace("/", "-")[:64]

    # Use best score across rubrics
    scores = [d.score for _, d in decisions if d.score is not None]
    score = round(sum(scores) / len(scores), 3) if scores else None
    passed = all(d.passed for _, d in decisions)
    status = "success" if passed else "failure"

    rubric_id = decisions[0][0].rubric_id if decisions else "unknown"
    reason = decisions[0][1].reason if decisions else ""

    eval_data = parent.eval_data or {}
    eval_input = parent.eval_input or {}
    input_summary = str(eval_input.get("user_message") or eval_input)[:500]
    output_summary = str(eval_data.get("output") or "")[:500]

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    frontmatter = f"""---
agent: {agent_id}
run_id: {run_id}
score: {score}
rubric: {rubric_id}
status: {status}
date: {date_str}
tags: [experience, {agent_id}]
---"""

    body = f"""
## Input
{input_summary}

## Score
{score} — {"passed ✓" if passed else "failed ✗"}

## What {"worked" if passed else "failed"}
{reason}

## Key pattern
{reason}
"""

    exp_dir = Path(vault_path) / "_system" / "experiences" / agent_id
    exp_dir.mkdir(parents=True, exist_ok=True)
    note_path = exp_dir / f"{date_str}-{run_id}.md"
    note_path.write_text(frontmatter + "\n" + body, encoding="utf-8")

    # Reindex immediately so the experience is searchable on the next agent run
    try:
        from agentos.knowledge import create_knowledge, reindex
        knowledge = create_knowledge()
        if knowledge is not None:
            reindex(vault_path=Path(vault_path), knowledge=knowledge)
    except Exception as exc:
        logging.getLogger("agentos.live_judge").warning("experience reindex failed: %s", exc)


def live_judge_cli(args: argparse.Namespace) -> int:
    from agentos.app import db

    def run_once() -> LiveJudgeRunResult:
        return run_live_judge_once(db, limit=args.limit)

    if args.loop:
        while True:
            result = run_once()
            print(_format_result(result), flush=True)
            time.sleep(args.interval)
    result = run_once()
    print(_format_result(result))
    return 0


def _format_result(result: LiveJudgeRunResult) -> str:
    return (
        "live-judge: "
        f"scanned={result.scanned} judged={result.judged} "
        f"skipped={result.skipped} failed={result.failed}"
    )


def iter_pending(rows: Iterable[EvalRunRecord]) -> Iterable[EvalRunRecord]:
    for row in rows:
        if (row.eval_data or {}).get("judge_status") == "pending":
            yield row
