# 12-03 Task 2 — Suite tier 1 (private-worker) evidence

**Date:** 2026-05-23
**Host:** srv847330 (root@31.97.130.253)
**Tier:** `EVAL_JUDGE_TIER=private-worker`
**Suite file under test:** `evals/test_curator.py` (3 parametrized cases)

## Setup

`evals/test_curator.py::test_curator_field_assertions` extended to depend on the new `eval_recorder`, `eval_db`, `judge_model` fixtures and call `eval_recorder(score=1.0, output={...}, eval_input={...}, case_id=case["id"], agent_id="curator")` at the end of each parametrized case. The change preserves the existing assertion contract; the recorder call only triggers the suite write when `POSTGRES_DSN_SESSIONS` is set (D-10).

## Snapshot before

```
accuracy_count_total=0
recent=0
```

## Run

```bash
ssh root@31.97.130.253 'cd /opt/ultra-agents-brain && set -a && . ./.env && set +a && \
  EVAL_JUDGE_TIER=private-worker .venv/bin/pytest evals/test_curator.py -q -m "not live"'
```

```
........                                                                 [100%]
8 passed in 0.35s
```

8 tests total → 5 smoke (no recorder) + 3 integration (each calls eval_recorder once).

## Snapshot after

```
accuracy_count_total=3
recent=3
{'jm': 'private-worker', 'tier': 'private-worker', 'run_id': 'suite-1067b9f7-1831-4172-9e7c-5a552fe76a6c-evals/test_curator.py::test_curator_field_assertions[curator-1]'}
{'jm': 'private-worker', 'tier': 'private-worker', 'run_id': 'suite-1067b9f7-1831-4172-9e7c-5a552fe76a6c-evals/test_curator.py::test_curator_field_assertions[curator-2]'}
{'jm': 'private-worker', 'tier': 'private-worker', 'run_id': 'suite-1067b9f7-1831-4172-9e7c-5a552fe76a6c-evals/test_curator.py::test_curator_field_assertions[curator-3]'}
```

- ✓ Row count delta: +3 (matches the 3 parametrized integration cases)
- ✓ All rows carry `judge_model='private-worker'` in `eval_input`
- ✓ Distinct `run_id` per case (suite-{uuid}-{nodeid} pattern from `eval_test_run_id` × `request.node.nodeid` — F7 deterministic-id contract)

## EVAL-02 verdict (tier 1): PASSED

Suite write path is live. Pre-commit eval router unaffected (8 tests collected exactly as before — `evals/test_curator.py` still passes locally without DSN).
