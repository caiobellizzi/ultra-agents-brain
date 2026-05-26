---
phase: 16-brain-vault-overhaul
plan: "16-03"
subsystem: vault-bridge
tags: [codebase-memory-mcp, spec-gen, reindex, post-commit-hook, tdd]

requires:
  - "16-01: TELOS activated"
  - "16-02: operating-manual.md written with spec discipline section"
provides:
  - "scripts/reindex_bridge.sh: post-commit hook writing vault/repos/<repo>/ARCHITECTURE.md"
  - "ultra_brain/spec_gen.py: generate_spec() — Brief→SPEC.md pure-Python generator"
  - "tests/unit/test_spec_gen.py: 4 unit tests for spec_gen required-field coverage"
affects:
  - vault-repos
  - spec-pipeline
  - codebase-memory-mcp

tech-stack:
  added: []
  patterns:
    - "codebase-memory-mcp cli subcommand: detect_changes + get_architecture via CLI JSON"
    - "pure-python SPEC templating: string assembly from briefing dict, no LLM required"
    - "EARS acceptance criteria: When X, the system shall Y — auto-templated from goal field"

key-files:
  created:
    - "scripts/reindex_bridge.sh"
    - "ultra_brain/spec_gen.py"
    - "tests/unit/test_spec_gen.py"
  modified: []

key-decisions:
  - "codebase-memory-mcp project name is path-derived (slashes → dashes); script derives it at runtime from REPO_ROOT"
  - "vault path discovery: checks $VAULT_PATH env var first, falls back to ~/Documents/second-brain; checks for /vault/ subdirectory vs flat layout"
  - "spec_gen is pure Python string templating in Phase 16; PgVector/LLM enhancement deferred to future phase"
  - "TDD RED/GREEN gate respected: test commit d314cca precedes implementation commit 9c5afc7"

requirements-completed: []

duration: 25min
completed: 2026-05-26
---

# Phase 16 Plan 03: Graph Bridge + Spec Generator Summary

**Post-commit hook writes vault ARCHITECTURE.md via codebase-memory-mcp; Brief→SPEC.md generator implemented TDD with 4 passing tests covering all 8 required spec sections.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-26T13:43:00Z
- **Completed:** 2026-05-26T14:10:00Z
- **Tasks:** 2 (Task 1: reindex_bridge.sh, Task 2: spec_gen.py via TDD)
- **Files created:** 3

## Accomplishments

### Task 1: scripts/reindex_bridge.sh

Created an 89-line bash post-commit hook that:

1. Resolves repo root via `git rev-parse --show-toplevel`
2. Derives project slug (basename, lowercased, kebab-cased)
3. Derives codebase-memory-mcp project name (path, slashes → dashes)
4. Calls `detect_changes` to flag dirty files; falls back to `index_repository` on miss
5. Calls `get_architecture` and writes JSON to `/tmp/uab-arch-summary-<slug>.txt`
6. Creates `vault/repos/<slug>/` (or `repos/<slug>/` if vault is flat-rooted)
7. Writes `ARCHITECTURE.md` with `# Architecture — <slug>`, ISO timestamp, and content
8. Exits 0 always — never blocks commits

Verified: running from the main repo root produced `/Users/caiobellizzi/Documents/second-brain/repos/ultra-agents-brain/ARCHITECTURE.md` with valid architecture JSON content.

### Task 2: ultra_brain/spec_gen.py (TDD — RED then GREEN)

**RED commit (d314cca):** 4 failing tests asserted on non-existent `generate_spec()`.

**GREEN commit (9c5afc7):** Implemented `generate_spec(briefing, architecture_md, repo_path)` producing:

| Section | Source |
|---------|--------|
| `Problem & Context` | briefing body + concept wikilinks |
| `In-Scope` | placeholder for human completion |
| `Out-of-Scope` | placeholder for human completion |
| `Interfaces` | placeholder typed Python signature |
| `Acceptance Criteria` | EARS format from `goal` field + 3 placeholders |
| `References` | `source_notes` wikilinks + repo file path |
| `Rails` | Always/Ask-First/Never table placeholders |
| `Code Style Example` | first code block from ARCHITECTURE.md or placeholder |

All 4 tests pass:

```
tests/unit/test_spec_gen.py::test_spec_gen_produces_all_required_fields PASSED
tests/unit/test_spec_gen.py::test_spec_gen_embeds_architecture_snippet PASSED
tests/unit/test_spec_gen.py::test_spec_gen_ears_format PASSED
tests/unit/test_spec_gen.py::test_spec_gen_references_source_wikilinks PASSED
4 passed in 0.01s
```

CLI tested — all 8 required section headers present in output.

## TDD Gate Compliance

- RED gate: `test(16-03)` commit `d314cca` — tests fail with `ModuleNotFoundError` (correct RED state)
- GREEN gate: `feat(16-03)` commit `9c5afc7` — 4/4 tests pass

## Task Commits

1. **Task 1: reindex_bridge.sh** — `57d131e` (feat(16-03))
2. **Task 2 RED: failing tests** — `d314cca` (test(16-03))
3. **Task 2 GREEN: spec_gen.py** — `9c5afc7` (feat(16-03))

## Deviations from Plan

### Auto-noted Issues

**1. [Rule 1 - Pre-existing] `python3 -m ultra_brain spec-gen` CLI blocked by llm.py import**
- **Found during:** Task 2 CLI verification
- **Issue:** `ultra_brain/__main__.py` imports `brief.py` which imports `from . import llm` — but `llm.py` is untracked (not in worktree). This is the same pre-existing issue noted in 16-01 SUMMARY.
- **Fix:** CLI tested directly via `_cli()` function call — all 8 sections verified present. The llm.py issue is pre-existing and out of scope for this plan.
- **Impact:** None — all acceptance criteria met via direct function call and pytest.

**2. [Rule 2 - Enhancement] vault path detection: flat layout vs /vault/ subdirectory**
- **Found during:** Task 1 testing
- **Issue:** The vault root at `~/Documents/second-brain` has no `vault/` subdirectory — `repos/` lives directly under the root. Plan assumed `vault/repos/<slug>/`.
- **Fix:** Script checks for `$VAULT_PATH/vault/` existence; falls back to `$VAULT_PATH/repos/` when not found. Both layouts supported.
- **Files modified:** `scripts/reindex_bridge.sh`

## Known Stubs

`spec_gen.py` In-Scope, Out-of-Scope, Interfaces, and Rails sections are intentional human-completion placeholders — this is by design. The spec generator produces a structured template; a human (or future LLM enhancement) fills the placeholder content. This does not block the plan's goal.

## Self-Check

### Files exist

- [x] `scripts/reindex_bridge.sh` — `57d131e`
- [x] `ultra_brain/spec_gen.py` — `9c5afc7`
- [x] `tests/unit/test_spec_gen.py` — `d314cca`

### Commits exist

- [x] `57d131e` — feat(16-03): add reindex_bridge.sh
- [x] `d314cca` — test(16-03): add failing tests (RED)
- [x] `9c5afc7` — feat(16-03): implement spec_gen.py (GREEN)

### Acceptance criteria

- [x] `scripts/reindex_bridge.sh` exists and is executable
- [x] Script exits 0 always (tested both missing-tool and live-tool paths)
- [x] `vault/repos/ultra-agents-brain/ARCHITECTURE.md` written when tool available
- [x] Graceful fallback when codebase-memory-mcp project not indexed
- [x] `tests/unit/test_spec_gen.py` has 4 tests; all pass GREEN
- [x] `generate_spec()` exported from `ultra_brain/spec_gen.py`
- [x] CLI produces SPEC.md with all 8 required section headers
- [x] No new package dependencies added to `requirements.txt`

## Self-Check: PASSED
