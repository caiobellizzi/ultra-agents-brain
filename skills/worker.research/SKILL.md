---
name: worker.research
description: Ephemeral bounded research worker that searches, fetches, extracts, summarizes with citations, and returns structured Markdown for aggregation.
---

# worker.research

## Purpose

Perform one bounded research subtask inside a fan-out plan. Search or fetch sources, extract content, summarize findings with citations, report confidence, and return structured Markdown to the orchestrator for aggregation into `synthesis.md` and `_briefing.md`.

## Triggers

- Orchestrator receives "research X" and creates parallel subtasks.
- Brain query finds a knowledge gap and user approves external research.
- Weekly review requests follow-up research.

## Required Env/Config

- Web search tool or MCP configured by Hermes.
- Crawl4AI/Jina/local extraction path shared with `brain.ingest`.
- LiteLLM Tier B by default; Tier C for mechanical extraction/high-throughput tasks.
- Per-worker timeout and budget from orchestrator.
- Cost ledger/trust gate helper.

## Expected Inputs

- `subtask`: narrow research question or angle.
- `scope`: allowed source types, date range, domains, or exclusions.
- `budget_usd`: max USD 1 per subtask by default.
- `timeout_seconds`.
- `citation_format`: source URL plus retrieved title/date when available.

## Expected Outputs

- Structured Markdown summary using `prompts/research-summary.md`.
- Source list with URL, title, date, retrieval status, and relevance.
- Claims separated by confidence.
- Failure/coverage notes for the aggregator.

## Cost/Trust Constraints

- Per-worker cap USD 1.
- Parent research task cap USD 5; deep research cap USD 10 only when explicitly requested.
- Use Tier C for broad scanning, Tier B for final worker summary.
- Do not perform code execution or destructive external actions.
- Respect robots/terms constraints exposed by extraction tools.
- Private research context must use Tier D/private worker or be refused.

## Relevant Helper Modules

- `skills/worker.research/loop.py`: plan search angle, search/fetch, scrape/extract, summarize loop.
- `brain.ingest` extractor helper.
- Research fan-out orchestration helper from task 08.
- Cost ledger/trust gate helper from task 06.

## Failure Handling

- Worker failure should not fail the whole research task unless quorum is impossible.
- Return partial findings with explicit coverage gaps.
- If search yields low-quality sources, say so and suggest refined subtask terms.
- Stop when budget or timeout is reached and mark the summary partial.
