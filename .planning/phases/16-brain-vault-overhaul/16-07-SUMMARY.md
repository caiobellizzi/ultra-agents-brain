---
plan: 16-07
phase: 16-brain-vault-overhaul
status: complete
completed: 2026-05-26
self_check: PASSED
---

## What Was Built

Wired the `review` subcommand in `ultra_brain/__main__.py` to the new Telegram-based review functions. Three surgical changes:

1. **Import line** — extended to include `weekly_review_draft` and `send_weekly_review_telegram`
2. **Review subparser** — added `--dry-run` flag (`action="store_true"`, prints draft without sending Telegram)
3. **Review handler** — replaced `write_weekly_review()` dispatch with:
   - `dry_run=True` → calls `weekly_review_draft(vault)`, prints draft + sweep_id to stdout
   - `dry_run=False` → calls `send_weekly_review_telegram(vault)`, sends to Telegram with HITL buttons

The old `write_weekly_review` import is preserved (it may be used elsewhere or needed for migration).

## Verification

```
$ python3 -m ultra_brain --vault vault review --dry-run
🧠 *Weekly Brain Review*
📥 Inbox: 157 item(s) awaiting decision
...
[DRY RUN] sweep_id=782396589f2c — no Telegram message sent.
```

Note: `--vault` is on the root parser (standard argparse convention), so it goes before the subcommand: `ultra-brain --vault <path> review [--dry-run]`.

## Key Files

- `ultra_brain/__main__.py` — review handler wired to new functions, --dry-run added

## Commits

- `feat(16-07): wire review CLI to send_weekly_review_telegram with --dry-run`

## Self-Check

- [x] `grep -c 'send_weekly_review_telegram' ultra_brain/__main__.py` → 2 (import + call)
- [x] `grep -c 'weekly_review_draft' ultra_brain/__main__.py` → 2 (import + call)
- [x] `python3 -m ultra_brain review --help` shows `--dry-run` flag
- [x] `python3 -m ultra_brain --vault vault review --dry-run` exits 0 with draft + [DRY RUN] line
- [x] `grep -c 'write_weekly_review' ultra_brain/__main__.py` → 1 (preserved)
