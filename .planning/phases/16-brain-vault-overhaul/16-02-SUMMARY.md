---
phase: 16-brain-vault-overhaul
plan: "16-02"
subsystem: vault
tags: [inbox-sweep, telos-scoring, operating-manual, vault, brain]

requires:
  - "16-01: TELOS activated — all four sub-docs filled"
provides:
  - "scripts/inbox_sweep.py: one-shot TELOS-scored inbox sweep utility"
  - "vault/_system/operating-manual.md: Brain maintenance playbook (247 lines)"
  - "130 Inbox items processed: 7 promoted to 02-Resources/articles/, 123 archived"
  - "telos_relevance scored and written to frontmatter of all processed items"
affects:
  - vault-inbox
  - telos-scoring
  - spec-discipline

tech-stack:
  added: []
  patterns:
    - "heuristic-keyword telos scoring: no LLM required, keyword lists for high/medium/negative priors"
    - "write-then-unlink file move: explicit Path.unlink() after write_bytes() for iCloud vault compatibility"
    - "vault-as-separate-git-repo: vault changes committed to second-brain git, not main project git"

key-files:
  created:
    - "scripts/inbox_sweep.py"
    - "vault/_system/operating-manual.md"
  modified:
    - "vault/_system/log.md"
    - "vault/02-Resources/articles/* (7 new promoted articles)"
    - "vault/03-Archives/inbox-sweep-2026-05/* (123 archived items)"

key-decisions:
  - "heuristic scoring over LLM call: no LLM needed for batch inbox scoring; keyword/prior lists are sufficient and deterministic"
  - "write_bytes+unlink instead of shutil.move: macOS iCloud APFS vault silently keeps source file on shutil.move; explicit write+unlink is reliable"
  - "vault is a separate git repo: vault/_system/ files committed to second-brain@main, not to main project repo"
  - "7 out of 130 promoted: threshold 0.6 correctly filtered AI/agent content from news/esoterica flood"

patterns-established:
  - "inbox_sweep.py pattern: dry-run first, then execute; always print item-by-item plan before moving"
  - "operating-manual structure: Purpose+TELOS → Pipeline → Distillation → Navigation → Cadence → Bridge → Decisions → Spec Discipline → Hygiene → Deferred"

requirements-completed: []

duration: 9min
completed: 2026-05-26
---

# Phase 16 Plan 02: Inbox Sweep + Operating Manual Summary

**TELOS-scored inbox sweep cleared 130 items from vault (7 promoted, 123 archived); Brain Operating Manual written as 247-line runbook with cadence table and spec checklist.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-05-26T13:53:08Z
- **Completed:** 2026-05-26T14:02:15Z
- **Tasks:** 2
- **Files modified:** 2 (main repo) + 132 (vault)

## Accomplishments

### Task 1: scripts/inbox_sweep.py

Created a standalone 260-line Python script for one-shot TELOS-scored inbox sweeps.

Key design choices:
- Keyword-based telos_relevance scoring (no LLM) using three tiered lists: high-relevance AI/agent keywords (+0.3 per hit up to 0.9), medium-relevance engineering keywords (+0.1 per hit), negative prior keywords (-0.4 per match)
- `--dry-run` mode prints item-by-item plan before any file operations
- Frontmatter extraction reads `title:` field from YAML frontmatter first, then falls back to first `# heading`, then filename stem
- File move uses `write_bytes() + unlink()` instead of `shutil.move()` — required for macOS iCloud APFS vaults where shutil.move silently keeps the source file

Run results (executed without --dry-run):
- 130 items scanned
- 7 promoted to `02-Resources/articles/` (telos_relevance 0.60–1.00)
- 123 archived to `03-Archives/inbox-sweep-2026-05/`
- Inbox contains only MOC.md + README.md
- Log entry appended to `_system/log.md`

Promoted items included: DeepSeek Reasonix coding agent, Kanban app with parallel agents, Constraint Decay for LLM agents, paperclip agent management app, Virgin Atlantic with Codex, Microsoft AI cost report, DeepSeek price discount.

### Task 2: vault/_system/operating-manual.md

Written as a 247-line (11-section) runbook — human and agent readable — covering:

1. Purpose and TELOS (telos_relevance gate, quarter-goals alignment)
2. Ingestion pipeline (ingest-everything-filter-later, negative priors)
3. Distillation ladder (layers 0–3, ~10–20% per layer, non-destructive)
4. Navigation (MOC.md maintenance, Statements vs Things)
5. Operating cadence (4-loop table: daily/weekly/monthly/project-mirror)
6. Brain↔code bridge (workshop registry → project mirror → ARCHITECTURE.md → SPEC.md)
7. Decision memory (ADR discipline, one PR = one code change + one knowledge update)
8. Spec discipline (7-field checklist with EARS acceptance criteria format)
9. Hygiene rules (CLAUDE.md <200 lines, monthly prune, weekly vault-health check)
10. Deferred v2.1 (email/calendar, LinkedIn)

Cadence table (section 5):

| Loop | Trigger | Autonomous | HITL gate |
|------|---------|------------|-----------|
| Daily auto-triage | Cron/worker | Score+file ≥0.6 | None |
| Weekly review | Sunday cron | Draft review doc | Telegram approve |
| Monthly TELOS recheck | Monthly cron | Score projects vs goals | Flag drift |
| Project-mirror sync | New repo in registry | Create structure | None |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] macOS iCloud vault: shutil.move leaves source file intact**
- **Found during:** Task 1 execution
- **Issue:** `shutil.move()` on an iCloud-synced APFS vault silently copies to destination but does not delete the source file, leaving duplicates in both Inbox and destination
- **Fix:** Replaced `shutil.move(str(item), str(dest))` with `dest.write_bytes(item.read_bytes()); item.unlink()` — explicit write + delete, which works correctly on iCloud
- **Files modified:** `scripts/inbox_sweep.py`
- **Commit:** a4766ae (fix was included in final committed version)

**2. [Rule 1 - Bug] frontmatter title extraction: first_heading returned field prefix**
- **Found during:** Task 1 dry-run scoring
- **Issue:** Files without a markdown `# heading` (only YAML frontmatter with `title:`) had their title extracted as "or:" (from "author:") because the loop searched all lines including frontmatter lines
- **Fix:** Added explicit YAML frontmatter `title:` extraction before fallback to markdown heading
- **Files modified:** `scripts/inbox_sweep.py` (`_extract_text` function)

## Self-Check

### Created files exist

- [x] `scripts/inbox_sweep.py` — committed at a4766ae
- [x] `vault/_system/operating-manual.md` — committed at vault@5a2b026

### Commits exist

- [x] a4766ae: feat(16-02): add inbox_sweep.py (main repo)
- [x] 85cb8b9: vault auto-sync (vault repo — 7 promoted + 123 archived + log entry)
- [x] 5a2b026: feat(16-02): add Brain Operating Manual (vault repo)

### Count invariant

- [x] 7 promoted + 123 archived = 130 total scanned ✓
- [x] vault/Inbox/ contains only MOC.md and README.md ✓
- [x] vault/_system/log.md has batch log entry ✓
- [x] operating-manual.md: 247 lines (≥120) ✓
- [x] cadence table present (4 loops) ✓
- [x] spec checklist present (7 checkboxes) ✓
- [x] [[telos]], [[quarter-goals]], [[dont-do]] wikilinks present ✓

## Self-Check: PASSED
