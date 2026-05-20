<!-- generated-by: gsd-doc-writer -->
# Testing

## Test Framework and Setup

The project uses **pytest** (version 9.0.3, as reflected in the `.pytest_cache` build artifacts) with Python 3.13. Tests live in the `tests/` directory at the project root.

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

## Writing New Tests

Test files follow the naming convention `test_*.py` and live in the `tests/` directory. There is no shared `conftest.py` or test helper module — each test file imports directly from the modules it exercises.

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

No CI/CD pipeline is configured. There is no `.github/workflows/` directory in the repository. Tests must be run locally before committing.
