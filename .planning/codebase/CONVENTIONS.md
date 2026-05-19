# Coding Conventions

**Analysis Date:** 2026-05-19

## Naming Patterns

**Files:**
- Module names use `snake_case` with a single domain noun: `cost.py`, `trust.py`, `vault.py`, `ingest.py`
- CLI wrappers in `skills/common/` are named by function: `cost_ledger.py`, `trust_policy.py`
- Script files use `kebab-case`: `health-check.sh`, `lint-check.sh`, `git-sync.sh`

**Classes:**
- PascalCase for all classes: `CostLedger`, `CostEntry`, `CostGate`, `Extractor`, `Filer`, `DedupStore`, `RipgrepRetriever`, `QmdClient`, `TelosSessionStore`
- Frozen dataclasses used for value objects / result types: `ExtractionResult`, `IngestResult`, `SearchHit`, `LintFinding`, `ReviewItem`, `TrustDecision`, `TelosCheck`, `ResearchSubtask`

**Functions:**
- `snake_case` for all functions and methods
- Private helpers prefixed with single underscore: `_extract_url`, `_choose_tier`, `_target_dir`, `_yaml_scalar`, `_terms`, `_words`, `_age_days`, `_fetch_url`
- Public module-level entry functions follow the pattern `verb_noun` or `noun_verb`: `ensure_vault`, `query_vault`, `run_lint`, `write_lint_report`, `plan_research`, `aggregate_research`, `score_alignment`, `classify_action`
- Write functions follow `write_X` naming: `write_lint_report`, `write_weekly_review`
- Run functions follow `run_X` naming: `run_lint`, `run_poll`, `run_llm_lint`

**Variables:**
- `snake_case` throughout
- Module-level constants use `UPPER_SNAKE_CASE`: `DEFAULT_LIMITS`, `HIGH_RISK_RE`, `MEDIUM_RISK_RE`, `VAULT_DIRS`, `SYSTEM_FILES`, `PRIVATE_BLOCK_RE`, `WIKILINK_RE`, `DEFAULT_QUESTIONS`, `URL_RE`
- Risk level constants: single-word uppercase strings `LOW = "low"`, `MEDIUM = "medium"`, `HIGH = "high"` (`trust.py`)

**Types:**
- PascalCase for dataclasses and classes; no `TypeAlias` or `NewType` in use
- `frozen=True` on every dataclass used as a return value or result object

## Code Style

**Formatting:**
- No formatter config file detected (no `pyproject.toml`, `.ruff.toml`, `.flake8`, `.prettierrc`)
- `.gitignore` includes `.ruff_cache/` and `.mypy_cache/`, indicating ruff and mypy are used locally but not enforced via config files committed to the repo
- One `# noqa: S310` comment and one `# noqa: E402` in skill wrappers — suppressed sparingly

**Line length:**
- No explicit limit configured; lines stay under ~120 chars in practice

**Quotes:**
- Double quotes for all strings

**Trailing commas:**
- Used consistently in multi-line data structures (function signatures, dict/list literals)

## Import Organization

**Order (strictly followed in every module):**
1. `from __future__ import annotations` — first line of every module without exception
2. Standard library imports (alphabetical within group): `hashlib`, `json`, `os`, `pathlib`, `re`, `urllib.*`, etc.
3. Intra-package relative imports: `from . import llm`, `from .cost import CostLedger`, `from .markdown import ...`

**No third-party dependencies in `ultra_brain/`** — entire package uses only stdlib (`urllib.request`, `xml.etree.ElementTree`, `subprocess`, `json`, `hashlib`, `re`, `pathlib`, `dataclasses`).

**Deferred imports inside functions** (used to avoid circular imports):
- `monitor.py`: `from .telos import score_alignment` deferred inside `score_items()` and `run_poll()`

**Skill wrappers (`skills/common/`):**
- Manipulate `sys.path` to add project root before relative imports from `ultra_brain`
- Use `# noqa: E402` on the import that follows the path manipulation

## Error Handling

**Core principle:** LLM calls and network I/O are wrapped in `try/except Exception: pass` with a graceful fallback. This is intentional — the system must degrade gracefully when the LLM gateway is unavailable.

**Pattern 1 — LLM fallback (all modules that call `llm.complete`):**
```python
try:
    response = llm.complete(...)
    # use response
except Exception:
    pass  # fall through to heuristic
```
Used in: `ingest.py` (`_choose_tier`), `telos.py` (`score_alignment`), `query.py` (`synthesize_answer`), `express.py` (`daily_digest`), `research.py` (`worker_summary`)

**Pattern 2 — Specific network exceptions (URL extraction):**
```python
try:
    return self._extract_crawl4ai(url)
except (OSError, ValueError, urllib.error.URLError):
    pass
```
Used in: `ingest.py` (`_extract_url`)

**Pattern 3 — Tolerated per-item errors (batch loops):**
```python
for url in feed_urls:
    try:
        all_items.extend(fetch_feed(url))
    except Exception as exc:
        print(f"monitor: failed to fetch {url}: {exc}", file=sys.stderr)
```
Used in: `monitor.py` (`run_poll`), `lint.py` (`run_llm_lint`)

**Pattern 4 — Explicit raises for programmer errors:**
```python
raise ValueError("invalid session store")
raise KeyError(f"session {session_id} not found")
```
Used in: `telos.py` (`TelosSessionStore.answer`)

**Pattern 5 — Silent skip with `continue`** used in `cost.py` entries parsing and `lint.py` LLM pass when individual files fail.

**Never propagated:** External service failures (LiteLLM, Crawl4AI, Jina) never bubble up to callers. The caller receives a degraded but valid result.

## Logging

**No structured logging library.** The project uses a flat Markdown append-log:
```python
append_log(log_path, "brain.ingest", "filed {title}", {"path": rel_path, "method": method})
```
`append_log` is defined in `ultra_brain/markdown.py` and writes `## [ISO timestamp] operation | description` blocks to `vault/_system/log.md`.

**stderr for operational errors** (not log file):
```python
print(f"monitor: failed to fetch {url}: {exc}", file=sys.stderr)
```

## Comments

**Module docstrings:** Every module has a one-line (or short multi-line) docstring at line 1 describing its purpose. This is the only mandatory documentation.

**Function-level docstrings:** Only complex functions document via docstring. Most functions rely on clear naming + type annotations instead. Exceptions: `score_items`, `run_poll` (both have full docstrings with param descriptions).

**Inline comments:** Rare, used only to explain non-obvious decisions:
- `# noqa: S310` — suppressing urllib security warning intentionally
- `# fall through to heuristic` — explaining the `except Exception: pass` pattern
- `# Heuristic fallback` — marking the non-LLM branch

## Function Design

**Size:** Functions are small; the largest (`Filer.file`) is ~50 lines. Complexity is split between the `Extractor` and `Filer` classes.

**Parameters:**
- Keyword-only parameters enforced with `*` for optional config: `def run_poll(feeds_yaml, vault_root, *, dedup_path=None, score=False, telos_root=None)`
- LLM model injection is always keyword-only: `*, llm_model: str | None = None`
- `Path` is the standard type for filesystem arguments, never raw `str`

**Return Values:**
- Functions that write files return the `Path` of what they wrote: `write_lint_report -> Path`, `write_weekly_review -> Path`, `aggregate_research -> Path`
- Functions that could fail return a result object, never raise: `CostLedger.record -> CostGate`, `classify_action -> TrustDecision`
- Query/synthesis functions return `str` for direct display

**Type annotations:** Full annotations on all public function signatures; private helpers (`_words`, `_terms`, `_age_days`) are also annotated. Return type `None` is explicit.

## Module Design

**Exports:**
- `ultra_brain/__init__.py` exports only `__version__`; all functionality is imported directly from submodules
- No barrel re-exports for domain modules

**Class vs. module-level functions:**
- Stateful objects (`CostLedger`, `Extractor`, `Filer`, `DedupStore`, `TelosSessionStore`) are classes
- Stateless operations are module-level functions (`ensure_vault`, `slugify`, `canonicalize_url`, `classify_action`, `score_alignment`)
- Classes that hold only config (no mutable state) pass config via `__init__` and expose operations as methods

**Frozen dataclasses as value objects:** Every domain result or decision type is a `@dataclass(frozen=True)`. This prevents mutation after construction and makes return values easy to inspect in tests.

**Skill wrappers (`skills/`):**
- Each skill in `skills/<name>/` has an implementation `.py` file and a `SKILL.md` spec
- The `skills/common/` directory holds thin CLI wrappers that delegate into `ultra_brain.*`
- Skill files add the project root to `sys.path` and invoke `ultra_brain` modules directly; they are standalone scripts, not packages

## Shell Scripting Conventions (`scripts/`)

**All scripts use:**
```bash
#!/usr/bin/env bash
set -euo pipefail
```

**Environment variables:**
- All configurable values read from env with fallbacks: `VAULT_DIR="${VAULT_VPS_PATH:-/srv/second-brain}"`
- Required vars validated with a `require_env()` helper function (in `lint-check.sh`)

**Telegram notifications:** Extracted to a shared `telegram_send()` function in each script (copy-pasted, not shared). The function silences errors with `|| true` to avoid blocking the script.

**Path handling:** `SCRIPT_DIR` computed via `$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)` in scripts that need relative paths.

**Exit codes:** `exit 1` on failure; `exit 0` implicit on success. `exit 2` for usage errors.

---

*Convention analysis: 2026-05-19*
