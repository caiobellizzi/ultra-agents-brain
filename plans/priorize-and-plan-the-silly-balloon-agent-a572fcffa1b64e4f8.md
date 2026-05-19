# Ultra-Agents-Brain: Phased Implementation Plan

## Executive Summary

The codebase is a well-structured scaffold — every module, prompt, and deploy artifact exists — but the system produces zero AI value because no module ever calls an LLM. The plan sequences work in six phases: first wire the LLM client (unblocks everything else), then light up the two highest-value user-facing flows (query answering and daily digest), then close the operational loops (monitor, git-sync, cron), then wire TELOS alignment gates, then harden the research worker and LLM lint pass, and finally expose the missing CLI verbs. Human-gate prerequisites (VPS, Telegram, keys) are parallel to Phases 1–4 and only become blocking at Phase 5 (live deploy).

---

## Phase 1 — LLM Client Foundation (Unblocks Everything)

**What:** Create `ultra_brain/llm.py` — a stdlib-only `urllib.request` wrapper against the LiteLLM proxy at `http://127.0.0.1:4000/v1`. ~25 LOC. Exposes one function: `complete(prompt: str, model: str = "orchestrator", *, system: str | None = None, max_tokens: int = 1024) -> str`.

**Files added/modified:**
- `ultra_brain/llm.py` — NEW. `complete()`, `LLMError` exception, reads `LITELLM_MASTER_KEY` from env.
- `tests/test_core.py` — add `LLMClientTest` using `unittest.mock.patch("urllib.request.urlopen")` to return a canned JSON response. Establishes the mock pattern for all later phases.

**Acceptance criteria:**
- `python -m pytest tests/test_core.py::LLMClientTest` passes with mocked HTTP.
- `python -c "from ultra_brain.llm import complete; print(complete('ping'))"` hits the proxy and returns a string when `LITELLM_MASTER_KEY` is set (manual smoke against live proxy).
- No new external dependencies introduced (`pip show litellm` still fails in the venv).

**Effort:** 2 h

**Dependencies:** None — fully parallel-safe with all human-gate items.

**Verification:** Unit test (mocked), manual smoke against LiteLLM proxy (requires keys, but can be skipped until Phase 5 deploy).

**Risks:** LiteLLM proxy config at `deploy/litellm/config.yaml` may have model-alias drift vs what `complete()` defaults to. Verify the 5 aliases before hardcoding defaults.

---

## Phase 2 — Query Answering + Ingest Summarization (First End-to-End Win)

**What:** Wire LLM into the two seams that produce the most immediate user-visible value: vault query answering and ingest summarization.

**Files modified:**
- `ultra_brain/query.py` — `synthesize_answer()` at line ~72: replace deterministic concat with `llm.complete(prompt, model="orchestrator")` using the `query-synthesis` prompt template from `skills/brain.query/prompts/query-synthesis.md`.
- `ultra_brain/ingest.py` — `Filer.file()` at line ~113 and `ingest_source()` at lines ~210–211: call `llm.complete()` with the `ingestion-summary` prompt; write result as YAML front-matter `summary:` field. Make LLM call conditional on `LITELLM_MASTER_KEY` being set so the path degrades gracefully without keys.
- `tests/test_core.py` — add `QueryLLMTest` and `IngestSummaryTest` with mocked `ultra_brain.llm.complete`.

**Acceptance criteria:**
- `python -m ultra_brain query "what is my TELOS?"` returns a coherent synthesized answer (not a raw dump of matched lines) when proxy is live.
- `python -m ultra_brain ingest <url>` produces a vault note whose YAML front-matter includes a non-empty `summary:` field.
- Both unit tests pass with mocked LLM.
- Ingest path degrades to no summary (existing behavior) when `LITELLM_MASTER_KEY` is absent.

**Effort:** 3 h

**Dependencies:** Phase 1 (`llm.py` must exist).

**Verification:** Unit tests (mocked). Manual: ingest one URL, open the resulting vault note, confirm `summary:` is populated.

**Risks:** Prompt templates reference vault-relative paths — verify `skills/brain.query/prompts/query-synthesis.md` is read correctly at runtime. The `cheap-worker` model alias may be more appropriate than `orchestrator` for summarization (cost tradeoff — flag for implementer decision).

---

## Phase 3 — Daily Digest + Monitor Polling Loop (Operational Value)

**What:** Two parallel tracks, both needed for the system to run unattended.

**Track A — Daily digest with LLM synthesis:**
- `ultra_brain/express.py` — `daily_digest()` lines 11–23: after assembling raw log lines, call `llm.complete()` with the `daily-digest` prompt from `skills/brain.express/prompts/daily-digest.md`. `project_briefing()` lines 26–33: call `llm.complete()` with `project-briefing` prompt instead of returning raw file content.

**Track B — Monitor polling loop:**
- `ultra_brain/monitor.py` — add `run_poll()` function: reads configured feeds, calls existing `fetch_feed()` + dedup logic, adds a new `score_items()` that calls `llm.complete()` with the `monitor` daily-digest prompt for TELOS relevance scoring, writes passing items to vault `Inbox/`. Add a `--once` flag for cron invocation.
- `scripts/git-sync.sh` — NEW. Bash script: `git -C $VAULT_ROOT pull --ff-only && ... && git -C $VAULT_ROOT add -A && git commit -m "auto: sync $(date -u +%Y-%m-%dT%H:%M:%SZ)" && git push`. Referenced in `docs/runbooks/vault-sync.md`.
- `deploy/cron/ultra-agents-brain.cron` — add 4 missing entries: `0 20 * * *` daily digest, `0 18 * * 0` weekly review, `*/240 * * * *` monitor poll, `*/30 * * * *` git-sync.

**Files added/modified:**
- `ultra_brain/express.py` (modified)
- `ultra_brain/monitor.py` (modified — add `run_poll()`, `score_items()`)
- `scripts/git-sync.sh` (NEW)
- `deploy/cron/ultra-agents-brain.cron` (modified — 4 new entries)
- `tests/test_core.py` — add `DigestLLMTest`, `MonitorPollTest`

**Acceptance criteria:**
- `python -m ultra_brain digest` returns a digest string that contains an LLM-synthesized narrative paragraph, not just raw log lines.
- `python -m ultra_brain monitor --once` completes without error and writes at least a stub entry to vault `Inbox/` (even against a test feed).
- `bash scripts/git-sync.sh` runs without error in a repo with a configured remote.
- Cron file has all 7 entries (3 existing + 4 new); `crontab -l` after install shows them.

**Effort:** 5 h (Track A: 2 h, Track B: 3 h)

**Dependencies:** Phase 1. Tracks A and B are independent of each other.

**Risks:** `git-sync.sh` needs `VAULT_ROOT` env var — document in `.env.example`. Monitor's `score_items()` LLM call adds latency per poll; cap with a timeout in `llm.complete()`. Vault GitHub repo must exist (human-gate item #5) for git-sync to push, but the script can run locally without it.

---

## Phase 4 — TELOS Alignment Gate (Trust Integrity)

**What:** Wire `score_alignment()` from `ultra_brain/telos.py` as an automatic pre-check before every `approval_prompt()` call in `ultra_brain/trust.py`. Add the `telos-check` LLM pass using the prompt at `skills/telos.check/prompts/telos-check.md`.

**Files modified:**
- `ultra_brain/trust.py` — at the top of `approval_prompt()`: call `telos.score_alignment(action, vault_root)` and surface the score in the prompt shown to the user. If score < threshold (configurable, default 0.4), prepend a warning banner.
- `ultra_brain/telos.py` — `score_alignment()`: implement the body using `llm.complete()` with the `telos-check` prompt. Currently a stub.
- `tests/test_core.py` — add `TelosGateTest`: verify that a low-alignment action produces a warning banner in the approval prompt output.

**Acceptance criteria:**
- `python -m ultra_brain telos-check "write a viral tweet"` prints an alignment score and reasoning.
- Running any trust-gated action (e.g., `ingest` with a new source) shows the TELOS score before the approval prompt.
- Score < 0.4 prepends visible warning; score >= 0.4 proceeds normally.
- Unit test passes with mocked `llm.complete`.

**Effort:** 3 h

**Dependencies:** Phase 1. Independent of Phases 2–3.

**Risks:** `score_alignment()` is called in the hot path of every trust gate — it adds one LLM round-trip per action. Use `cheap-worker` model alias. Consider caching the score for identical (action, vault-state-hash) pairs if latency is a problem.

---

## Phase 5 — Deploy Hardening + Human Gates (Live System)

**What:** Execute human prerequisite items and finalize deploy artifacts. This is the only phase that is human-gate blocking.

**Human actions required (parallel):**
1. Provision Hostinger VPS, run `scripts/vps-bootstrap.sh`.
2. Create Telegram bot via BotFather, record token.
3. Confirm LLM provider API keys (OpenAI / Anthropic / Groq).
4. Create private GitHub repo for vault, push initial vault.
5. Join Tailscale network (per `ops/decisions.md`).

**Code changes:**
- `deploy/docker-compose.yml` — verify LiteLLM + Hermes service health-checks; add `vault-sync` service using `scripts/git-sync.sh` if not present.
- `deploy/hermes/config.yaml` — confirm Telegram webhook URL matches provisioned bot.
- `.env.example` — document all required vars: `LITELLM_MASTER_KEY`, `TELEGRAM_BOT_TOKEN`, `VAULT_ROOT`, `VAULT_GITHUB_REPO`, `OPENAI_API_KEY` (or equivalent).
- `scripts/smoke-litellm.sh` — extend to test all 5 model aliases end-to-end.

**Acceptance criteria:**
- `docker compose up -d` on VPS brings all services healthy (`docker compose ps` shows all green).
- `bash scripts/smoke-litellm.sh` returns 200 on all 5 aliases.
- Sending `/query what is my TELOS?` to the Telegram bot returns a synthesized answer within 30 s.
- Cron entries installed on VPS (`crontab -l | grep ultra-agents-brain`).

**Effort:** 4 h (code) + human time for provisioning

**Dependencies:** All prior phases complete. All 5 human-gate items complete.

**Risks:** Tailscale routing between Hermes → LiteLLM proxy may require explicit ACL rules. Hostinger firewall must allow Telegram webhook inbound. VPS cold-start of LiteLLM can take 30–60 s; health-check retry logic needed.

---

## Phase 6 — Research Worker + LLM Lint + Missing CLI Verbs (Full Capability)

**What:** Close the remaining three gaps — research with real fetch+summarize, LLM contradiction detection in lint, and the three missing CLI verbs.

**Files modified:**
- `ultra_brain/research.py`:
  - `plan_research()` lines 21–32: call `llm.complete()` with `research-summary` prompt to generate dynamic angles instead of hardcoded 5.
  - `worker_summary()` lines 35–43: `urllib.request.urlopen` to fetch URL, truncate to 8 KB, call `llm.complete()` with the fetched content.
  - `aggregate_research()` lines 61–72: call `llm.complete()` with `research-summary` prompt over all worker summaries to produce synthesis section.
- `ultra_brain/lint.py` — after existing structural passes at line ~41: add `llm_lint_pass()` that calls `llm.complete()` with `lint-report` prompt for contradiction and stale-claims detection. Gated on `--llm` flag so default lint stays fast/deterministic.
- `ultra_brain/__main__.py` — add 3 subcommands: `monitor` (calls `monitor.run_poll()`), `review` (calls `review.weekly_review()`), `telos-interview` (calls `telos.run_interview()`).
- `tests/test_core.py` — add `ResearchWorkerTest`, `LintLLMPassTest`.

**Acceptance criteria:**
- `python -m ultra_brain research "agentic memory systems"` completes and writes a vault Research note with a non-empty `synthesis.md` containing more than 3 bullet points.
- `python -m ultra_brain lint --llm` produces a report section titled "LLM Checks" with at least one contradiction or stale-claims finding (or explicit "none found").
- `python -m ultra_brain monitor`, `python -m ultra_brain review`, `python -m ultra_brain telos-interview` all resolve without `argparse` "unrecognized command" errors.
- All new unit tests pass with mocked LLM.

**Effort:** 5 h

**Dependencies:** Phase 1. Research fetch needs no new deps (stdlib `urllib.request`). `telos-interview` CLI verb needs Phase 4 (`telos.py` body complete).

**Risks:** Research URL fetch has no robots.txt check or rate limiting — add a 1 s sleep between worker fetches as a minimum courtesy. LLM lint pass on large vaults can be expensive; recommend `cheap-worker` model and a 50-note cap per invocation.

---

## Shared Blockers Map

| Blocker | Blocks | Parallel-safe until |
|---|---|---|
| `llm.py` does not exist | Phases 2, 3, 4, 6 | Phase 1 must land first |
| VPS not provisioned | Phase 5 live smoke only | Phases 1–4, 6 are local-only |
| Telegram bot not created | Phase 5 Telegram test | All other phases |
| Provider API keys | Phase 5 live smoke, manual smokes in 2–4 | Mock-based tests in all phases |
| Vault GitHub repo | `git-sync.sh` push path | Local pull/commit still testable |

---

## First Cut Recommendation

**Do Phase 1 + the query half of Phase 2 in a single sitting (approx 3 h total).**

Create `ultra_brain/llm.py` with `complete()` and its mock-based test. Then wire `synthesize_answer()` in `query.py`. The result: `python -m ultra_brain query "what is my TELOS?"` returns a real LLM-synthesized answer for the first time. This is the single highest-signal proof that the architecture works end-to-end and unblocks all subsequent phases. Everything else can be layered on top without re-touching this seam.

