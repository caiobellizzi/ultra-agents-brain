# Technology Stack

**Analysis Date:** 2026-05-19

## Languages

**Primary:**
- Python 3 (3.x) - All application logic in `ultra_brain/` package and `skills/*/` Python helpers
- Bash - Operational scripts in `scripts/`, VPS bootstrap, cron jobs

**Secondary:**
- YAML - Service configuration (`deploy/litellm/config.yaml`, `deploy/hermes/config.yaml`, `skills/worker.monitor/feeds.yaml`)

## Runtime

**Environment:**
- Python 3 (CPython) — no version pin detected in repo; system Python 3 assumed on VPS (Debian)
- No `.python-version`, `pyproject.toml`, `setup.py`, or `requirements.txt` present

**Package Manager:**
- None — the `ultra_brain` package has zero third-party Python dependencies; pure stdlib only
- Lockfile: Not applicable

**System packages installed by `scripts/vps-bootstrap.sh`:**
- `docker.io`, `docker-compose-v2` (runtime for LiteLLM + Hermes containers)
- `git`, `gh`, `jq`, `ripgrep`, `sqlite3`, `curl`, `tailscale`, `ufw`

## Frameworks

**Core:**
- None — `ultra_brain` is a pure-stdlib Python package; no web framework, no ORM

**Agent Runtime:**
- Hermes Agent (`ghcr.io/nousresearch/hermes-agent:v2026.5.16`) — Docker container that loads skills and handles the Telegram webhook gateway

**LLM Proxy:**
- LiteLLM (`ghcr.io/berriai/litellm:main-latest`) — OpenAI-compatible proxy that routes model-tier aliases to backends

**Testing:**
- Python `unittest` (stdlib) — `tests/test_core.py`

**Build/Dev:**
- No build step; Python package is run directly as `python3 -m ultra_brain`

## Key Dependencies

**Critical (stdlib only — no pip installs):**
- `urllib.request` — all HTTP calls (LiteLLM proxy, Crawl4AI, Jina Reader, RSS feeds)
- `xml.etree.ElementTree` — RSS/Atom feed parsing in `ultra_brain/monitor.py`
- `json` — LLM request/response serialization, session stores, dedup stores
- `hashlib` — SHA-256 content hashing for dedup and note IDs
- `pathlib` — all vault filesystem operations
- `argparse` — CLI entry point in `ultra_brain/__main__.py`
- `subprocess` — optional `qmd` search client in `ultra_brain/query.py`
- `dataclasses` — all domain types (ExtractionResult, CostEntry, TrustDecision, etc.)
- `re` — Markdown parsing, trust gate pattern matching, slug generation

**Optional External Binaries (not installed by default):**
- `qmd` — semantic search CLI; falls back to pure Python ripgrep-style search if absent
- `curl` — used in shell scripts for health checks and Telegram API calls

## Configuration

**Environment:**
- Single `.env` file at `$UAB_PROJECT_ROOT/.env` on VPS (copied from `.env.example`)
- Never committed; `.env.example` documents all required variables
- Key env vars consumed by `ultra_brain/llm.py`:
  - `LITELLM_BASE_URL` (default: `http://127.0.0.1:4000/v1`)
  - `LITELLM_MASTER_KEY`
- Key env vars consumed by `ultra_brain/ingest.py`:
  - `CRAWL4AI_ENDPOINT` (optional; falls back to Jina Reader then placeholder)

**Build:**
- No build config files — no `Dockerfile` for the Python package itself
- `deploy/docker-compose.yml` is the compose manifest for LiteLLM + Hermes containers
- Containers launched via systemd unit `deploy/systemd/ultra-agents-brain.service`

## Scheduled Jobs

Cron schedule defined in `deploy/cron/ultra-agents-brain.cron`, run as `uabrain` service user:

| Schedule | Job |
|----------|-----|
| Every 15 min | `scripts/health-check.sh --quiet` |
| Daily 08:05 | `scripts/cost-check.sh` |
| Monday 07:15 | `scripts/lint-check.sh` |
| Daily 20:00 | `python3 -m ultra_brain --vault $SECOND_BRAIN_DIR digest` |
| Sunday 18:00 | `python3 -m ultra_brain --vault $SECOND_BRAIN_DIR review` |
| Every 4 hours | `python3 -m ultra_brain --vault $SECOND_BRAIN_DIR monitor` |
| Daily 02:00 | `python3 -m ultra_brain --vault $SECOND_BRAIN_DIR lint --report` |

## Platform Requirements

**Development:**
- Python 3 with no extra packages
- Run tests: `python3 -m pytest tests/` or `python3 -m unittest tests/test_core.py`
- All tests use `tempfile.TemporaryDirectory`; no external services required

**Production:**
- Debian/Ubuntu VPS (bootstrap script targets `apt-get`)
- Docker + Docker Compose v2
- Tailscale (network access to LM Studio via LM Link)
- `uabrain` service user with Docker group membership
- Vault directory at `/srv/second-brain` (git-tracked Markdown files)

---

*Stack analysis: 2026-05-19*
