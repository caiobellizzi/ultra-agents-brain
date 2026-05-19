---
name: brain.review
description: Weekly review of Projects, Areas, archive candidates, stale work, and TELOS alignment proposals.
---

# brain.review

## Purpose

Run a weekly operating review of the second brain. Surface stale Projects, dormant Areas, archive candidates, unresolved decisions, accumulated lint findings, and TELOS alignment concerns once TELOS exists.

## Triggers

- Weekly cron, expected Sunday 18:00 local time.
- Manual command such as "weekly review", "review my brain", or "what should I archive?".
- Pre-archive approval flow.

## Required Env/Config

- `SECOND_BRAIN_ROOT`, vault `CLAUDE.md`, `_system/log.md`, `_system/lint-report.md`, and cost ledger.
- Optional `_system/telos.md` and `_system/telos/*.md`.
- LiteLLM Tier A for review synthesis because recommendations can affect priorities.
- Telegram approval channel for medium-risk actions.

## Expected Inputs

- Optional `date_range`, default last 7 days.
- Optional `scope`: all vault, Projects, Areas, or specific folder.
- Optional TELOS context when available.

## Expected Outputs

- Weekly review Markdown summary.
- Telegram summary with recommended actions.
- Archive/action proposals only; no automatic medium-risk moves.
- TELOS alignment notes and feed/topic suggestions.
- Append-only review log entry.

## Cost/Trust Constraints

- Weekly review target cost USD 0.20-0.70, amortized daily budget under USD 1.
- Proposals are low risk. Moving files, archiving Projects, changing Areas, or altering TELOS is medium risk and requires approval.
- High-risk destructive actions such as deletion are forbidden.
- Strip private blocks before cloud LLM calls unless Tier D/private worker is used.

## Relevant Helper Modules

- No dedicated helper in the plan for v1; expected to reuse `brain.query` retrieval and `brain.lint` reports.
- `telos.check` for alignment scoring once wired.
- Cost ledger/trust gate helper from task 06.

## Failure Handling

- If TELOS is absent, run a non-TELOS review and include a note that alignment scoring is skipped.
- If lint report is stale or missing, review logs and Projects directly.
- If budget is exceeded, produce a partial review with scanned scopes.
