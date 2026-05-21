---
phase: "06-wave-4-adapter"
plan: "06-01"
subsystem: "channels/telegram"
tags: ["telegram", "typed-responses", "pydantic", "hitl", "knowledge"]
dependency_graph:
  requires: ["05-01"]
  provides: ["telegram-typed-response-extraction"]
  affects: ["channels/telegram_adapter.py", "agentos/knowledge.py"]
tech_stack:
  added: []
  patterns: ["typed-response-extraction", "citation-formatting"]
key_files:
  created:
    - "ops/README.md"
  modified:
    - "channels/telegram_adapter.py"
    - "agentos/knowledge.py"
    - "tests/test_telegram_adapter.py"
decisions:
  - "note_path checked before actions_taken in extract_reply_text to handle IngestResult with empty actions_taken list"
metrics:
  duration: "10m"
  completed: "2026-05-21T01:12:43Z"
  tasks_completed: 4
  files_modified: 4
---

# Phase 06 Plan 01: Wave 4 — Telegram Adapter + Vault Reindex Summary

## One-liner

Typed agent response extraction (ChatReply/QueryAnswer/ResearchReport) wired into Telegram adapter with citation formatting and `--reindex` CLI entry point for vault seeding.

## What Was Built

The Telegram adapter now correctly extracts human-readable text from Pydantic-serialized agent responses returned by the Wave 3 agents, rather than dumping raw JSON to users. A `--reindex` entry point was added to `agentos/knowledge.py` for one-shot vault seeding post Wave 3 deployment.

### Helper functions added to `channels/telegram_adapter.py`

- `extract_reply_text(agent_response)` — dispatches on output shape: `text` (ChatReply), `answer` (QueryAnswer), `findings` (ResearchReport), `note_path` (IngestResult), `actions_taken` (CuratorResult), with string fallback
- `format_citations(citations)` — appends up to 3 source titles as `_Sources:_` block

### Integration points updated

- `route_message()` — replaced raw JSON extraction with `extract_reply_text()` + citation append
- `handle_callback()` — replaced raw JSON extraction with `extract_reply_text()`
- HITL flow (`send_approval_buttons`, callback validation) — unchanged

### Vault reindex entry point (`agentos/knowledge.py`)

`python -m agentos.knowledge --reindex` creates a `VaultKnowledge` instance, calls `load()`, and reports file count.

### Operational docs (`ops/README.md`)

New file documents the `ops/` directory contents and the vault reindex command.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed note_path/actions_taken priority in extract_reply_text**
- **Found during:** Test run — `test_extract_ingest_result_note_path` failed
- **Issue:** `actions_taken` branch checked before `note_path`. IngestResult carries both keys (`note_path` + empty `actions_taken: []`), so the `actions_taken` branch fired first, returning `"Done: "` instead of the path.
- **Fix:** Swapped check order — `note_path` checked before `actions_taken`
- **Files modified:** `channels/telegram_adapter.py`
- **Commit:** ea106ae

### Pre-existing Failures (out of scope)

Two `TestRoutingLogic` tests fail with `'supervisor' != 'chat'` — the adapter default route was changed to `supervisor` in session 19849 (Wave 1 HITL work). These failures predate this plan and are not caused by any changes here. Logged to `deferred-items.md` scope.

## Test Results

- New tests added: 9 (`TestExtractReplyText`)
- Pre-existing passing tests: 25 (telegram adapter)
- Pre-existing failing tests: 2 (`TestRoutingLogic` routing — pre-existing, out of scope)
- `test_core.py`: collection error due to missing `ultra_brain.llm` module (pre-existing, untracked file `ultra_brain/llm.py` not yet staged)

## Known Stubs

None — all extraction logic is wired to real output fields.

## Threat Flags

None — no new network endpoints or auth paths introduced.

## Self-Check: PASSED

- `channels/telegram_adapter.py` — FOUND (extract_reply_text at line 107, format_citations at line 136)
- `agentos/knowledge.py` — FOUND (`__main__` block appended)
- `ops/README.md` — FOUND (created)
- `tests/test_telegram_adapter.py` — FOUND (TestExtractReplyText class, 9 tests)
- Commit ea106ae — FOUND
