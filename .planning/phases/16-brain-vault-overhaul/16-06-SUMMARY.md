---
plan: 16-06
phase: 16-brain-vault-overhaul
status: complete
completed: 2026-05-26
self_check: PASSED
---

## What Was Built

Implemented the fourth automation loop — monthly TELOS recheck:

**`ultra_brain/monthly_telos.py`** (new module):
- `monthly_telos_recheck(vault_root, *, drift_threshold=0.5, send_telegram=True, chat_id=None)`
- Iterates `vault/00-Projects/` directories, calls `score_alignment()` per project
- Sorts results: drifting projects first, then by score ascending
- Prints formatted report to stdout always
- Sends Telegram `send_message()` with drift summary when `send_telegram=True` and drift detected
- Gracefully returns `[]` if `00-Projects/` directory is absent

**`ultra_brain/__main__.py`** (3 changes):
1. Import: `from .monthly_telos import monthly_telos_recheck`
2. Subparser: `monthly-telos-recheck` with `--no-telegram` flag
3. Handler: dispatches to `monthly_telos_recheck(vault, send_telegram=not args.no_telegram)`

## Live Run Result

```
Monthly TELOS Recheck — 2026-05-26
--------------------------------------------------
  daily-briefs: 0.00 [DRIFT] — action overlaps with TELOS dont-do terms: briefs
--------------------------------------------------
Drifting: 1 / 1
Monthly TELOS recheck: 1 projects checked, 1 drifting
```

Note: `daily-briefs` project scored 0.00 because its name matches a "dont-do" term in TELOS. This is expected behavior — the loop correctly surfaces the misalignment.

## Key Files

- `ultra_brain/monthly_telos.py` — new module (monthly_telos_recheck)
- `ultra_brain/__main__.py` — monthly-telos-recheck subcommand wired

## Commits

- `feat(16-06): add monthly TELOS recheck automation loop`

## Self-Check

- [x] `python3 -c "from ultra_brain.monthly_telos import monthly_telos_recheck"` → OK
- [x] `python3 -m ultra_brain --vault vault monthly-telos-recheck --no-telegram` → exits 0
- [x] Output shows per-project scores with [DRIFT]/[ok] tags
- [x] `grep -c 'monthly-telos-recheck' ultra_brain/__main__.py` → 2
- [x] `grep -c 'monthly_telos_recheck' ultra_brain/__main__.py` → 2
- [x] `python3 -m ultra_brain monthly-telos-recheck --help` shows `--no-telegram` flag
