---
name: brain.query
description: Answer questions from the Markdown second brain using qmd hybrid retrieval or ripgrep fallback, with cited synthesis and optional write-back.
---

# brain.query

## Purpose

Answer "what do we know about X?" from the vault. Retrieve relevant notes, synthesize a grounded answer with citations to vault files, state missing knowledge clearly, and optionally file durable answers back into the wiki.

## Triggers

- Telegram questions such as "what do we know about...", "find my notes on...", "summarize our knowledge of...", or "where did I save...".
- Orchestrator needs context before planning a research, review, lint, or approval action.
- User asks to turn an answer into a concept note or project note.

## Required Env/Config

- `SECOND_BRAIN_ROOT` and readable vault `CLAUDE.md`.
- `qmd` installed and indexed against the vault.
- `rg` available for fallback retrieval.
- LiteLLM model routing: Tier A for complex planning, Tier B for synthesis.
- Cost ledger/trust gate helper.

## Expected Inputs

- `question`: the user's natural-language query.
- Optional `scope`: Project, Area, Resource folder, date range, tag, entity, or concept.
- Optional `write_back`: false by default; true only when user requests durable capture.
- Optional `answer_style`: brief, normal, exhaustive, or citation-first.

## Expected Outputs

- Cited Markdown answer using vault-relative file citations.
- "Known / uncertain / missing" separation for ambiguous topics.
- Retrieval trace: qmd query terms, top files, fallback status.
- Optional new or updated wiki note when explicitly requested or approved.
- Append-only query log entry.

## Cost/Trust Constraints

- Default to Tier B synthesis; use Tier A only for broad, ambiguous, or high-impact questions.
- Keep retrieval cheap: qmd/rg first, LLM only for reranking and synthesis.
- Do not exceed per-subtask USD 1 without approval.
- Daily cap USD 20 and 80 percent warning apply.
- Read-only answers are low risk. Write-back is medium risk unless writing a new, user-confirmed note.
- Strip private blocks before cloud LLM calls; if private content is essential, use Tier D/private worker or refuse.

## Relevant Helper Modules

- `skills/brain.query/qmd_client.py`: qmd invocation, result parsing, scoring.
- Retrieval fallback helper: `rg` search plus LLM rerank.
- Cost ledger/trust gate helper from task 06.

## Failure Handling

- If qmd fails or has no index, fall back to `rg` plus rerank.
- If retrieval finds weak evidence, say so and ask whether to run `worker.research`.
- If citations cannot be produced, do not synthesize as fact; return candidate files and uncertainty.
- If write-back conflicts with existing files, request approval before changing anything.
