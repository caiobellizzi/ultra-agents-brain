---
name: worker.monitor
description: Low-risk autonomous RSS monitor that deduplicates feeds, captures new items to Inbox, and hands promotion to brain.ingest.
---

# worker.monitor

## Purpose

Poll low-risk RSS/Atom sources, deduplicate by canonical URL and content hash, write new low-confidence items to `Inbox/`, and let `brain.ingest` promote them into PARA. Initial feeds are placeholders; TELOS-derived feeds should replace them later.

## Triggers

- Cron every 4 hours.
- Manual command such as "poll feeds" or "monitor now".
- TELOS review updates feed candidates.

## Required Env/Config

- `SECOND_BRAIN_ROOT` with writable `Inbox/`.
- `skills/worker.monitor/feeds.yaml`.
- Dedup state store from future implementation.
- LiteLLM Tier C or Tier D for cheap relevance checks.
- Cost ledger/trust gate helper.

## Expected Inputs

- Feed configuration: URL, enabled flag, topic, default tags, max items, trust level.
- Optional TELOS relevance rules.
- Last-seen/dedup state.

## Expected Outputs

- New Inbox Markdown notes for unseen feed items.
- Dedup skip log.
- Optional low-cost relevance score and TELOS tags.
- Telegram summary only on failures, high-signal items, or manual runs.

## Cost/Trust Constraints

- Monitoring should be cheap and mostly non-LLM.
- RSS ingest is low risk when writing new Inbox files only.
- Auto-promoting to Projects/Areas is medium risk unless the rule is explicit and TELOS-backed.
- Daily USD 20 cap applies; pause LLM relevance checks when near budget.
- Private feeds require Tier D/private worker or should stay disabled.

## Relevant Helper Modules

- Future RSS polling/dedup helper from task 12.
- `brain.ingest` for Inbox promotion.
- Cost ledger/trust gate helper from task 06.

## Failure Handling

- If a feed fails, record the failure and continue polling other feeds.
- If dedup state is unavailable, avoid writing duplicates by checking existing Inbox URLs first.
- If TELOS is absent, keep placeholder feeds disabled and require manual enablement.
- If budget is exhausted, write raw feed items only when no LLM call is needed.
