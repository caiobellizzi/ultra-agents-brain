---
status: partial
phase: 16-brain-vault-overhaul
source: [16-VERIFICATION.md]
started: 2026-05-26T16:10:00-03:00
updated: 2026-05-26T16:10:00-03:00
---

## Current Test

[awaiting human testing]

## Tests

### 1. SC2 live vault sweep — Inbox clean on iCloud path

expected: Running `python3 scripts/inbox_sweep.py --vault vault` leaves `vault/Inbox/` containing only `MOC.md` and `README.md` immediately after the sweep completes. The write_bytes+unlink pattern must prevent iCloud ghost copies from being left behind.

result: [pending]

### 2. SC6 Telegram review delivery — HITL buttons work

expected: Running `python3 -m ultra_brain --vault vault review` (no --dry-run) sends a Telegram message containing the weekly brain review draft with ✅/🔍 HITL buttons. Tapping a button in Telegram registers the action without error.

result: [pending]

### 3. SC6 post-commit reindex — ARCHITECTURE.md updated on commit

expected: After making a commit to the repo, `scripts/reindex_bridge.sh` triggers automatically and updates `vault/_system/ARCHITECTURE.md` with the current codebase structure. The file should have a recent timestamp.

result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
