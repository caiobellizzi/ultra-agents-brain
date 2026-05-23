<!-- generated-by: gsd-doc-writer -->
# Development

## Local Setup

1. Clone the repository and enter the project directory:

```bash
git clone <repo-url>
cd ultra-agents-brain
```

2. Create and activate a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Copy the environment template and fill in secrets:

```bash
cp .env.example .env
```

5. Start the LiteLLM proxy and supporting services (required for model calls):

```bash
docker compose -f deploy/docker-compose.yml up -d
```

6. (Optional) Start the AgentOS FastAPI host for local HTTP access:

```bash
uvicorn agentos.app:app --host 0.0.0.0 --port 7001 --reload
```

See `docs/CONFIGURATION.md` for a full description of all environment variables.

## Build Commands

This project has no build step — Python source is run directly. The following operational scripts live in `scripts/`:

| Script | Description |
|---|---|
| `scripts/lint-check.sh` | Lint vault Markdown files via the Python CLI or LiteLLM API fallback |
| `scripts/smoke_agno.py` | Smoke test for Agno agent connectivity |
| `scripts/smoke-litellm.sh` | Smoke test for the LiteLLM proxy endpoint |
| `scripts/health-check.sh` | System and agent health check |
| `scripts/cost-check.sh` | Print LLM spending summary |
| `scripts/git-sync.sh` | Sync the vault git repository |
| `scripts/vps-bootstrap.sh` | Provision a fresh VPS deployment |

## Code Style

No automated Python formatter is configured (no `pyproject.toml`, `.flake8`, or `ruff.toml`). The `scripts/lint-check.sh` script lints vault **Markdown** content, not Python source.

Follow standard Python style (PEP 8) and match the conventions visible in the existing source under `ultra_brain/` and `agentos/`.

## Pre-commit hook

`.pre-commit-config.yaml` registers one local hook:

| Hook | Script | When |
|------|--------|------|
| `scoped-evals` | `tools/precommit_eval_router.sh` | `pre-commit`, only when the changed files require it (`always_run: false`) |

Install once per clone: `pip install pre-commit && pre-commit install`. The router runs the smoke-tier agent evals scoped to whatever files you staged.

## Test markers

`pytest.ini` defines three marker tiers — select with `-k` or `-m`:

- `smoke` — fast schema-level assertions, no LLM calls
- `integration` — full agent runs, requires live services
- `live` — requires a deployed VPS; skip in unit-only CI runs

Test layout: `tests/unit/`, `tests/integration/`, top-level `tests/test_*.py`, shared fixtures in `tests/conftest.py` (includes the EVAL-02 suite write hook).

## Branch Conventions

No branch naming convention is documented in the repository. No `.github/` directory or pull request template exists.

## PR Process

No pull request workflow is documented. The project is private with no GitHub Actions CI pipeline detected. Local pre-commit + manual `pytest -k smoke` is the de facto gate.
