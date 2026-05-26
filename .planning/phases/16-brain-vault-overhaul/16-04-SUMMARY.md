---
plan: "16-04"
phase: "16-brain-vault-overhaul"
status: complete
started: 2026-05-26
completed: 2026-05-26
executor: interactive
---

# Plan 16-04 Summary — Automation Loops

## What was built

Three automation loops wired end-to-end:

**Task 1 — Daily TELOS-scored auto-triage (TDD)**
- `ultra_brain/telos_score.py` (70 lines) — extracted heuristic scorer with HIGH/MEDIUM/NEGATIVE keyword lists; `score_telos_relevance(title, body, tags) -> float`
- `ultra_brain/monitor.py` extended — new items scored on ingestion; ≥0.6 → `02-Resources/articles/`, <0.3 → `03-Archives/auto-culled/`, mid-range stays in `Inbox/` with `telos_relevance` in YAML frontmatter
- `tests/unit/test_telos_scoring.py` — 4 tests (RED→GREEN): high-relevance AI article, low-relevance news, APL esoterica, medium infra
- TDD gates: RED commit `c7ddaa4` (ImportError), GREEN commit `ba8dc7a` (4/4 pass)

**Task 2 — Weekly review draft with Telegram HITL**
- `ultra_brain/telegram.py` — `send_message_with_buttons(text, buttons, *, chat_id)` added
- `ultra_brain/review.py` — `weekly_review_draft()` (5-section: inbox count, stale projects, promotions, archives, summary), `apply_pending_sweep()`, `cancel_pending_sweep()`, `send_weekly_review_telegram()`
- `channels/telegram_adapter.py` — `_handle_review_sweep_callback()` + dispatch hook in `handle_callback()` for `review_sweep:apply:{id}` and `review_sweep:skip:{id}`

**Task 3 — Project-mirror sync on repo add**
- `agentos/workshop_registry.py` extended — `persist_registry()` detects newly added repos (diff against old JSON before overwrite), calls `_mirror_repo_to_vault()` for each
- `_mirror_repo_to_vault()` creates `vault/00-Projects/<slug>/` with `_briefing.md`, `_log.md`, `_meta.yaml` using vault CLAUDE.md templates; idempotent (existing files not overwritten)
- `_resolve_vault_root()` uses `SECOND_BRAIN_VAULT` env var or derives from registry path
- All 14 pre-existing contract tests still pass (2 skipped: fastapi not in test env, pre-existing)

## Key files

| File | Change | Lines |
|------|--------|-------|
| `ultra_brain/telos_score.py` | New | 70 |
| `ultra_brain/monitor.py` | Extended (+13 lines) | 178 |
| `tests/unit/test_telos_scoring.py` | New | 51 |
| `ultra_brain/telegram.py` | Extended (+32 lines) | 68 |
| `ultra_brain/review.py` | Extended (+100 lines) | 154 |
| `channels/telegram_adapter.py` | Extended (+21 lines) | 521 |
| `agentos/workshop_registry.py` | Extended (+89 lines) | 196 |

## Commits

- `c7ddaa4` test(16-04): add failing tests for telos_score (RED)
- `ba8dc7a` feat(16-04): telos_score.py + monitor TELOS-scored ingestion (GREEN)
- `b1a563f` feat(16-04): weekly review draft with Telegram HITL buttons
- `9740194` feat(16-04): workshop_registry auto-creates vault project mirror on repo add

## Deviations

None. All tasks executed as specified. TDD RED→GREEN discipline observed.

## Self-Check: PASSED

- `tests/unit/test_telos_scoring.py` 4/4 green
- `tests/unit/test_spec_gen.py` 4/4 green (Wave 3, no regression)
- `agentos/workshop_registry.py` 14/14 contract tests pass
- `ultra_brain/review.py` imports and `weekly_review_draft()` runs clean
- `channels/telegram_adapter.py` parses without syntax errors
