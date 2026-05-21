#!/usr/bin/env bash
# precommit_eval_router.sh — maps staged agent files to scoped eval runs.
# Called by .pre-commit-config.yaml on every commit.
# Exit 0 = pass, non-zero = block commit.
set -euo pipefail

STAGED=$(git diff --cached --name-only 2>/dev/null || true)

EVALS_TO_RUN=""

for file in $STAGED; do
  case "$file" in
    agentos/agents/chat.py)       EVALS_TO_RUN="$EVALS_TO_RUN evals/test_chat.py" ;;
    agentos/agents/curator.py)    EVALS_TO_RUN="$EVALS_TO_RUN evals/test_curator.py" ;;
    agentos/agents/ingest.py)     EVALS_TO_RUN="$EVALS_TO_RUN evals/test_ingest.py" ;;
    agentos/agents/query.py)      EVALS_TO_RUN="$EVALS_TO_RUN evals/test_query.py" ;;
    agentos/agents/research.py)   EVALS_TO_RUN="$EVALS_TO_RUN evals/test_research.py" ;;
    agentos/agents/supervisor.py) EVALS_TO_RUN="$EVALS_TO_RUN evals/test_supervisor.py" ;;
    agentos/knowledge.py)         EVALS_TO_RUN="$EVALS_TO_RUN evals/test_query.py evals/test_research.py" ;;
    agentos/model.py|agentos/app.py|agentos/schemas.py) EVALS_TO_RUN="evals/" ;;
  esac
done

# Deduplicate while preserving order
EVALS_TO_RUN=$(echo "$EVALS_TO_RUN" | tr ' ' '\n' | awk '!seen[$0]++' | tr '\n' ' ' | xargs)

if [ -z "$EVALS_TO_RUN" ]; then
  exit 0  # No relevant agent files staged — skip evals
fi

echo "[precommit-evals] Running scoped evals: $EVALS_TO_RUN"
PYTHONPATH=. .venv/bin/pytest $EVALS_TO_RUN -k "smoke" --tb=short -q
