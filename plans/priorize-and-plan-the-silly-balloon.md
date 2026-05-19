# Plan: Prioritize and close ultra-agents-brain implementation gaps

**Status:** Draft, awaiting approval via ExitPlanMode
**Date:** 2026-05-18
**Owner:** Caio Bellizzi
**Working directory:** `~/Documents/Projects/ultra-agents-brain/`
**Sequencing:** Value-first (LLM client + first end-to-end win, then expand)
**Source plan being implemented against:** `plans/ultra-research-about-mult-generic-cocke.md`

---

## Context

The codebase is ~75% complete against the source plan. All 13 `ultra_brain/*.py` modules, all 9 SKILL.md files, the LiteLLM/Hermes Docker stack, and the test suite exist and pass. **But no module ever invokes an LLM.** The 10 pre-written prompt files in `skills/*/prompts/` sit on disk untouched. The system today is a high-quality deterministic scaffold with zero AI value delivered.

This plan sequences the work to wire the LLM layer first (single highest-leverage gap), close operational holes second, then deploy. Human-gate prerequisites run as a parallel track owned by the user.

**End state after Phases 1–6:** `python -m ultra_brain query "what is my TELOS?"` returns an LLM-synthesized answer locally; ingest summarizes URLs into the vault; daily digest synthesizes log lines; monitor polls RSS into `Inbox/`; research worker plans + fetches + summarizes; git-sync keeps the vault on GitHub; cron schedules daily/weekly/4h jobs. With Phase 0 done, the system runs unattended on the VPS, accessible via Telegram.

---

## First cut — start here (≈3 hours)

**Phase 1 + first half of Phase 2 in one sitting.** Result: the first real LLM answer returned by the local system.

1. Write `ultra_brain/llm.py` (stdlib `urllib.request` wrapper, ~25 LOC)
2. Add `LLMClientTest` to `tests/test_core.py` with mocked `urlopen` — establishes the mock pattern for all later phases
3. Replace `query.py:72` `synthesize_answer()` body with `llm.complete()` using `skills/brain.query/prompts/query-synthesis.md`
4. Run `python -m ultra_brain query "what is my TELOS?"` against a live LiteLLM proxy → real answer

This unblocks every subsequent phase without touching any other seam.

---

## Phase 0 — Human-gate prerequisites (parallel track, user-owned)

Listed in `ops/decisions.md`. None block Phases 1–4 (everything mock-tests locally). They block Phase 5 (live deploy) only.

| # | Item | Blocking from |
|---|---|---|
| 1 | Hostinger VPS provisioned (Ubuntu 24.04, 2 vCPU / 4 GB) and SSH-reachable | Phase 5 |
| 2 | Telegram bot created via BotFather, token stored | Phase 5 (Telegram path) |
| 3 | Anthropic API key confirmed | Live LLM smoke tests (parallel) |
| 4 | At least one fallback provider key (Groq preferred) | LiteLLM fallback chain |
| 5 | Private GitHub repo for vault remote | `git-sync.sh` push path (Phase 3) |
| 6 | Tailscale account + target tailnet decided | Phase 5 (VPS networking) |
| 7 | Decide Ollama-on-Mac role (v1 or fallback-only) | Phase 5 (model routing) |
| 8 | Exact vault paths on VPS + Mac decided | Phase 3 (git-sync), Phase 5 |
| 9 | Webhook URL pattern decided | Phase 5 (Hermes config) |

**Suggested ordering for human work:** #1 → #3 → #4 → #5 → #6 → #2 → #8 → #9 → #7. Items #3 and #4 are highest priority since they let Phase 1's live smoke test run.

---

## Phase 1 — LLM client foundation (≈2 h)

**Goal:** Make every LLM call cheap, mockable, and stdlib-only.

**Files:**
- `ultra_brain/llm.py` — NEW. Exposes `complete(prompt, *, model="default-worker", system=None, max_tokens=2048, timeout=120) -> str` and `LLMError`. Reads `LITELLM_BASE_URL` (default `http://127.0.0.1:4000/v1`) and `LITELLM_MASTER_KEY` from env. Uses `urllib.request` against `/chat/completions`. ~25 LOC.
- `tests/test_core.py` — add `LLMClientTest(TestCase)`: patch `urllib.request.urlopen`, assert headers, assert body shape, assert returned content extraction.

**Reuse:** Mirrors the `urllib.request` usage already in `ingest.py:75-81` (Crawl4AI extraction) and `monitor.py:64-65` (RSS fetch). No new external deps.

**Acceptance:**
- `python -m unittest tests.test_core.LLMClientTest` passes
- `LITELLM_MASTER_KEY=... python -c "from ultra_brain.llm import complete; print(complete('ping'))"` returns a string against a live proxy
- `pip show litellm` still fails — discipline preserved

**Risk:** Verify the 5 model alias names against `deploy/litellm/config.yaml` before hardcoding `default-worker` as the default — exact match required.

---

## Phase 2 — Query synthesis + ingest summarization (≈3 h)

**Goal:** First user-visible AI value. Wire LLM into the two highest-traffic seams.

**Files:**
- `ultra_brain/query.py:72` — replace `synthesize_answer()` body with `llm.complete(prompt, system=open(prompts_dir/"query-synthesis.md").read())` passing `hits` as context. Keep function signature unchanged.
- `ultra_brain/ingest.py:113` (`Filer.file()`) + `ingest.py:210-211` (`ingest_source()`) — after `Extractor.extract()` returns, call `llm.complete()` with `skills/brain.ingest/prompts/ingestion-summary.md` prompt. Parse structured response into `para_tier`, `tags`, `entities`, `concepts`, `summary`. Write `summary:` into YAML frontmatter. Degrade gracefully (skip summary, log warning) when `LITELLM_MASTER_KEY` is absent.
- `ultra_brain/cost.py` — already supports `CostLedger.record()`. Each LLM call records cost. No changes required.
- `tests/test_core.py` — add `QueryLLMTest` and `IngestSummaryTest`, both patching `ultra_brain.llm.complete` with a fixture response.

**Reuse:** Existing prompt files at `skills/brain.query/prompts/query-synthesis.md` and `skills/brain.ingest/prompts/ingestion-summary.md`. Cost ledger pattern at `ingest.py:169`.

**Acceptance:**
- `python -m ultra_brain query "what is my TELOS?"` returns synthesized narrative with citations, not bullet list
- `python -m ultra_brain ingest <url>` produces a note with non-empty `summary:` frontmatter
- Cost ledger row appended per LLM call
- Both new unit tests pass

**Risk:** `cheap-worker` may be more appropriate than `default-worker` for summarization (~10× cost difference). Default to `default-worker` per plan but make `model=` overridable from CLI.

---

## Phase 3 — Operational loops (digest, monitor, git-sync, cron) (≈5 h)

Two parallel tracks; both depend only on Phase 1.

### Track A — LLM-synthesized digest + briefing (≈2 h)

**Files:**
- `ultra_brain/express.py:11-23` — `daily_digest()`: after assembling raw log lines, call `llm.complete()` with `skills/brain.express/prompts/daily-digest.md`. Output replaces raw log dump.
- `ultra_brain/express.py:26-33` — `project_briefing()`: read project files, call `llm.complete()` with `skills/brain.express/prompts/project-briefing.md`.
- `tests/test_core.py` — `DigestLLMTest` with mocked `llm.complete`.

### Track B — Monitor polling loop + git-sync + cron (≈3 h)

**Files:**
- `ultra_brain/monitor.py` — add `score_items(items, telos_path)` (LLM TELOS relevance using `skills/worker.monitor/prompts/daily-digest.md`) and `run_poll(feeds_yaml, vault_root, --once)`. Items passing relevance threshold written to `vault/Inbox/` via `markdown.append_log`-style helper.
- `ultra_brain/__main__.py` — add `monitor` subcommand (calls `run_poll`).
- `scripts/git-sync.sh` — NEW. `git -C $VAULT_ROOT pull --ff-only`, `git -C $VAULT_ROOT add -A`, `git commit -m "vault: hermes sync $(date -u +%FT%TZ)"` (skip if nothing staged), `git push`. Telegram alert on failure via `health-check.sh` pattern.
- `.env.example` — add `VAULT_ROOT`, `VAULT_GITHUB_REPO`.
- `deploy/cron/ultra-agents-brain.cron` — add 4 entries:
  - `0 20 * * * uabrain` → `python -m ultra_brain digest` (daily digest, 20:00)
  - `0 18 * * 0 uabrain` → `python -m ultra_brain review` (weekly, Sun 18:00; requires Phase 6 verb)
  - `0 */4 * * * uabrain` → `python -m ultra_brain monitor --once`
  - `*/30 * * * * uabrain` → `/opt/ultra-agents-brain/scripts/git-sync.sh`

**Reuse:** `health-check.sh` Telegram alert pattern, `markdown.append_log` for Inbox writes, existing `monitor.py` dedup logic.

**Acceptance:**
- `python -m ultra_brain digest` returns synthesized narrative
- `python -m ultra_brain monitor --once` writes ≥1 stub entry to `vault/Inbox/`
- `bash scripts/git-sync.sh` runs end-to-end in a repo with a remote (uses local fixture if Phase 0 #5 not yet done)
- Cron file has 7 total entries (3 existing + 4 new)

**Risk:** Monitor's per-item LLM call inflates latency — use `cheap-worker`, cap at 50 items/poll. `git-sync.sh` needs `set -euo pipefail` and lockfile (use `flock`) to prevent overlapping runs.

---

## Phase 4 — TELOS alignment gate (≈3 h)

**Goal:** Wire `telos.score_alignment()` automatically into every `trust.approval_prompt()` call.

**Files:**
- `ultra_brain/telos.py:score_alignment()` — replace current word-overlap heuristic body with `llm.complete()` using `skills/telos.check/prompts/telos-check.md`. Parse YAML output to extract score (0.0–1.0) and reasoning string.
- `ultra_brain/trust.py:approval_prompt()` — top of function: call `telos.score_alignment(action, vault_root)`. If score < 0.4, prepend "⚠️ Low TELOS alignment ({score}): {reasoning}" banner to the prompt body.
- `ultra_brain/__main__.py` — `telos-check` subcommand already exists; verify it calls the new LLM-backed `score_alignment`.
- `tests/test_core.py` — `TelosGateTest`: mock `llm.complete` returning low-alignment YAML, assert banner in approval prompt.

**Reuse:** Existing `trust.classify_action` regex pipeline, existing `TelosSessionStore` for reading telos files.

**Acceptance:**
- `python -m ultra_brain telos-check "write a viral tweet"` prints score + reasoning
- Mocked low-alignment action shows warning banner before approval prompt
- High-alignment action proceeds without banner

**Risk:** One round-trip per gated action. Use `cheap-worker`. Consider in-memory cache keyed on `(action_hash, telos_file_mtimes)` if latency becomes painful — defer until measured.

---

## Phase 5 — Deploy + live validation (≈4 h code + human time)

**Blocks on Phase 0 items #1, #2, #3, #4, #5, #6.** Cannot start until VPS exists and keys exist.

**Files:**
- `deploy/docker-compose.yml` — add healthchecks on `litellm` and `hermes` services; verify `vault` volume mount path matches `VAULT_ROOT` decision (Phase 0 #8).
- `deploy/hermes/config.yaml` — fill in actual Telegram webhook URL once Phase 0 #9 decided.
- `.env.example` — finalize all variables; document each. Companion `.env` lives on VPS only, never committed.
- `scripts/smoke-litellm.sh` — already iterates 5 aliases; verify still passes against live proxy.
- `docs/runbooks/cost-cap.md` — NEW. What to do when $20 cap fires (gate which skills, disable which models, manual reset).
- `docs/runbooks/api-key-rotation.md` — NEW. Per-provider rotation steps.
- `docs/runbooks/telegram-webhook.md` — NEW. Rotation, re-registration, dropped-message diagnosis.

**Acceptance per `taks/14-production-validation.md`:**
- `docker compose up -d` brings all services healthy on VPS
- `bash scripts/smoke-litellm.sh` returns ok on all 5 aliases
- Telegram `/query what is my TELOS?` returns synthesized answer within 30 s
- `crontab -l -u uabrain` shows all 7 cron entries
- Cost ledger increments after each Telegram interaction

**Risk:** Tailscale ACLs may block Hermes→LiteLLM. LiteLLM cold-start is 30–60 s; add healthcheck retry with `start_period: 90s`. Hostinger firewall must allow Telegram webhook inbound (TCP 443).

---

## Phase 6 — Research worker + LLM lint + missing CLI verbs (≈5 h)

**Goal:** Complete the autonomous research and lint capabilities. Lower priority because they're not on the daily critical path.

**Files:**
- `ultra_brain/research.py:21-32` (`plan_research()`) — replace 5-hardcoded-angle stub with `llm.complete()` for dynamic angles based on topic.
- `ultra_brain/research.py:35-43` (`worker_summary()`) — add stdlib `urllib.request` fetch loop over `sources` URLs, then `llm.complete()` with `skills/worker.research/prompts/research-summary.md`. Implement per-worker timeout + cost cap.
- `ultra_brain/research.py:61-72` (`aggregate_research()`) — after writing scaffold, call `llm.complete()` to synthesize cross-worker briefing into `synthesis.md` and `briefing.md`.
- `ultra_brain/lint.py:41+` — add `llm_lint_pass(parsed, vault_root)` for contradiction/stale-claims using `skills/brain.lint/prompts/lint-report.md`. Gate behind `--llm` flag so default `lint` stays fast and free. Cap at 50 notes/run.
- `ultra_brain/__main__.py` — add subcommands `monitor` (already in Phase 3), `review` (calls `review.write_weekly_review`), `telos-interview` (calls `telos.TelosSessionStore`).
- `tests/test_core.py` — `ResearchWorkerTest` (mocked LLM + mocked urlopen), `LintLLMPassTest`.

**Reuse:** Existing `monitor.py` URL fetch pattern, existing prompt files.

**Acceptance:**
- `python -m ultra_brain research "agentic memory systems"` produces a vault project dir with `synthesis.md` containing >3 substantive bullet points
- `python -m ultra_brain lint --llm` produces a "Semantic Checks" section in the lint report
- `python -m ultra_brain monitor`, `... review`, `... telos-interview` all resolve

**Risk:** Research URL fetch should respect 1 s minimum sleep between requests as minimum courtesy. LLM lint cost can balloon on large vaults — `cheap-worker` + 50-note cap is required.

---

## Shared blockers map

| Blocker | Blocks | Parallel-safe with |
|---|---|---|
| `ultra_brain/llm.py` missing | Phases 2, 3, 4, 6 | Phase 0 entirely |
| Phase 0 #1 (VPS) | Phase 5 live smoke | Phases 1, 2, 3, 4, 6 (all local) |
| Phase 0 #2 (Telegram) | Phase 5 Telegram path | All others |
| Phase 0 #3 + #4 (API keys) | Live LLM smoke tests | Mock-based tests in Phases 1, 2, 3, 4, 6 |
| Phase 0 #5 (GitHub repo) | `git-sync.sh` push | Phase 3 local fixture testing |

---

## Critical files reference

**New files:**
- `ultra_brain/llm.py` (Phase 1)
- `scripts/git-sync.sh` (Phase 3)
- `docs/runbooks/cost-cap.md` (Phase 5)
- `docs/runbooks/api-key-rotation.md` (Phase 5)
- `docs/runbooks/telegram-webhook.md` (Phase 5)

**Modified files:**
- `ultra_brain/query.py` — Phase 2
- `ultra_brain/ingest.py` — Phase 2
- `ultra_brain/express.py` — Phase 3A
- `ultra_brain/monitor.py` — Phase 3B
- `ultra_brain/telos.py` — Phase 4
- `ultra_brain/trust.py` — Phase 4
- `ultra_brain/lint.py` — Phase 6
- `ultra_brain/research.py` — Phase 6
- `ultra_brain/__main__.py` — Phases 3B (monitor), 6 (review, telos-interview)
- `tests/test_core.py` — Phases 1, 2, 3A, 3B, 4, 6 (add one test class per phase)
- `deploy/cron/ultra-agents-brain.cron` — Phase 3B (+4 entries)
- `.env.example` — Phase 3B (VAULT_ROOT, VAULT_GITHUB_REPO), Phase 5 (finalize)
- `deploy/docker-compose.yml` — Phase 5
- `deploy/hermes/config.yaml` — Phase 5

**Reused functions / utilities (no rewrite needed):**
- `urllib.request` pattern at `ingest.py:75-81` and `monitor.py:64-65` (for `llm.py`)
- `CostLedger.record()` in `cost.py` (called per LLM invocation)
- `markdown.append_log()` (for Inbox writes in Phase 3B)
- `health-check.sh` Telegram alert pattern (for `git-sync.sh` failure path)
- All 10 prompt files in `skills/*/prompts/` (read at runtime)

---

## Verification strategy

**Per phase:** Each new code path lands with at least one unit test in `tests/test_core.py` using the mock pattern established in Phase 1's `LLMClientTest`.

**End-to-end (after Phase 5):**

1. `python -m unittest discover tests` — all tests green (including ~7 new LLM-mocking tests added across phases)
2. `bash scripts/smoke-litellm.sh` against live VPS proxy — 5/5 aliases ok
3. Telegram `/ingest https://example.com/article` — vault gets a note with LLM summary, cost logged
4. Telegram `/query what is my TELOS?` — synthesized answer with citations within 30 s
5. Cron `crontab -l -u uabrain` shows 7 entries
6. Manually wait 24 h, verify `vault/_system/cost-ledger.md` populated, `vault/_system/log.md` populated, `vault/Inbox/` has monitor-captured items
7. Telegram `/research agentic memory systems` — wait, verify vault project dir created with synthesis.md + briefing.md

**Rollback:** Each phase commits cleanly. Phase 1 alone is reversible (delete `llm.py` + revert test). Phase 2 reverts to deterministic synthesis. Phase 5 deploy reverts to local-only via `docker compose down` + git revert.

---

## Open questions / risks

1. **Default model alias** — Phase 1 hardcodes `default-worker` as default; verify this matches user intent (orchestrator vs default-worker for routine calls). Quick fix if wrong; flag for review.
2. **Hermes skill invocation path** — Hermes loads skills via Python import (per exploration). The `ultra_brain/llm.py` module is reachable from `skills/*/*.py` helpers only if `sys.path` includes the project root. Confirm Hermes config's `skills.directory` resolution puts repo root on path — if not, add a setup hook.
3. **TELOS docs are scaffolded but empty** — Phase 4's `score_alignment()` will hallucinate without populated `vault/_system/telos/mission.md` etc. The user must run `telos.interview` (Phase 6 CLI verb) at least once to seed TELOS. Order suggestion: do Phase 6's `telos-interview` verb add before Phase 4 wiring.
4. **Cost cap regression** — six new LLM-call sites multiply daily spend. Phase 2's ingest+query alone could exceed $5/day in heavy use. The existing $20 cap will catch this, but the warning at 80% may fire frequently early on. Monitor via `cost-check.sh` for the first week and tune model aliases per seam.
5. **LiteLLM proxy URL inside Docker** — `http://127.0.0.1:4000/v1` works locally but inside Docker network the host is `http://litellm:4000/v1`. The `llm.py` default should be `http://127.0.0.1:4000/v1` for local dev; the VPS `.env` overrides `LITELLM_BASE_URL=http://litellm:4000/v1`. Document this in `.env.example` comment.
6. **No `WRITES` rule from Hermes to vault** — Phase 3B writes to `vault/Inbox/` directly from Python. Verify this matches the source plan's write discipline (pull-before-write hook). If not, monitor writes should go through a `vault_writer` helper that calls `git-sync.sh` pre/post.

---

## Recommended execution order

1. **Start: First cut (Phase 1 + half of Phase 2 — query synth only)** — ~3 h, single sitting
2. **Then: complete Phase 2** (ingest summarization) — ~1.5 h, same day
3. **Then: Phase 3** in two parallel passes (3A digest then 3B monitor/git-sync/cron) — ~5 h
4. **Then: Phase 6 partial** — add `telos-interview` CLI verb only (~30 min), then run it to seed TELOS docs before Phase 4
5. **Then: Phase 4** (TELOS alignment gate) — ~3 h
6. **In parallel from day 1:** Phase 0 items #1, #3, #4, #5 (user-owned)
7. **When Phase 0 is done AND Phases 1–4 are done:** Phase 5 (live deploy + validate)
8. **Last:** Phase 6 remainder (research worker + LLM lint + missing verbs) — ~4 h

Total: ~22 hours of focused code work + ~4–6 hours of user-owned VPS/Telegram/repo setup.
