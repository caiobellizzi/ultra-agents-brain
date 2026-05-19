---
name: brain.express
description: Convert project and vault state into concise Telegram briefings, daily digests, and optional TTS-ready weekly scripts.
---

# brain.express

## Purpose

Express the brain's current state back to the user. Produce daily digests, project briefings, and optional weekly TTS-ready scripts from existing vault material, then push concise summaries to Telegram.

## Triggers

- Daily digest cron, expected around 20:00 local time.
- Completion of a `worker.research` fan-out task.
- Manual command such as "brief me", "daily digest", or "send project briefing".
- Weekly review may call this skill to deliver its summary.

## Required Env/Config

- `SECOND_BRAIN_ROOT` with readable Project logs, `_briefing.md`, and `_system/log.md`.
- Telegram delivery channel from Hermes.
- LiteLLM Tier B for daily/project synthesis; Tier C for mechanical formatting or TTS script cleanup.
- Optional TTS provider config for later weekly podcast support.
- Cost ledger/trust gate helper.

## Expected Inputs

- `briefing_type`: project, daily, weekly-script, or ad hoc.
- Optional `project_path`, `date_range`, or `scope`.
- Optional `delivery`: Telegram text by default; TTS placeholder only when configured.

## Expected Outputs

- Telegram-ready briefing with completed work, key findings, decisions needed, costs, and links/paths.
- Updated Project `_briefing.md` when called from research aggregation.
- Daily digest Markdown when scheduled.
- Optional TTS script draft; no audio generation unless provider is configured and approved.

## Cost/Trust Constraints

- Daily express target: USD 1/day or less.
- Project briefing cost should be charged to the parent research task budget.
- Summarization and Telegram delivery are low risk. TTS generation with paid provider is medium risk until cost envelope is confirmed.
- Do not expose private blocks in outbound Telegram unless user explicitly requested private-channel delivery and policy permits it.

## Relevant Helper Modules

- `skills/brain.express/tts.py`: future TTS script/audio provider wrapper.
- Research aggregation helper from task 08.
- Cost ledger/trust gate helper from task 06.

## Failure Handling

- If Telegram delivery fails, persist briefing in the vault and log delivery failure.
- If source files are missing, produce a degraded digest from `_system/log.md`.
- If cost budget is exhausted, send a minimal non-LLM status summary where possible.
