---
name: brain.lint
description: Nightly hygiene for the second brain: contradictions, stale claims, orphan pages, missing links, and progressive summarization candidates.
---

# brain.lint

## Purpose

Maintain the vault as a useful wiki instead of a capture dump. Run scheduled and manual passes that find contradictions, stale claims, orphan pages, missing cross-links, duplicate notes, and Forte progressive summarization candidates. Write findings to `_system/lint-report.md`.

## Triggers

- Nightly cron, expected around 02:00 UTC.
- Manual Telegram command such as "lint brain" or "run vault hygiene".
- Pre-weekly-review context gathering.

## Required Env/Config

- `SECOND_BRAIN_ROOT`, vault `CLAUDE.md`, and `_system/index.md`.
- qmd or rg for vault search.
- LiteLLM Tier B model with prompt caching enabled.
- Cost ledger/trust gate helper with USD 3 per lint run cap.
- Writable `_system/lint-report.md` and append-only logs.

## Expected Inputs

- Optional `scope`: all vault, Project path, Area path, or changed-since date.
- Optional `passes`: contradictions, stale claims, orphans, missing-links, duplicates, distill-candidates.
- Optional `apply`: false by default. Reports only unless explicitly approved.

## Expected Outputs

- `_system/lint-report.md` with dated findings, severity, affected files, suggested action, and confidence.
- Candidate progressive summarization queue: raw to highlighted, highlighted to summarized, summarized to executive.
- Append-only lint entry in `_system/log.md`.
- Telegram summary with counts and top risks.

## Cost/Trust Constraints

- Hard cap USD 3 per lint run; stop early and report partial progress if reached.
- Use qmd/rg structural checks before LLM calls.
- Prompt-cache vault schema, index, and recent log context.
- Reports are low risk. Applying edits, archiving, or deleting is medium/high risk and must not happen in this instruction-only version.
- Private blocks are stripped for cloud LLM calls; private-only findings require Tier D/private worker.

## Relevant Helper Modules

- `skills/brain.lint/lint_passes.py`: structural and LLM-assisted pass orchestration.
- qmd/ripgrep retrieval helper from `brain.query`.
- Cost ledger/trust gate helper from task 06.

## Failure Handling

- If full-vault lint exceeds budget, emit a partial report with completed scopes.
- If qmd is unavailable, use rg and filesystem traversal.
- If a contradiction is low confidence, mark it as "needs human review" instead of rewriting notes.
- If report write fails, return findings in Telegram and state that persistence failed.
