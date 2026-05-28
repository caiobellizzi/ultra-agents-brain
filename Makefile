.PHONY: test eval-smoke eval-full check-surfaces

test:
	PYTHONPATH=. .venv/bin/pytest tests/ --ignore=tests/test_core.py -q

eval-smoke:
	PYTHONPATH=. .venv/bin/pytest evals/ -k smoke -q

eval-full:
	EVAL_JUDGE_TIER=orchestrator PYTHONPATH=. .venv/bin/pytest evals/ -q

check-surfaces:
	PYTHONPATH=. .venv/bin/python scripts/check_surfaces.py
