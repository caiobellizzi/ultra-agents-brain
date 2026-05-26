---
phase: 16-brain-vault-overhaul
verified: 2026-05-26T18:45:00-03:00
status: gaps_found
score: 4/6 success criteria verified
overrides_applied: 0
gaps:
  - truth: "Inbox/ contains only MOC.md and README.md after sweep; all original items are archived or promoted"
    status: failed
    reason: "iCloud APFS unlink bug not fully resolved at vault level. inbox_sweep.py wrote_bytes+unlink fix works for new runs but the May 26 sweep left all 130 original items in Inbox/ (duplicated in 03-Archives/ and 02-Resources/). Inbox currently contains 130 non-system .md files alongside MOC.md and README.md."
    artifacts:
      - path: "vault/Inbox/"
        issue: "132 .md files present (130 non-system); should be 2 after sweep"
      - path: "scripts/inbox_sweep.py"
        issue: "write_bytes+unlink fix is in the script code but the executed sweep left source files intact — evidence: same filenames appear in both Inbox/ and 03-Archives/inbox-sweep-2026-05/ with different MD5 hashes (archive has enriched frontmatter, inbox has originals)"
    missing:
      - "Re-run scripts/inbox_sweep.py against the current vault state to remove duplicates from Inbox/"
      - "Verify unlink actually deletes source files on iCloud-backed APFS (test outside worktree)"

  - truth: "Monthly TELOS recheck automation loop produces its expected artifact when triggered"
    status: failed
    reason: "Monthly TELOS recheck loop is entirely absent from the codebase. No code in ultra_brain/, agentos/, or scripts/ implements a monthly scoring pass of vault projects against TELOS goals. The operating-manual.md documents this loop in the cadence table but no implementation exists."
    artifacts:
      - path: "ultra_brain/"
        issue: "No monthly_telos_recheck, telos_recheck, or similar function exists in any module"
    missing:
      - "Implement monthly TELOS recheck: score vault/00-Projects/ items against telos.md goals; flag drift via Telegram"
      - "Add CLI entry point so it is runnable on demand"

  - truth: "Each automation loop is runnable on demand via CLI without requiring a full cron trigger"
    status: partial
    reason: "Two of the four loops have CLI issues. (1) Weekly review CLI (python3 -m ultra_brain review) calls the old write_weekly_review() function, not the new weekly_review_draft() + Telegram HITL path. The --dry-run flag specified in the plan acceptance criteria does not exist. (2) Monthly TELOS recheck has no CLI at all (loop not implemented — see above gap). Daily triage and project-mirror sync are correctly callable."
    artifacts:
      - path: "ultra_brain/__main__.py"
        issue: "Line 149-152: 'review' command dispatches to write_weekly_review(), not send_weekly_review_telegram() or weekly_review_draft()"
      - path: "ultra_brain/review.py"
        issue: "No --dry-run support; weekly_review_draft() + Telegram HITL is not exposed via CLI"
    missing:
      - "Wire ultra_brain/__main__.py 'review' subcommand to call send_weekly_review_telegram() (or weekly_review_draft() for --dry-run)"
      - "Add --dry-run and --vault flags to the review CLI subcommand"

deferred:
  - truth: "One SPEC.md generated from brain and accepted by ultra-workshop /build on a real feature"
    addressed_in: "v3.0 (ultra-workshop)"
    evidence: "ROADMAP.md: 'v3.0 — ultra-workshop. Separate repo. Agno orchestrator + OpenHands coder sandbox. Reads from Brain via HTTP. Begins only after v2.0 has been running daily for 2–4 weeks.' The ultra-workshop /build endpoint does not yet exist."
---

# Phase 16: Brain Vault Overhaul Verification Report

**Phase Goal:** Fill TELOS, clean inbox, write operating manual, build brain→SPEC.md generator, wire automation loops (daily triage, weekly review, monthly TELOS recheck, project-mirror sync).
**Verified:** 2026-05-26T18:45:00-03:00
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC1 | `ultra_brain telos` reports TELOS `active` with all four sub-docs non-empty | VERIFIED | `vault/_system/telos.md` status: active (19 lines); mission.md (12), quarter-goals.md (32), values.md (37), dont-do.md (35) — all non-empty, no placeholder text |
| SC2 | `Inbox/` contains only MOC.md and README.md after sweep; all original items are archived or promoted | FAILED | 130 non-system .md files remain in `vault/Inbox/`. 123 are duplicated in `03-Archives/inbox-sweep-2026-05/` (different MD5 — enriched versions). iCloud APFS unlink did not delete source files. |
| SC3 | `_system/operating-manual.md` exists, scannable in <5 min, contains cadence table and spec checklist | VERIFIED | 247 lines, status: active, 4-row cadence table confirmed, 7 spec checklist items, wikilinks to [[telos]], [[quarter-goals]], [[dont-do]] present |
| SC4 | codebase-memory-mcp reindexes on git commit; `vault/repos/<repo>/ARCHITECTURE.md` written after reindex | VERIFIED | `vault/repos/ultra-agents-brain/ARCHITECTURE.md` exists (991 bytes, written 2026-05-26); `scripts/reindex_bridge.sh` (89 lines, executable) exits 0 always |
| SC5 | One SPEC.md generated from brain and accepted by ultra-workshop `/build` on a real feature | DEFERRED | ultra-workshop v3.0 is a future milestone. `generate_spec()` function is implemented and produces all 8 required sections — the generator half is done. The `/build` acceptance half requires ultra-workshop which does not exist yet. |
| SC6 | All four automation loops produce their expected artifact when triggered | PARTIAL/FAILED | Daily triage: VERIFIED. Project-mirror sync: VERIFIED. Weekly review: PARTIAL (Telegram code exists but CLI doesn't route to it). Monthly TELOS recheck: FAILED (not implemented). |

**Score:** 3/5 verifiable criteria pass (SC5 deferred; SC6 counted as failed due to 2 of 4 loops broken)

### Deferred Items

Items not yet met but addressed in later milestone phases.

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | One SPEC.md generated from brain and accepted by ultra-workshop `/build` | v3.0 (ultra-workshop) | ROADMAP.md: v3.0 is a separate repo gated on 2-4 weeks of v2.0 production operation; the `/build` endpoint does not exist in this phase. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `vault/_system/telos.md` | TELOS root doc, status: active, ≥10 lines | VERIFIED | 19 lines, status: active |
| `vault/_system/telos/mission.md` | Mission statement, ≥5 lines | VERIFIED | 12 lines, status: active |
| `vault/_system/telos/quarter-goals.md` | Q2 2026 measurable goals, ≥10 lines | VERIFIED | 32 lines, status: active |
| `vault/_system/telos/values.md` | Four values with in-practice rules, ≥15 lines | VERIFIED | 37 lines, status: active |
| `vault/_system/telos/dont-do.md` | Negative prior lists, ≥15 lines | VERIFIED | 35 lines, status: active |
| `scripts/inbox_sweep.py` | One-shot TELOS-scored inbox sweep, ≥60 lines | VERIFIED | 389 lines; --dry-run works; produces correct heuristic scores |
| `vault/_system/operating-manual.md` | Brain maintenance playbook, ≥120 lines | VERIFIED | 247 lines, cadence table, spec checklist, wikilinks confirmed |
| `scripts/reindex_bridge.sh` | Post-commit hook, ≥20 lines | VERIFIED | 89 lines, executable bit set, exits 0 always |
| `ultra_brain/spec_gen.py` | Brief→SPEC.md generator, ≥80 lines | VERIFIED | 307 lines; `generate_spec()` exported; all 8 required sections produced |
| `tests/unit/test_spec_gen.py` | 4 unit tests, ≥40 lines | VERIFIED | 107 lines, 4/4 tests pass |
| `ultra_brain/telos_score.py` | TELOS scoring helper | VERIFIED | 86 lines; `score_telos_relevance()` exported; imported by monitor.py |
| `tests/unit/test_telos_scoring.py` | 4 unit tests, ≥40 lines | VERIFIED | 51 lines, 4/4 tests pass |
| `ultra_brain/monitor.py` | Extended with TELOS-scored triage | VERIFIED | Lines 150-172: scores on ingestion, routes ≥0.6 → 02-Resources, <0.3 → 03-Archives/auto-culled |
| `ultra_brain/review.py` | Weekly review draft + Telegram HITL | PARTIAL | `weekly_review_draft()` and `send_weekly_review_telegram()` implemented; but CLI dispatches to old `write_weekly_review()` instead |
| `channels/telegram_adapter.py` | review_sweep callback handler | VERIFIED | Lines 389-430: `_handle_review_sweep_callback()` and dispatch hook wired |
| `agentos/workshop_registry.py` | Project-mirror on repo add | VERIFIED | `persist_registry()` + `_mirror_repo_to_vault()` confirmed; tested in isolation — creates _briefing.md, _log.md, _meta.yaml |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ultra_brain/monitor.py` | `ultra_brain/telos_score.py` | lazy import `score_telos_relevance` at line 150 | VERIFIED | Import confirmed; routing logic at lines 165-172 |
| `ultra_brain/review.py` `send_weekly_review_telegram()` | `ultra_brain/telegram.py` `send_message_with_buttons()` | import at line 175 | VERIFIED | Function call confirmed at line 178 |
| `channels/telegram_adapter.py` | `ultra_brain/review.py` `apply_pending_sweep()` / `cancel_pending_sweep()` | `_handle_review_sweep_callback()` lines 389-430 | VERIFIED | Callback dispatch wired |
| `agentos/workshop_registry.py` `persist_registry()` | `_mirror_repo_to_vault()` | diff-detection + call at line 108 | VERIFIED | Isolation test confirms 3-file creation |
| `ultra_brain/__main__.py` `review` subcommand | `weekly_review_draft()` + Telegram HITL | should dispatch to `send_weekly_review_telegram()` | BROKEN | Line 150 dispatches to `write_weekly_review()` (old function); new Telegram HITL path unreachable via CLI |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `ultra_brain/monitor.py` triage | `item_score` | `score_telos_relevance(title, url)` | Yes — heuristic keyword scoring against actual title/URL | FLOWING |
| `ultra_brain/review.py` draft | inbox items, stale projects | vault Inbox/ scan + 00-Projects/ mtime | Yes — reads real vault directories | FLOWING |
| `ultra_brain/spec_gen.py` | briefing fields | caller-supplied dict from vault briefing file | Yes — pure template from real input | FLOWING |
| `agentos/workshop_registry.py` mirror | entry dict | `persist_registry()` JSON payload from API | Yes — real repo metadata | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 8 spec_gen tests pass | `/usr/local/bin/python3 -m pytest tests/unit/test_spec_gen.py tests/unit/test_telos_scoring.py -v` | 8/8 passed in 0.01s | PASS |
| generate_spec produces all 8 required headers | `python3 -c "from ultra_brain.spec_gen import generate_spec; ..."` | All 8 section headers present | PASS |
| workshop_registry _mirror_repo_to_vault creates 3 files | `python3 -c "from agentos.workshop_registry import _mirror_repo_to_vault; ..."` with tmpdir | _briefing.md, _log.md, _meta.yaml created | PASS |
| reindex_bridge.sh is executable and exits 0 | `ls -la scripts/reindex_bridge.sh` | -rwxr-xr-x | PASS |
| Inbox contains >2 items (SC2 failure) | `ls vault/Inbox/ | wc -l` | 132 items (130 non-system) | FAIL |
| Monthly TELOS recheck CLI | search all modules for monthly/telos_recheck | No matches | FAIL |

### Requirements Coverage

Phase 16 is not covered by any requirement ID in `.planning/REQUIREMENTS.md` (which scopes the v2.0 milestone only). Phase 16 represents a new v2.5 initiative beyond the requirements document scope. No orphaned requirements apply.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `ultra_brain/monitor.py:168` | `shutil.move()` used (same iCloud APFS bug that was fixed in inbox_sweep.py) | Warning | New items routed by monitor may not actually move on iCloud-backed vault; same duplicate-file bug as inbox_sweep initial version |
| `ultra_brain/__main__.py:150` | CLI 'review' dispatches to `write_weekly_review()` not `weekly_review_draft()` | Blocker | Telegram HITL weekly review path is unreachable from CLI; plan acceptance criteria require `--dry-run --vault` flags that don't exist |

No TBD/FIXME/XXX markers found in phase-modified files.

### Human Verification Required

#### 1. Weekly Review Telegram Delivery

**Test:** Trigger `send_weekly_review_telegram()` directly (bypassing broken CLI) with real vault path  
**Expected:** Telegram message arrives with brain-health summary and two inline buttons; "Apply sweep" files items; "Skip" defers  
**Why human:** Requires live Telegram bot session and real vault inbox state

#### 2. iCloud Unlink Fix Validation

**Test:** Run `scripts/inbox_sweep.py --vault ~/Documents/second-brain` again on the current state (130 items remain)  
**Expected:** Items in Inbox/ are deleted after write_bytes+unlink; no duplicates remain  
**Why human:** Requires confirming unlink behavior on iCloud APFS mount; automated grep cannot observe filesystem delete  

#### 3. Post-commit Hook End-to-End

**Test:** Install `scripts/reindex_bridge.sh` as `.git/hooks/post-commit` in a registered repo, make a commit, verify `vault/repos/<repo>/ARCHITECTURE.md` updates within 10 seconds  
**Expected:** Architecture content reflects new commit; timestamp in header updates  
**Why human:** Requires live codebase-memory-mcp session and vault write access

### Gaps Summary

Three gaps block full goal achievement:

**Gap 1 — Inbox not clean (iCloud unlink bug):** SC2 is the most visible failure. The sweep ran, archived 123 items to `03-Archives/inbox-sweep-2026-05/` and promoted 7 to `02-Resources/articles/`, but did not delete the source files from `vault/Inbox/`. The `write_bytes+unlink` fix is in `scripts/inbox_sweep.py` but did not work for the actual sweep execution. All 130 items remain in Inbox alongside their copies. Fix: re-run the sweep; diagnose whether iCloud sandbox prevents `Path.unlink()` for this specific path.

**Gap 2 — Monthly TELOS recheck not implemented:** The fourth automation loop is entirely absent. The operating-manual.md cadence table documents it, and Plan 16-04 specifies it, but no code implements it. This is not a documentation/wiring issue — the feature was never built.

**Gap 3 — Weekly review CLI not wired to Telegram HITL path:** `ultra_brain/__main__.py` dispatches the `review` subcommand to the old `write_weekly_review()` function. The new `weekly_review_draft()` + `send_weekly_review_telegram()` path exists and is correctly implemented, but is unreachable via the CLI without code change. The plan acceptance criteria required `--dry-run` and `--vault` flags which also do not exist.

Root cause for Gaps 2 and 3: Plan 16-04 had 3 tasks; the SUMMARY claims all complete, but task 1 (TELOS scoring) and task 3 (project-mirror) were well executed while task 2 (weekly review) was only partially wired and the monthly loop was never created.

---

_Verified: 2026-05-26T18:45:00-03:00_
_Verifier: Claude (gsd-verifier)_
