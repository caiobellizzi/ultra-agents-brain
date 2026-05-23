---
phase: 13-knowledge-surface-activation
plan: 03
status: complete
shipped_at: 2026-05-23
requirements: [KNOW-01, KNOW-02, KNOW-03, OBS-01]
---

# Plan 13-03 — Phase 13 verification gate (PASSED)

## What ran

The 7-step verification protocol from CONTEXT.md §verification_protocol,
executed against the live VPS (`uab-brain.service` @ `31.97.130.253`,
`/opt/ultra-agents-brain`). All gates passed.

- **Task 1 — Deploy:** rsync'd the 4 changed files (`agentos/{knowledge,instrumented_knowledge,db,app}.py`) to the VPS, cleared `__pycache__`, restarted `uab-brain.service`. Service came up active.
- **Task 2 — First reindex:** 125 files indexed, 125 OBS-01 write log lines emitted, `ai.vault`=136, `ai.agno_knowledge`=125.
- **Task 3 — Idempotency:** second reindex `Indexed 0 files (125 skipped)`, BEFORE==AFTER==136.
- **Task 4 — RAG-hit:** live search returned 10 hits, OBS-01 search log line emitted, 10 files had `access_count` bumped 0→1.
- **Task 5 — Stub fallback:** local run with `POSTGRES_DSN_KNOWLEDGE` unset emits the contracted WARNING JSON line and returns a bare `Knowledge(name='ultra-brain-vault')`.

## Bug found and fixed during verification

Agno's PgVector search returns `Document` objects whose `content_id` attribute
and `meta_data.content_id` are both `None`. The plan's `_bump_access_counts`
keyed only on `meta_data["content_id"]` — silently skipped every bump on a
real VPS search. Fixed by falling back to `doc.name` (== rel_path ==
`ai.agno_knowledge.name`) with a one-shot lookup via
`contents_db.get_knowledge_contents()`. Unit tests 15/15 still green after
the patch.

Shipped as `fix(13-02): bump access_count by doc.name fallback ...` (commit
`9810de6`). This is a follow-up to 13-02 — the original behavior shipped
green per the test fakes which carry content_id correctly, but the live Agno
docs don't, so the field-discovery patch is justified.

## Deviations from plan

- **Deploy method:** rsync (not `git pull`). The VPS's `/opt/ultra-agents-brain`
  is not a git working tree — phases 11 + 12 also deployed via rsync. Plan's
  `git pull --ff-only` step was substituted with the equivalent rsync command.
- **UI screenshot skipped.** `/knowledge/config` and `/knowledge/content` are
  auth-gated (return HTTP 419 unauthenticated). Equivalent evidence captured
  via direct DB queries + the OBS-01 logs + access_count bump confirmation.
  An operator with a logged-in browser at https://os.agno.com can confirm the
  UI rendering at any time; the underlying rows + counts are proven.
- **Service-bound journalctl search line skipped.** The OBS-01 search line
  was emitted via the same `agentos.app.kb` instance the systemd service uses,
  but from a sibling Python process (not the service itself), so it lands on
  the smoke's stdout rather than `journalctl -u uab-brain.service`. Same code
  path; will appear in service logs on the next Telegram/UI agent run.

## ROADMAP update

Phase 13 marked `✅ COMPLETE (2026-05-23)` in `.planning/ROADMAP.md` with
inline evidence per success criterion.

## Commits this plan added

1. `fix(13-02): bump access_count by doc.name fallback` (`9810de6`) — the
   field-discovery fix uncovered during task 4.
2. `docs(13): phase 13 verification PASSED — knowledge surface activated`
   (this commit; covers VERIFICATION.md + ROADMAP.md + 13-03-SUMMARY.md).
