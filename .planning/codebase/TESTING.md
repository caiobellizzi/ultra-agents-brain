# Testing Patterns

**Analysis Date:** 2026-05-19

## Test Framework

**Runner:**
- `unittest` (stdlib) — `unittest.TestCase` base class used exclusively
- `pytest` is the test runner (`.pytest_cache/` present in repo)
- Config: no `pytest.ini` or `pyproject.toml`; pytest runs with defaults

**Assertion Library:**
- `unittest.TestCase` assertion methods (`assertTrue`, `assertFalse`, `assertIn`, `assertEqual`, `assertGreater`)
- No third-party assertion libraries (`assertpy`, `hamcrest`, etc.)

**Run Commands:**
```bash
python -m pytest tests/          # Run all tests
python -m pytest tests/ -v       # Verbose output
python -m pytest tests/test_core.py::CoreTest::test_cost_gate_warns_and_refuses_at_limits  # Single test
python -m unittest tests/test_core.py  # Run via unittest runner (also works)
```

## Test File Organization

**Location:** Tests live in a flat `tests/` directory at project root.

**Naming:**
- Test file: `tests/test_core.py`
- Test class: `CoreTest(unittest.TestCase)`
- Test methods: `test_<feature>_<behavior>` — descriptive, full sentence style

**Structure:**
```
tests/
└── test_core.py    # Single file, one class, 8 integration tests
```

There are no unit tests, no test subdirectories, and no test fixtures or factory modules.

## Test Structure

**Single test class covers all modules:**
```python
class CoreTest(unittest.TestCase):
    def test_ingest_files_markdown_logs_cost_and_query_finds_it(self) -> None: ...
    def test_cost_gate_warns_and_refuses_at_limits(self) -> None: ...
    def test_trust_strips_private_and_blocks_high_risk(self) -> None: ...
    def test_research_aggregation_creates_project_outputs(self) -> None: ...
    def test_lint_report_detects_private_blocks_and_missing_source(self) -> None: ...
    def test_telos_session_and_alignment(self) -> None: ...
    def test_monitor_dedup_and_rss_parse(self) -> None: ...
    def test_weekly_review_writes_report(self) -> None: ...
```

**Test method naming pattern:** `test_<module>_<what_it_does>` or `test_<scenario>_<expected_outcome>`. Names are intentionally verbose — they read as mini-specs:
- `test_ingest_files_markdown_logs_cost_and_query_finds_it`
- `test_cost_gate_warns_and_refuses_at_limits`
- `test_trust_strips_private_and_blocks_high_risk`

**No setUp / tearDown.** Each test is fully self-contained.

## Mocking

**Framework:** None. Zero mocking in the test suite.

**Strategy:** Tests exercise real implementations end-to-end within temporary directories. The entire stack (vault creation, file I/O, data parsing, cost accounting, dedup stores) runs without mocks.

**LLM calls are avoided:** Tests pass `prefer_qmd=False` and do not supply `llm_model`, so the `llm.complete` path is never invoked. The heuristic/fallback paths are what get tested. Example:
```python
answer = query_vault("prompt caching cost", vault, prefer_qmd=False)
# Uses RipgrepRetriever fallback, not LLM synthesis
```

**What to mock:** Only mock `llm.complete` if writing tests that specifically validate LLM-driven branching. Currently none exist.

**What NOT to mock:** Filesystem operations — `tempfile.TemporaryDirectory` is used instead to give each test an isolated real filesystem.

## Fixtures and Factories

**Test Data:**
```python
# Every test that touches vault creates a fresh temp dir
with tempfile.TemporaryDirectory() as tmp:
    vault = Path(tmp) / "vault"
    ensure_vault(vault)
    ...
```

**No factory functions** — test data is created inline within each test method.

**Inline fixture content:**
```python
# RSS XML constructed inline as a string literal
xml = """<?xml version="1.0"?><rss><channel><item>...</item></channel></rss>"""

# Vault notes written directly
note.write_text("---\ntype: article\ntitle: Bad\n---\n\n<private>hide</private>\n", encoding="utf-8")

# Telos mission written directly
(system / "telos" / "mission.md").write_text("Async research for AI tooling.", encoding="utf-8")
```

**Location:** No `tests/fixtures/`, `tests/factories/`, or `conftest.py`. All fixture data is inline.

## Coverage

**Requirements:** None enforced. No `.coveragerc`, no `--cov` in any script or config.

**Covered modules (via `tests/test_core.py` imports):**
- `ultra_brain.cost` — `CostLedger` (gate, record, limits)
- `ultra_brain.ingest` — `Extractor`, `Filer` (text extraction, vault filing)
- `ultra_brain.lint` — `run_lint`, `write_lint_report`
- `ultra_brain.monitor` — `DedupStore`, `canonicalize_url`, `parse_rss`
- `ultra_brain.query` — `query_vault`
- `ultra_brain.research` — `aggregate_research`, `plan_research`, `worker_summary`
- `ultra_brain.review` — `write_weekly_review`
- `ultra_brain.telos` — `TelosSessionStore`, `score_alignment`
- `ultra_brain.trust` — `classify_action`
- `ultra_brain.vault` — `ensure_vault`

**Not covered:**
- `ultra_brain.llm` — `complete()` (LLM-gated, never called in tests)
- `ultra_brain.express` — `daily_digest`, `project_briefing`, `tts_placeholder`
- `ultra_brain.__main__` — CLI dispatch logic
- `ultra_brain.monitor.run_poll` — live network fetching path
- `ultra_brain.lint.run_llm_lint` — LLM-driven lint pass
- `ultra_brain.query.synthesize_answer` LLM branch
- `ultra_brain.ingest.Extractor._extract_url`, `_extract_crawl4ai`, `_extract_jina` — live URL extraction

**View Coverage:**
```bash
python -m pytest tests/ --cov=ultra_brain --cov-report=term-missing
```

## Test Types

**Integration Tests (all 8 tests):**
- Each test exercises a full cross-module workflow: create vault → run operation → assert file contents
- Tests are integration-style because modules interact deeply through shared filesystem state (vault layout, log files, cost ledger)

**Unit Tests:** None. No isolated function-level tests exist.

**E2E Tests:** Not used. No HTTP calls, no Telegram, no LiteLLM invocations during tests.

## Common Patterns

**Temp directory isolation:**
```python
def test_X(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "vault"
        ensure_vault(vault)
        # ... test body
```

**File content assertion:**
```python
text = result.note_path.read_text(encoding="utf-8")
self.assertIn("prompt-caching", text)
self.assertIn("brain.ingest", (vault / "_system" / "log.md").read_text(encoding="utf-8"))
```

**Numeric threshold assertion:**
```python
self.assertIn("0.010000", ledger.path.read_text(encoding="utf-8"))
self.assertGreater(score.score, 0.5)
```

**State machine / sequential assertion (cost gate):**
```python
first = ledger.record(scope="test", operation="a", model="m", cost_usd=0.79)
self.assertTrue(first.allowed)
self.assertFalse(first.warning)
second = ledger.record(scope="test", operation="b", model="m", cost_usd=0.10)
self.assertTrue(second.allowed)
self.assertTrue(second.warning)
refused = ledger.record(scope="test", operation="c", model="m", cost_usd=0.20)
self.assertFalse(refused.allowed)
```

**Async Testing:** Not applicable — all code is synchronous.

**Error/Refusal Testing:**
```python
private = classify_action("summarize <private>secret</private>", private_worker_available=False)
self.assertFalse(private.allowed)
self.assertNotIn("secret", private.sanitized_text)

high = classify_action("run shell rm -rf /")
self.assertFalse(high.allowed)
self.assertEqual(high.risk, "high")
```

## Notes for Adding New Tests

- Place new test methods in `tests/test_core.py::CoreTest`
- Use `tempfile.TemporaryDirectory` + `ensure_vault` for any test touching the vault
- Do not supply `llm_model` unless specifically testing LLM branching (requires a live LiteLLM instance)
- Assert by reading actual file content, not by inspecting in-memory state
- Name tests as full scenario descriptions: `test_<subject>_<condition>_<expected>`

---

*Testing analysis: 2026-05-19*
