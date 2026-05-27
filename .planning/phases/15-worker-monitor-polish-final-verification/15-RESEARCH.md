# Phase 15 Research: worker.monitor Polish + Final Verification

**Date:** 2026-05-27
**Requirements:** MON-01, MON-02, OBS-02

---

## ## RESEARCH COMPLETE

---

## 1. MON-01 — Daily-brief date-mismatch bug

### Root cause (confirmed in code)

`brief.py:_read_inbox_items` globs the Inbox directory with a strict date prefix:

```python
for path in sorted(inbox_dir.glob(f"{day.isoformat()}-*.md")):
```

`monitor.py:run_poll` files items using `today = date.today().isoformat()` at the time it runs.

**Race condition:** monitor runs at 23:55 on day X → files items as `2026-05-27-*.md`. Brief runs at 06:00 on day X+1 → `date.today()` returns `2026-05-28` → glob finds zero files → no items in brief. Every item monitor filed the previous evening is silently dropped.

### Additional complication

Items scored `>= 0.6` by `telos_relevance` are moved from `Inbox/` to `02-Resources/articles/` by `run_poll`. Items scored `< 0.3` go to `03-Archives/auto-culled/`. The brief only reads `Inbox/` — so it also misses high-relevance items that were routed to articles. Whether this is intentional is unclear from the code; MON-01 only covers the date-mismatch case.

### Existing change in `brief.py` (git diff)

The uncommitted diff in `brief.py` fixes the Telegram bullet formatting only — it does **not** address the date-mismatch bug. MON-01 is still open.

### Fix approach

Change `_read_inbox_items` to look back N days instead of strictly today:

```python
from datetime import date, timedelta

def _read_inbox_items(vault_root: Path, *, day: date, lookback_days: int = 2) -> list[dict]:
    inbox_dir = vault_root / "Inbox"
    if not inbox_dir.exists():
        return []
    items = []
    for offset in range(lookback_days):
        check_day = day - timedelta(days=offset)
        for path in sorted(inbox_dir.glob(f"{check_day.isoformat()}-*.md")):
            # parse title, url, published (existing logic)
            ...
    return items
```

The existing `_filter_unseen` dedup store (`brief-seen.json`) already handles "don't include the same URL twice" — so extending the lookback window is safe. Items already included in a prior brief are silently skipped.

### Regression test

File: `tests/unit/test_brief.py` (new)

Pattern: create a temp vault, write a stub Inbox file dated yesterday, call `_read_inbox_items(day=today)`, assert the item is found.

Reference patterns: `tests/test_core.py` uses `tempfile.TemporaryDirectory()` + `ensure_vault(vault)`.

---

## 2. MON-02 — Vault sync `--delete` wipes VPS-generated inbox items

### Current script state

`ops/sync-vault-to-vps.sh` already implements a 2-pass strategy (confirmed in code):

```bash
# Pass 1: VPS → Mac (pull, --update only, no --delete)
rsync -av --update "${EXCLUDES[@]}" "$REMOTE" "$LOCAL"

# Pass 2: Mac → VPS (push, --update --delete)
rsync -av --update --delete "${EXCLUDES[@]}" "$LOCAL" "$REMOTE"
```

**The logic is correct.** VPS-generated Inbox items land on Mac in pass 1, so they exist locally before pass 2's `--delete` runs — they are not deleted.

### What MON-02 actually requires

The requirement is a **regression test** that proves the 2-pass strategy works as specified. No code bug to fix — the fix is already in place. The test is the deliverable.

### Test approach

Since rsync can't be safely mocked end-to-end in CI, the test should verify the shell script's logical structure (not execute rsync):

```python
# tests/unit/test_sync_vault.py
def test_pull_before_push_delete():
    script = Path("ops/sync-vault-to-vps.sh").read_text()
    lines = [l.strip() for l in script.splitlines() if "rsync" in l]
    assert len(lines) >= 2
    pull_idx = next(i for i, l in enumerate(lines) if "--delete" not in l)
    push_idx = next(i for i, l in enumerate(lines) if "--delete" in l)
    assert pull_idx < push_idx, "pull (no --delete) must precede push (--delete)"
```

Alternatively, a functional test using `tmp_path` dirs:
1. Create `local/` and `remote/` temp dirs
2. Write a file only to `remote/Inbox/` (simulates VPS-generated item)
3. Run the 2-pass sync logic manually using `subprocess.run(["rsync", ...])` against local dirs
4. Assert the file exists in `local/Inbox/` and `remote/Inbox/` after sync

The functional approach is more valuable as a real regression test.

---

## 3. OBS-02 — check-surfaces

### Four surfaces and their storage backends

| Surface | Local backend | VPS backend |
|---------|--------------|-------------|
| memory | SQLite (`agno.db`) via Agno `AgentMemory` | PostgreSQL via `PostgresDb(id="ultra-brain-main")` |
| evals | SQLite (eval recorder writes to agno.db) | PostgreSQL |
| knowledge | SQLite fallback / pgvector `vault` table | pgvector `vault` table |
| approvals | SQLite (Agno HITL queue) | PostgreSQL |

Agno's `AgentOS` exposes these as `/v1/memory`, `/v1/evals`, `/v1/knowledge`, `/v1/approvals` routes, backed by the shared `db` object in `agentos/db.py`.

### Implementation approach

A Python script `scripts/check_surfaces.py` (or inline in `Makefile`) that:
1. Reads `POSTGRES_DSN_SESSIONS` env var — if set, uses PostgreSQL; otherwise falls back to SQLite
2. Queries row counts for each surface's backing table
3. Prints counts and exits non-zero if any count is 0

**PostgreSQL table names** (from Agno's `PostgresDb` schema with `id="ultra-brain-main"`):
- memory: `ultra_brain_main_memory`
- sessions: `ultra_brain_main_sessions`
- runs: `ultra_brain_main_runs`
- knowledge: `vault` (from `knowledge.py:126` — `table_name="vault"`)
- approvals: `ultra_brain_main_run_approval_requests`

Verify exact names by running `\dt` against the VPS Postgres instance, or use Agno's schema introspection.

**Minimal script pattern:**

```python
#!/usr/bin/env python3
"""Smoke-check that all 4 AgentOS surfaces have non-zero row counts."""
import os, sys, psycopg2  # or sqlite3 fallback

DSN = os.getenv("POSTGRES_DSN_SESSIONS")
if not DSN:
    print("POSTGRES_DSN_SESSIONS not set — using SQLite (local mode)")
    # query agno.db for session/memory tables

surfaces = {
    "memory":    "SELECT COUNT(*) FROM ultra_brain_main_memory",
    "evals":     "SELECT COUNT(*) FROM ultra_brain_main_runs WHERE is_eval = true",
    "knowledge": "SELECT COUNT(*) FROM vault",
    "approvals": "SELECT COUNT(*) FROM ultra_brain_main_run_approval_requests",
}
failed = []
with psycopg2.connect(DSN) as conn:
    for name, sql in surfaces.items():
        count = conn.cursor().execute(sql).fetchone()[0]
        status = "✓" if count > 0 else "✗ EMPTY"
        print(f"  {status}  {name}: {count} rows")
        if count == 0:
            failed.append(name)
sys.exit(1 if failed else 0)
```

### Makefile target

```makefile
check-surfaces:
    PYTHONPATH=. .venv/bin/python scripts/check_surfaces.py
```

### On local dev (no Postgres)

The script should degrade gracefully: detect no `POSTGRES_DSN_SESSIONS`, fall back to checking SQLite `agno.db` for the memory/sessions tables (always exist), print a note that knowledge + approvals can't be checked without Postgres.

---

## 4. RETROSPECTIVE.md

New file at repo root. Content outline per v2.0 success criteria:
- Timeline (phases 10–18, dates)
- What shipped vs original scope
- Key decisions: SQLite → Postgres, pgvector for knowledge, Agno AgentOS surface
- Known gaps not closed: streaming eval recording, model_id null in live traffic
- Surprises: Phase 18 auto-sync prerequisite, iCloud APFS move_to_trash fix
- Lessons: discuss-phase before each phase pays off; Nyquist validation found real gaps

---

## 5. Validation Architecture

Key test gaps for Nyquist compliance:

| Requirement | Test needed |
|-------------|-------------|
| MON-01 | `tests/unit/test_brief.py::test_date_lookback_catches_yesterday_items` |
| MON-01 | `tests/unit/test_brief.py::test_no_duplicates_across_days` (dedup still works with lookback) |
| MON-02 | `tests/unit/test_sync_vault.py::test_pull_before_push_delete` (script structure) |
| MON-02 | `tests/unit/test_sync_vault.py::test_vps_generated_items_survive_delete_sync` (functional) |
| OBS-02 | Manual/smoke only — no pytest needed for check-surfaces itself; CI just needs the script to exit 0 on VPS |

---

## 6. File map

| File | Action |
|------|--------|
| `ultra_brain/brief.py` | Fix `_read_inbox_items` — add `lookback_days=2` param |
| `tests/unit/test_brief.py` | New — regression tests for MON-01 |
| `ops/sync-vault-to-vps.sh` | No code change needed |
| `tests/unit/test_sync_vault.py` | New — regression tests for MON-02 |
| `scripts/check_surfaces.py` | New — OBS-02 smoke checker |
| `Makefile` | Add `check-surfaces` target |
| `RETROSPECTIVE.md` | New — v2.0 retrospective |
