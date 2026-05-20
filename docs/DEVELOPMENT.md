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

No automated formatter or linter is configured in the repository (no `pyproject.toml`, `.flake8`, or `ruff.toml` detected). The `scripts/lint-check.sh` script lints vault **Markdown** content, not Python source.

Follow standard Python style (PEP 8) and match the conventions visible in the existing source under `ultra_brain/` and `agentos/`.

## Branch Conventions

No branch naming convention is documented in the repository. No `.github/` directory or pull request template exists.

## PR Process

No pull request workflow is documented. The project is private with no GitHub Actions CI pipeline detected.
