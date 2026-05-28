---
phase: 15
fixed_at: 2026-05-28T19:30:00-03:00
review_path: .planning/phases/15-worker-monitor-polish-final-verification/15-REVIEW.md
iteration: 1
findings_in_scope: 6
fixed: 6
skipped: 0
status: all_fixed
---

# Phase 15: Code Review Fix Report

**Fixed at:** 2026-05-28T19:30:00-03:00
**Source review:** .planning/phases/15-worker-monitor-polish-final-verification/15-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 6
- Fixed: 6
- Skipped: 0

## Fixed Issues

### CR-01: SQL injection via f-string table name interpolation

**Files modified:** `scripts/check_surfaces.py`
**Commit:** (first fix commit)
**Applied fix:** Added `import psycopg2.sql` and replaced the raw f-string `f"SELECT COUNT(*) FROM {table_name}"` (with `# noqa: S608` suppression) with `psycopg2.sql.SQL("SELECT COUNT(*) FROM {}").format(psycopg2.sql.Identifier(table_name))`. This safely quotes the identifier via the psycopg2 SQL composition API, eliminating the injection vector. The `# noqa: S608` suppressor was removed.

### CR-02: Unguarded chained indexing on LiteLLM response

**Files modified:** `ultra_brain/llm.py`
**Commit:** (second fix commit)
**Applied fix:** Extracted `data.get("choices")` into a local variable, added a guard that raises `ValueError` with the full response context when `choices` is falsy (empty list or missing key), then indexed `choices[0]` only after the guard. This produces a clear diagnostic error instead of an opaque `IndexError`/`KeyError` on partial or error responses.

### WR-01: DedupStore.add_new read-modify-write race

**Files modified:** `ultra_brain/monitor.py`
**Commit:** (third fix commit)
**Applied fix:** Added `import fcntl` at module level. In `add_new`, moved `self.path.parent.mkdir(...)` before the lock acquire (safe to run outside lock), then wrapped the entire read-load-write cycle in `fcntl.flock(lock_fh, fcntl.LOCK_EX)` using a `.lock` sidecar file. The exclusive lock is held for the duration of load + conditionally write, then released on context-manager exit. This eliminates the race where two concurrent poll workers could both read the same `seen` set and both write overlapping entries.

### WR-02: Test reads sync script via CWD-relative path

**Files modified:** `tests/unit/test_sync_vault.py`
**Commit:** (fourth fix commit)
**Applied fix:** Changed `Path("ops/sync-vault-to-vps.sh").read_text()` to `(Path(__file__).parents[2] / "ops/sync-vault-to-vps.sh").read_text()`. This computes the path relative to the test file's own location (two levels up from `tests/unit/` reaches the project root), making the test CWD-independent.

### WR-03: IndexError on malformed URLs in domain extraction

**Files modified:** `ultra_brain/brief.py`
**Commit:** (fifth fix commit)
**Applied fix:** Added `import urllib.parse` to brief.py. Replaced the `item["url"].split("/")[2]` set comprehension with `urllib.parse.urlsplit(item["url"]).netloc`, which returns an empty string (never raises) on malformed or scheme-less URLs. The filter condition additionally excludes items where `netloc` is empty, matching the original intent.

### WR-04: Missing test coverage for "*\t" bullet prefix in _telegram_summary

**Files modified:** `ultra_brain/brief.py`, `tests/unit/test_brief.py`
**Commit:** (sixth fix commit)
**Applied fix (brief.py):** Updated `_telegram_summary` to handle all three bullet variants (`"- "`, `"* "`, `"*\t"`) by using `stripped.startswith(("- ", "* ", "*\t"))` and normalizing all to `"• "` prefix. The worktree had the older version that only handled `"- "`.
**Applied fix (test_brief.py):** Added `_telegram_summary` to the import. Added a `@pytest.mark.parametrize` test `test_telegram_summary_bullet_prefixes` with three cases (`"- "`, `"* "`, `"*\t"`), each verifying the normalized `"• "` output appears in the summary.

**Test run:** `python -m pytest tests/unit/test_brief.py tests/unit/test_sync_vault.py -q` — 9 passed in 0.05s.

---

_Fixed: 2026-05-28T19:30:00-03:00_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
