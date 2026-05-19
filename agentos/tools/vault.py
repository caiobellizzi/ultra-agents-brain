"""Agno tool wrappers around ultra_brain modules.

Each function below is `@tool`-decorated so Agno agents can call them. The
underlying ultra_brain modules are NOT rewritten — these are thin adapters that
normalize arguments and return JSON-serialisable payloads.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from agno.tools import tool

from ultra_brain import express, ingest, lint, monitor, query, research, review

VAULT_ROOT = Path(os.environ.get("UAB_VAULT_PATH", "./vault")).expanduser().resolve()


@tool
def ingest_to_vault(source: str) -> str:
    """Extract content from a URL or local file and file it into the vault.

    Args:
        source: A URL (https://...) or local path to ingest.

    Returns:
        Path to the resulting note (or error message).
    """
    result = ingest.ingest_source(source, VAULT_ROOT)
    return str(getattr(result, "path", result))


@tool
def query_vault(question: str, *, max_hits: int = 5) -> str:
    """Search the vault and return cited answer.

    Args:
        question: Natural-language query.
        max_hits: Maximum number of vault passages to include.

    Returns:
        Synthesised answer with citations.
    """
    return query.query_vault(question, vault_root=VAULT_ROOT, max_hits=max_hits)


@tool
def research_topic(topic: str, *, max_workers: int = 3) -> str:
    """Plan and execute multi-source research on a topic, file results in vault.

    Args:
        topic: Topic to research.
        max_workers: Number of parallel research sub-tasks.

    Returns:
        Path to the aggregated research note.
    """
    subtasks = research.plan_research(topic, max_workers=max_workers)
    worker_outputs = [research.worker_summary(topic, st.angle, st.sources) for st in subtasks]
    path = research.aggregate_research(topic, worker_outputs, VAULT_ROOT)
    return str(path)


@tool
def run_digest() -> str:
    """Generate today's daily digest of vault activity."""
    return express.daily_digest(VAULT_ROOT)


@tool
def run_review() -> str:
    """Run the weekly review across the vault."""
    path = review.write_weekly_review(VAULT_ROOT)
    return str(path)


@tool
def lint_vault() -> str:
    """Lint the vault for structural issues; returns JSON list of findings."""
    findings = lint.run_lint(VAULT_ROOT)
    return json.dumps([f.__dict__ for f in findings], default=str)


@tool
def poll_feeds() -> str:
    """Poll configured RSS feeds, score items against telos, file high-signal ones."""
    result = monitor.run_poll(vault_root=VAULT_ROOT)
    return json.dumps(result, default=str)
