from __future__ import annotations

from agentos.eval_live_policy import EvalLivePolicy, normalize_score


def test_live_policy_defaults(monkeypatch):
    monkeypatch.delenv("EVAL_LIVE_JUDGE_ENABLED", raising=False)
    monkeypatch.delenv("EVAL_LIVE_SAMPLE_RATE", raising=False)
    monkeypatch.delenv("EVAL_LIVE_MAX_ATTEMPTS", raising=False)

    policy = EvalLivePolicy.from_env()

    assert policy.enabled is False
    assert policy.default_sample_rate == 0.0
    assert policy.max_attempts == 3


def test_live_policy_per_agent_sample_rate_override(monkeypatch):
    monkeypatch.setenv("EVAL_LIVE_JUDGE_ENABLED", "true")
    monkeypatch.setenv("EVAL_LIVE_SAMPLE_RATE", "0.0")
    monkeypatch.setenv("EVAL_LIVE_SAMPLE_RATE_CHAT", "0.75")

    policy = EvalLivePolicy.from_env()

    assert policy.enabled is True
    assert policy.sample_rate_for("chat") == 0.75
    assert policy.sample_rate_for("query") == 0.0


def test_live_policy_rejects_sensitive_or_oversized_payloads():
    policy = EvalLivePolicy(max_payload_chars=20)

    assert policy.privacy_allows({"text": "normal output"}).allowed is True
    assert policy.privacy_allows({"api_key": "sk-secret"}).allowed is False
    assert policy.privacy_allows({"text": "password: hunter2"}).allowed is False
    assert policy.privacy_allows({"text": "x" * 50}).allowed is False


def test_ingest_content_read_is_opt_in(monkeypatch):
    monkeypatch.delenv("EVAL_LIVE_ALLOW_CONTENT_READ", raising=False)
    policy = EvalLivePolicy.from_env()

    assert policy.can_read_full_content("ingest") is False

    monkeypatch.setenv("EVAL_LIVE_ALLOW_CONTENT_READ", "true")
    policy = EvalLivePolicy.from_env()

    assert policy.can_read_full_content("ingest") is True


def test_normalize_score_handles_binary_and_numeric_values():
    assert normalize_score({"passed": True}) == 1.0
    assert normalize_score({"passed": False}) == 0.0
    assert normalize_score({"score": 10}) == 1.0
    assert normalize_score({"score": 1}) == 0.1
    assert normalize_score(7) == 0.7
