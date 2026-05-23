<!-- generated-by: gsd-doc-writer -->
# Testing

## Test Framework and Setup

The project uses **pytest 9.0.3** with **Python 3.13.7**. Tests live in `tests/` with two subdirectories: `tests/unit/` and `tests/integration/`. Shared fixtures live in `tests/conftest.py` (sets `LITELLM_MASTER_KEY` for transitive imports, provides `tmp_vault`, `live_postgres_dsn_knowledge`, and the EVAL-02 suite write hook).

Before running tests, ensure the virtual environment is active and dependencies are installed:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
```

No additional test-specific dependencies are declared in `requirements.txt`. Pytest is available via the `.venv/bin/pytest` binary.

## Running Tests

Run the full test suite from the project root:

```bash
pytest tests/
```

Run a single test file:

```bash
pytest tests/test_core.py
pytest tests/test_agentos.py
pytest tests/test_telegram_adapter.py
```

Run with verbose output:

```bash
pytest tests/ -v
```

Run a specific test by name:

```bash
pytest tests/test_core.py -k "test_name"
```

### Marker tiers (declared in `pytest.ini`)

```bash
pytest -k smoke         # fast schema-level assertions, no LLM calls
pytest -k integration   # full agent runs, requires live LiteLLM + DB
pytest -k live          # requires deployed VPS (set POSTGRES_DSN_KNOWLEDGE etc.)
pytest -k "smoke or unit"  # combine for local pre-push checks
```

The `live` tier auto-skips when required env vars (`POSTGRES_DSN_KNOWLEDGE`, etc.) are unset.

## Writing New Tests

Test files follow the naming convention `test_*.py`. Use `tests/unit/` for pure logic, `tests/integration/` for tests that need a running LiteLLM or DB, and the top-level `tests/test_*.py` files for the legacy three suites. Shared fixtures live in `tests/conftest.py`.

Existing test files map to their modules as follows:

| Test file | Module under test |
|-----------|-------------------|
| `tests/test_core.py` | `ultra_brain` core APIs (trust, cost, ingest, vault) |
| `tests/test_agentos.py` | `agentos/` agent orchestration layer |
| `tests/test_telegram_adapter.py` | `channels/` Telegram adapter |

New test files should be added to `tests/` with the `test_` prefix and import from the corresponding source module.

## Coverage Requirements

No coverage threshold is configured. There is no `.nycrc`, `c8` config, or `pytest-cov` section in any configuration file.

To generate a coverage report manually, install `pytest-cov` and run:

```bash
pip install pytest-cov
pytest tests/ --cov=ultra_brain --cov=agentos --cov=channels --cov-report=term-missing
```

## CI Integration

No GitHub Actions or other remote CI is configured (no `.github/workflows/`). The local quality gate is a **pre-commit hook** (`tools/precommit_eval_router.sh` via `.pre-commit-config.yaml`) that runs scoped smoke-tier agent evals on changed files. Install once per clone with `pre-commit install`. Tests beyond what the hook covers must be run manually before committing.
