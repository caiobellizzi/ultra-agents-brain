# 12-03 Task 3 — Tier-swap evidence (EVAL-03)

**Date:** 2026-05-23
**Host:** srv847330 (root@31.97.130.253)
**Suite file:** `evals/test_curator.py` (3 parametrized cases)
**Tiers compared:** `EVAL_JUDGE_TIER=private-worker` vs `EVAL_JUDGE_TIER=orchestrator`

## Tier 2 run

```bash
ssh root@31.97.130.253 'cd /opt/ultra-agents-brain && set -a && . ./.env && set +a && \
  EVAL_JUDGE_TIER=orchestrator .venv/bin/pytest evals/test_curator.py -q -m "not live"'
```

```
........                                                                 [100%]
8 passed in 0.34s
```

## Snapshot after tier 2

```
accuracy_count_total=6
recent=6
{'jm': 'orchestrator', 'tier': 'orchestrator', 'run_id': 'suite-3fc49a0a-2170-4ce9-84a3-14a6021da023-...curator-1'}
{'jm': 'orchestrator', 'tier': 'orchestrator', 'run_id': 'suite-3fc49a0a-2170-4ce9-84a3-14a6021da023-...curator-2'}
{'jm': 'orchestrator', 'tier': 'orchestrator', 'run_id': 'suite-3fc49a0a-2170-4ce9-84a3-14a6021da023-...curator-3'}
{'jm': 'private-worker', 'tier': 'private-worker', 'run_id': 'suite-1067b9f7-1831-4172-9e7c-5a552fe76a6c-...curator-1'}
{'jm': 'private-worker', 'tier': 'private-worker', 'run_id': 'suite-1067b9f7-1831-4172-9e7c-5a552fe76a6c-...curator-2'}
{'jm': 'private-worker', 'tier': 'private-worker', 'run_id': 'suite-1067b9f7-1831-4172-9e7c-5a552fe76a6c-...curator-3'}
```

## Set comparison

- Tier 1 `judge_model` set: `{"private-worker"}`
- Tier 2 `judge_model` set: `{"orchestrator"}`
- Intersection: `∅` (empty)
- **disjoint: yes**

## Row-count deltas

- Tier 1 run: 0 → 3 (+3)
- Tier 2 run: 3 → 6 (+3)

Each tier produced exactly one row per parametrized case (3/3), with distinct `eval_test_run_id` uuids — F7 contract holds (deterministic per-session, disjoint across sessions).

## Note on the model identifiers

The `judge_model` field in `eval_input` carries the **tier name** (`"private-worker"` / `"orchestrator"`), not the underlying model id (e.g., `"openai/gpt-4o"`). `agentos.model.chat_model(tier)` resolves the tier string to a `LiteLLMChat` instance whose `.id` attribute is the same tier name pattern. The two tier strings are different by configuration — that is the property EVAL-03 cares about: a config knob produces measurably distinct rows.

If the operator wants the actual underlying provider/model id, that would come from `agentos/model.py` LiteLLM dispatch — out of scope for plan 12-03 closeout (the data is captured; the cross-walk is a query rather than a code change).

## EVAL-03 verdict: PASSED

Tier swap produces disjoint judge_model sets and the same case_id × `suite-{uuid}` reservation contract. EVAL-03 surface is alive.
