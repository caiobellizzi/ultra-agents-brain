# STATE — ultra-agents-brain

**Updated:** 2026-05-19
**Milestone:** v1.0
**Current phase:** 01-ultra-brain-agno
**Status:** wave_4_complete_deployed

## Position

- **Phase 01** (`ultra-brain-agno`): in_progress, 1 plan, 0 summaries
- **Plan 01-01** (`Build ultra-brain on Agno`): pending execution
- **Next action:** Run end-to-end verification per PLAN.md `## Verification` table (Telegram round-trip, vault ingest, HITL approve, timer scheduling)

## Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-19 | Brain-first architecture | Workshop needs populated vault to query; building Workshop first ships shallow output for weeks |
| 2026-05-19 | Build on Agno (not 200-LOC native Python) | Agno provides memory/HITL/observability as first-class primitives; native plan would balloon to 800+ LOC in weeks |
| 2026-05-19 | Wrap existing `ultra_brain/*.py` as Agno tools (don't rewrite) | Preserves working code; only `llm.py` gets replaced (by Agno provider) |
| 2026-05-19 | AgentOS = single source of truth; channels = dumb adapters | New channels (Discord etc.) won't require agent code changes |
| 2026-05-19 | Cron timers POST to AgentOS via curl (not Python) | Curator behavior shared across invokers |
| 2026-05-19 | `ultra-workshop` deferred to separate repo, future session | Foundation first; Workshop design should be informed by 2–4 weeks of Brain usage |
| 2026-05-19 | Single-phase, 4-wave roadmap (not 4 separate phases) | Coarse granularity preferred; waves give enough checkpointing |
| 2026-05-19 | Interactive mode (not YOLO) | First-time Agno build — pause between waves for verification |

## Blockers / risks

| Risk | Mitigation |
|------|-----------|
| Agno API surface evolves | Pin exact version in `requirements.txt`; verify against current docs in Wave 1. Note: agno 2.6.7 non-stream PAUSED response uses `requirements[]` not `active_requirements` (property, not serialized). |
| Bot token still exposed from prior session | Rotate via BotFather `/revoke` after Wave 4 (REQ-204) |
| AgentOS endpoint paths in cron services are illustrative | Confirm exact routes during Wave 2 build; update systemd `ExecStart` lines |
| Two systemd services restart together on rsync | `systemctl restart uab-brain && sleep 5 && curl :7000/health` before restarting `uab-telegram` |
| `/srv/second-brain` may be near-empty at first | Expected — curator will have little to digest for first few days |

## History

- 2026-05-19 15:05 UTC: **Wave 4 complete — deployed to VPS** (`root@31.97.130.253:/opt/ultra-agents-brain/`). 8 systemd units installed (`uab-brain`, `uab-telegram`, 3×service+timer for digest/review/monitor). Both services `active (running)`. Health: `{"status":"ok"}`. Timers scheduled: monitor every 4h, digest 20:00 daily, review Sun 18:00. Old `deploy/hermes/` deleted. `ultra-agents-brain.service` removed.

- 2026-05-19 11:40: **Wave 3 HITL smoke green** — Telegram `/ingest https://anthropic.com` -> Approve button -> vault note written at `02-Resources/articles/`. Adapter fix (commit a244fd4): keep `requires_confirmation=True` and echo full ToolExecution dict on /continue; Agno only executes when both flags are True.

- 2026-05-19: Codebase mapped (`.planning/codebase/` — 7 documents, 1,359 lines)
- 2026-05-19: Plan imported from `plans/continue-from-las-session-tender-wand.md` → `01-01-PLAN.md`
- 2026-05-19: PROJECT.md, REQUIREMENTS.md, ROADMAP.md, STATE.md created via `/gsd:new-project`
- 2026-05-19 02:25: **Wave 1 complete** — agno 2.6.7 + litellm 1.85.0 in `.venv`; `scripts/smoke_agno.py` proves Agno → LiteLLM (`:4000`) → LM Studio (`google/gemma-4-e4b`) end-to-end
- 2026-05-19 02:50: **Wave 2 complete** — `agentos/` package (knowledge, tools/{vault,trust_gate}, 5 agents, FastAPI on :7000). Smoke POST /v1/agents/chat returned reply via Agno→LiteLLM→LM Studio. Git repo init; 8 commits.
- 2026-05-19 09:51: **Wave 3 adapter built** — channels/telegram_adapter.py ready. Manual smoke (3.2, 3.3) pending user.
- 2026-05-19 ~11:17: **HITL fix** — replaced broken trust_gate with Agno @tool(requires_confirmation=True); /agents endpoint regression check passed; ingest runs now produce status=PAUSED with requirements[].tool_execution; adapter resumes via /runs/{run_id}/continue. Commit e010792.
- 2026-05-19 03:10: **Dashboard wired** — switched `agentos/app.py` to `agno.os.app.AgentOS`; bound to `127.0.0.1:7001` (macOS AirPlay holds :7000); https://os.agno.com connects, lists 5 agents, chat works. Workaround for Wave 3+: do NOT use `@tool` decorator on tool callables — `agno.os.utils.format_tools` crashes on already-wrapped `Function` instances in 2.6.7. Pass plain Python callables with type hints + docstrings.

## Wave 1 findings (must inform Wave 2)

- **Agno 2.x requires `db=`** on every Agent. Use `from agno.db.sqlite import SqliteDb`. Plan path: one shared SqliteDb at `/var/lib/uab/agno.db` (VPS) or `~/Documents/uab-state/agno.db` (Mac).
- **Extra deps for Task 2.1 `requirements.txt`**: `sqlalchemy`, `aiosqlite` (Agno's SqliteDb depends on them; not pulled in by `agno` core wheel).
- **`deploy/litellm/config.yaml` was broken on LiteLLM 1.85** — `model_info.tier` must be `'free' \| 'paid'` or omitted. Our `tier: A/B/C/D` silently invalidated every deployment. Tier lines removed. `model:` field hardcoded to `openai/google/gemma-4-e4b` (env interpolation only works for `api_base`/`api_key`, not `model`).
- **LiteLLM master_key auth**: with `LITELLM_MASTER_KEY` set, the client `api_key` must match exactly. Wave 2 Agno agents must read `os.environ["LITELLM_MASTER_KEY"]` rather than hardcode.
- **`.env` created** from `.env.example`: `LITELLM_MASTER_KEY=sk-dev-local`, `LM_STUDIO_MODEL=google/gemma-4-e4b`, `LM_STUDIO_FAST_MODEL=google/gemma-4-e4b`. `.env` is git-ignored.
- **Postgres for LiteLLM admin UI**: Docker container `uab-litellm-db` (`postgres:16-alpine`, port 5432, db=`litellm`, password=`litellm`). `DATABASE_URL=postgresql://postgres:litellm@127.0.0.1:5432/litellm` in `.env`. Schema applied via `python -m prisma db push` against the LiteLLM `schema.prisma`. UI login confirmed at http://127.0.0.1:4000/ui (admin / `sk-dev-local`). VPS deployment (Wave 4) will need its own Postgres or a managed DB.
- **Extra dev deps installed** beyond `agno`+`litellm[proxy]`: `sqlalchemy`, `aiosqlite`, `prisma`. Wave 2 `requirements.txt` should pin all of them.
