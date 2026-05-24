from __future__ import annotations

from agno.db.schemas.evals import EvalRunRecord, EvalType

from agentos.live_judge import JudgeDecision, run_live_judge_once


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.created = []
        self.last_kwargs = None

    def get_eval_runs(self, **kwargs):
        self.last_kwargs = kwargs
        return list(self.rows)

    def create_eval_run(self, record):
        self.created.append(record)
        return record


class _FakeJudge:
    model_id = "judge-model"

    def evaluate(self, *, rubric, judge_input):
        return JudgeDecision(score=1.0, passed=True, reason=f"ok:{rubric.rubric_id}")


def _parent(agent_id="chat", output="hello"):
    return EvalRunRecord(
        run_id="parent-1",
        eval_type=EvalType.PERFORMANCE,
        agent_id=agent_id,
        name=f"live:{agent_id}",
        evaluated_component_name=agent_id,
        model_id="private-worker",
        model_provider="litellm",
        eval_input={"user_message": "hi"},
        eval_data={
            "output": output,
            "status": "ok",
            "score": None,
            "judge_status": "pending",
            "judge_attempts": 0,
        },
    )


def test_live_judge_writes_child_row_and_marks_parent_judged():
    parent = _parent()
    db = _FakeDb([parent])

    result = run_live_judge_once(db, judge=_FakeJudge(), limit=10)

    assert result.judged == 1
    assert len(db.created) == 1
    child = db.created[0]
    assert child.eval_type == EvalType.AGENT_AS_JUDGE
    assert child.name.startswith("eval-live:chat:")
    assert child.evaluated_component_name == "chat"
    assert child.eval_data["parent_run_id"] == "parent-1"
    assert child.eval_data["score"] == 1.0
    assert child.run_id == f"judge:parent-1:{child.eval_data['rubric_id']}:judge-model"
    assert parent.eval_data["judge_status"] == "judged"


def test_live_judge_skips_privacy_sensitive_parent_without_calling_judge():
    parent = _parent(output={"api_key": "sk-secret"})
    db = _FakeDb([parent])

    result = run_live_judge_once(db, judge=_FakeJudge(), limit=10)

    assert result.judged == 0
    assert result.skipped == 1
    assert db.created == []
    assert parent.eval_data["judge_status"] == "skipped_privacy"
