# Codebase Concerns

**Analysis Date:** 2026-05-19

---

## Critical: Hermes Is a Hallucinated Docker Image

**The most significant concern in this codebase.**

- Risk: `ghcr.io/nousresearch/hermes-agent:v2026.5.16` does not exist. NousResearch does not publish a "Hermes Agent" runtime container. This image will fail to pull on any VPS.
- Files: `deploy/docker-compose.yml:23`, `deploy/hermes/config.yaml:2`, `.env.example:26`, `docs/runbooks/recovery.md:99`
- Current mitigation: None. `ops/decisions.md:14` documents the pin as if it were verified ("documented from the parent agent's GitHub release check"), but this was a hallucination during planning.
- Impact: The entire Telegram gateway layer — the primary human interface to the system — cannot run. Task `04-hermes-telegram-runtime.md` cannot be completed as written.
- Fix approach: Replace Hermes with a native Python `python-telegram-bot` service that calls `ultra_brain` modules directly. The Python codebase (`ultra_brain/`) already implements all skill logic. The Hermes container is only needed as a message dispatcher. A ~150-line `telegram_bot.py` entry point with `python-telegram-bot` is the correct replacement. Remove the `hermes:` service block from `docker-compose.yml`, remove `deploy/hermes/config.yaml`, and update all runbooks and health-check scripts.

---

## Tech Debt

**Hallucinated image baked into multiple config layers:**
- Issue: `HERMES_IMAGE`, `HERMES_HTTP_PORT`, `HERMES_CONFIG_DIR`, `HERMES_SKILLS_DIR`, `HERMES_STATE_DIR`, `HERMES_TELEGRAM_WEBHOOK_URL` env vars in `.env.example` all exist solely for the non-existent container.
- Files: `.env.example:26-31`, `deploy/docker-compose.yml:22-46`, `deploy/hermes/config.yaml` (entire file)
- Impact: Every deployment instruction in `docs/runbooks/vps-foundation.md` that references Hermes is incorrect.
- Fix approach: Once Hermes is replaced, purge these vars and config files. Add native Python service under `deploy/` (e.g., `deploy/telegram/`) with its own systemd unit or compose service.

**`skills/` directory is a documentation layer with no runtime hook:**
- Issue: `skills/brain.ingest/`, `skills/brain.query/`, etc. contain `SKILL.md` files and thin Python wrappers, but there is no runtime dispatcher that reads them. They are intended to be loaded by Hermes's `skills.directory` config, which does not exist.
- Files: All `skills/*/` directories
- Impact: Skills are never invoked at runtime. The `ultra_brain/` package contains the real implementation; the `skills/` tree is orphaned until a dispatcher is built.
- Fix approach: After replacing Hermes, decide whether skills are Python entry points called by the bot dispatcher, or remove the `skills/` duplication and call `ultra_brain/` modules directly.

**`feeds.yaml` is a YAML config that the `run_poll()` function ignores:**
- Issue: `skills/worker.monitor/feeds.yaml` is a structured YAML file documenting feed placeholders with `enabled: false`. However `ultra_brain/monitor.py:run_poll()` reads a plain text file (one URL per line), not YAML. The YAML is never parsed.
- Files: `skills/worker.monitor/feeds.yaml`, `ultra_brain/monitor.py:112-113`, `ultra_brain/__main__.py:121-126`
- Impact: If a user creates a `feeds.txt` as the CLI expects, the YAML file is ignored. If a user reads the YAML file expecting it to configure the monitor, they will see silently no feeds load.
- Fix approach: Either parse the YAML in `run_poll()` and respect `enabled: true/false`, or replace the YAML with a plain text file and document it clearly.

**`tts_placeholder` is the only TTS implementation:**
- Issue: `ultra_brain/express.py:55-57` writes a text file as a "TTS placeholder." There is no real TTS integration. `skills/brain.express/tts.py` wraps this placeholder.
- Files: `ultra_brain/express.py:55-57`, `skills/brain.express/tts.py`
- Impact: The `brain.express` skill promises audio delivery but produces a `.txt` file instead.
- Fix approach: Implement OpenAI TTS (`openai.audio.speech`) or ElevenLabs integration, gated behind `OPENAI_API_KEY` availability, with the placeholder as fallback.

**`ingest.py` entity pages use a hardcoded `ai-tooling-landscape` path:**
- Issue: `ultra_brain/ingest.py:215` always writes entity stubs to `01-Areas/ai-tooling-landscape/entities/`. This is hardcoded regardless of the entity's actual domain.
- Files: `ultra_brain/ingest.py:215`
- Impact: All entities — people, companies, concepts — land in an AI tooling area even if they have no relation to AI tooling.
- Fix approach: Either derive the area from the entity type/tags or accept an `entity_area` parameter in `Filer.file()`.

**`git-sync.sh` uses `git add -A`:**
- Issue: `scripts/git-sync.sh:26` stages all files including any unintended artifacts. On a VPS where the vault directory may accumulate temp files, this can commit noise.
- Files: `scripts/git-sync.sh:26`
- Impact: Low risk today, but becomes a reliability issue when the monitor or research workers create intermediate files.
- Fix approach: Add a `.gitignore` to the vault root (already scaffolded at `vault/`) or switch to `git add -u` to stage only tracked-file changes.

**Cost ledger is a Markdown table, not a database:**
- Issue: `ultra_brain/cost.py` reads and writes cost data as an append-only Markdown table. Querying today's spend requires a full file scan on every `record()` call.
- Files: `ultra_brain/cost.py:61-75`, `ultra_brain/cost.py:77-79`
- Impact: Performance degrades linearly as the ledger grows. At 100+ daily operations over months, `spent_today()` will scan thousands of lines per call.
- Fix approach: SQLite (already installed by `vps-bootstrap.sh`) with a simple schema. The Markdown file can remain as a human-readable export.

---

## Security Considerations

**`health-check.sh` and `cost-check.sh` expose bot token via process args:**
- Risk: Both scripts call `curl` with `TELEGRAM_BOT_TOKEN` interpolated into a URL on the command line (`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/...`). Bot tokens in URLs appear in process listings (`ps aux`) and shell history.
- Files: `scripts/health-check.sh:24`, `scripts/cost-check.sh:14`
- Current mitigation: None.
- Recommendations: Use `curl -H "Authorization: Bearer $TOKEN"` against the Bot API's header-auth endpoint, or write the URL to a temp file with `curl --config`.

**`LITELLM_MASTER_KEY` defaults to empty string:**
- Risk: `ultra_brain/llm.py:18` reads `LITELLM_MASTER_KEY` with a default of `""`. If the env var is missing, all LiteLLM requests are sent without authorization. LiteLLM's `general_settings.master_key` is set from the same var. An unconfigured key means any process on the VPS can query the model gateway.
- Files: `ultra_brain/llm.py:18`, `deploy/litellm/config.yaml:95`
- Current mitigation: LiteLLM is bound to `127.0.0.1:4000` in `network_mode: host`, reducing exposure to localhost.
- Recommendations: Fail loudly at startup if `LITELLM_MASTER_KEY` is empty. Add a check in `__main__.py` or a startup validator.

**`trust.py` keyword matching is bypassable:**
- Risk: `ultra_brain/trust.py:HIGH_RISK_RE` is a simple regex. An adversarial prompt can reformat high-risk phrases (word breaks, unicode homoglyphs, multi-turn decomposition) to bypass the pattern.
- Files: `ultra_brain/trust.py:15-18`
- Current mitigation: The regex covers the most direct phrasings.
- Recommendations: This is known-hard and acceptable for a personal assistant. Document the limitation explicitly. Add a test for at least one evasion variant.

**`_extract_jina` sends every ingested URL to `r.jina.ai` (external service):**
- Risk: `ultra_brain/ingest.py:87-93` proxies all URL extractions through Jina AI's public reader service when Crawl4AI is unavailable. This leaks the URLs being researched to a third party.
- Files: `ultra_brain/ingest.py:87-93`
- Current mitigation: Crawl4AI is checked first; Jina is only a fallback.
- Recommendations: Document in `SKILL.md` that Jina is an external fallback. Add an `enable_jina=False` default option or at minimum a log warning when the Jina path is taken.

---

## Missing Critical Features

**No Telegram bot implementation exists:**
- Problem: The entire user-facing interface (Telegram) depends on a non-existent container. There is no Python file that starts a Telegram bot, registers command handlers, or calls `ultra_brain` modules.
- Blocks: Everything. The system cannot receive user input.
- Required: A `telegram_bot.py` (or equivalent) using `python-telegram-bot` or `aiogram`, calling `ultra_brain.__main__.main()` or module functions directly.

**No `pyproject.toml` or `setup.py`:**
- Problem: `ultra_brain/` is a proper Python package with `__init__.py` and `__main__.py`, but there is no `pyproject.toml`, `setup.py`, or `requirements.txt`.
- Blocks: Cannot `pip install` the package. The cron entries in `deploy/cron/ultra-agents-brain.cron:8-13` call `python3 -m ultra_brain` but rely on `PYTHONPATH` being set externally. `scripts/lint-check.sh:32` sets `PYTHONPATH` as a workaround.
- Fix approach: Add a minimal `pyproject.toml` with `[build-system]` and `[project]` sections.

**No reverse proxy / webhook endpoint config:**
- Problem: Telegram webhooks require a public HTTPS endpoint. `docs/runbooks/vps-foundation.md:89-96` says "point your reverse proxy or tunnel" but provides no config. There is no nginx, caddy, or tunnel config anywhere in `deploy/`.
- Blocks: Telegram webhook mode cannot be activated without this.
- Fix approach: Add an nginx config fragment or Caddy Caddyfile in `deploy/` for the webhook path.

**`monitor` cron uses `feeds.txt` which does not exist in the repo:**
- Problem: `deploy/cron/ultra-agents-brain.cron:12` calls `python3 -m ultra_brain ... monitor` with the default `--feeds feeds.txt`. This file is not in the repo.
- Files: `deploy/cron/ultra-agents-brain.cron:12`, `ultra_brain/__main__.py:121-126`
- Impact: The cron job silently does nothing (the CLI prints a message and exits 0 when the file is missing).
- Fix approach: Either ship a starter `feeds.txt` or change the default to the `skills/worker.monitor/feeds.yaml` path (after fixing the format mismatch).

**No vault initialization step in the deployment sequence:**
- Problem: `ultra_brain/vault.py:ensure_vault()` creates the PARA structure but is never called by cron jobs or the startup sequence. The cron entries assume `/srv/second-brain` is already a Git repo with the vault layout.
- Files: `deploy/cron/ultra-agents-brain.cron`, `docs/runbooks/vps-foundation.md`
- Fix approach: Add an `ensure-vault` call to `vps-bootstrap.sh` after cloning the vault repo.

---

## Test Coverage Gaps

**No tests for `express.py`, `vault.py`, `markdown.py`, `llm.py`:**
- What's not tested: `daily_digest()`, `project_briefing()`, `tts_placeholder()`, `ensure_vault()`, `unique_path()`, `llm.complete()`, all markdown helper functions.
- Files: `ultra_brain/express.py`, `ultra_brain/vault.py`, `ultra_brain/markdown.py`, `ultra_brain/llm.py`
- Risk: `llm.py` is the single HTTP call layer; any breakage goes undetected. `vault.py` creates directory structure used by every other module.
- Priority: High for `vault.py` and `markdown.py`; medium for `llm.py` (needs mock).

**No tests for edge cases in `trust.py`:**
- What's not tested: Medium-risk path requiring approval, private-worker routing when `private_worker_available=True`, `approval_prompt()` output, boundary cases in regex matching (e.g., `rm -rf` split across words).
- Files: `ultra_brain/trust.py`, `tests/test_core.py:57-63`
- Priority: High — trust is a security boundary.

**No tests for `run_poll()` / `fetch_feed()` with mock HTTP:**
- What's not tested: Feed fetch errors, partial feed failures, scoring path, dedup persistence across calls, Inbox file writing.
- Files: `ultra_brain/monitor.py:85-157`, `tests/test_core.py:101-109`
- Priority: Medium — the test covers `parse_rss` and `DedupStore` but not the full integration path.

**No integration tests for cron script behavior:**
- What's not tested: `scripts/health-check.sh` failure modes, `scripts/cost-check.sh` awk logic with real ledger content, `scripts/git-sync.sh` conflict handling.
- Files: `scripts/`
- Priority: Medium — these are the operational safety net.

**`test_research_aggregation_creates_project_outputs` does not use LLM:**
- What's not tested: `worker_summary()` with a live `llm_model`, `aggregate_research()` synthesis quality, the LLM-assisted PARA classification in `Filer._choose_tier()`.
- Files: `tests/test_core.py:65-74`, `ultra_brain/research.py`, `ultra_brain/ingest.py:178-201`
- Priority: Low for CI (requires LiteLLM); medium for a separate smoke-test suite.

---

## Fragile Areas

**`cost.py` Markdown parsing:**
- Files: `ultra_brain/cost.py:61-75`
- Why fragile: The ledger parser splits on `|` and accesses cells by index. Any note field containing a pipe character corrupts the parse silently. The `record()` method sanitizes `|` to `/` in the `notes` field but not in `scope`, `operation`, or `model`.
- Safe modification: Always sanitize all string fields before writing. Add a test with pipe-containing strings.

**`telos.py` session ID assignment:**
- Files: `ultra_brain/telos.py:39`
- Why fragile: Session IDs are assigned as `len(sessions) + 1`. If a session is deleted from the JSON, the next session gets a duplicate ID. The `answer()` method finds sessions by ID using linear search, so the first match wins.
- Safe modification: Use a monotonic counter stored in the JSON root rather than `len(sessions)`.

**`query.py` ripgrep fallback reads every `.md` file in-process:**
- Files: `ultra_brain/query.py:33-46`
- Why fragile: `RipgrepRetriever.search()` reads all Markdown files into memory with `path.read_text()`. On a large vault this can exhaust memory. There is no size limit per file.
- Safe modification: Add a file size guard (`if path.stat().st_size > 1_000_000: continue`) and a cap on total files scanned.

**`systemd` unit does not specify a user:**
- Files: `deploy/systemd/ultra-agents-brain.service`
- Why fragile: The unit has no `User=` directive. `ExecStart` runs `docker compose up -d`, which works only if the invoking user has Docker socket access. If systemd runs this as root, Docker runs as root. If run as `uabrain`, Docker access requires the group membership set by `vps-bootstrap.sh`, but systemd group membership changes require re-login.
- Safe modification: Add `User=uabrain` and `Group=docker` to the `[Service]` section.

---

## Scaling Limits

**Cost ledger (Markdown table):**
- Current capacity: Unbounded text file, linear scan.
- Limit: Practical degradation begins around 10,000 rows (~500KB file).
- Scaling path: Migrate to SQLite (already on VPS per `vps-bootstrap.sh`).

**`RipgrepRetriever` in-process search:**
- Current capacity: Acceptable for a vault under ~500 files.
- Limit: Full-file reads on 2,000+ notes may exceed 1GB RAM on a 4GB VPS during query bursts.
- Scaling path: `qmd` (already wired as the preferred path in `query_vault()`), or vector embeddings via a local model.

**`DedupStore` (JSON file):**
- Current capacity: Fine for thousands of URL hashes.
- Limit: JSON parse/write on every poll for 100,000+ seen items becomes slow.
- Scaling path: SQLite set or Bloom filter file.

---

## Unresolved Human Prerequisites (from `ops/decisions.md`)

The following are not code concerns but block any deployment. They are listed here for completeness:

- Hostinger VPS not yet confirmed to exist or be SSH-accessible.
- Telegram bot token not yet created.
- Anthropic API key not confirmed.
- Vault remote GitHub repository not yet created.
- Tailscale account and tailnet not confirmed.
- `OLLAMA_API_BASE` / Ollama-on-Mac strategy undecided.
- `VAULT_REMOTE_URL`, `VAULT_VPS_PATH`, `VAULT_MAC_PATH` not set.

---

*Concerns audit: 2026-05-19*
