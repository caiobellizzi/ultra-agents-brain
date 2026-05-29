# MAINTENANCE

Operator guide for keeping the second brain running. Organized by **cadence**, not by skill. For source-by-source detail see [SOURCES.md](./SOURCES.md). For "what to add next" see [CONNECTIONS-ROADMAP.md](./CONNECTIONS-ROADMAP.md).

The CLI is `python -m ultra_brain --vault <path> <command>`. On the VPS, `$SECOND_BRAIN_DIR` is `/srv/second-brain`. Locally, `--vault vault` resolves through the symlink to `~/Documents/second-brain`.

---

## At a glance

| Flow | Cadence | Surface | Writes to | Skill / module |
|------|---------|---------|-----------|----------------|
| Health check | every 15 min | VPS cron | Telegram on failure | `scripts/health-check.sh` |
| Cost rollup | daily 08:05 | VPS cron | stdout / Telegram | `scripts/cost-check.sh` |
| RSS poll | every 4 h | VPS cron | `vault/_inbox/` | `worker.monitor` |
| Daily brief | daily 20:00 | VPS cron + manual | `vault/Projects/_briefing.md`, Telegram | `brain.express` |
| Vault lint | daily 02:00 | VPS cron | `vault/_system/lint-report.md` | `brain.lint` |
| Weekly review | Sun 18:00 | VPS cron | `vault/_system/weekly-review.md` | `brain.review` |
| Weekly lint sweep | Mon 07:15 | VPS cron | stdout | `scripts/lint-check.sh` |
| Vault sync | every 5 min | macOS LaunchAgent | local ↔ VPS rsync | `ops/sync-vault-to-vps.sh` |
| Inbox refinement | on demand | manual / Claude | promotes `_inbox/` → PARA | `brain.ingest` |
| Vault search | on demand | manual / Telegram | stdout | `brain.query` + `qmd` |
| Bluesky poll | on demand | manual | `vault/_inbox/` | `bluesky` subcommand |
| Research run | on demand | manual | `vault/Projects/Research/<topic>/` | `worker.research` |
| Telos check | on demand | manual | stdout | `telos.check` |
| Live judging | every 2 min (VPS timer) | VPS systemd | `vault/_system/experiences/` + `ai.agno_eval_runs` | `agentos/live_judge.py` |

---

## Daily flows

### `brain.express` — daily brief (20:00 VPS)

Synthesizes the day's inbox + briefing notes into a digest and sends it to Telegram.

```bash
# Manual run on VPS
python3 -m ultra_brain --vault "$SECOND_BRAIN_DIR" daily-brief

# Local dry-run (no Telegram)
python -m ultra_brain --vault vault daily-brief --no-telegram

# Specific date
python -m ultra_brain --vault vault daily-brief --date 2026-05-22
```

**Writes:** `vault/Projects/_briefing.md`, appends to `vault/_system/log.md`, Telegram message to `TELEGRAM_ALLOWED_CHAT_IDS`.

**Verify:** check the timestamp in `_briefing.md`; check the bot delivered (search Telegram chat).

**Failure recovery:**
- *No Telegram delivery* — verify `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_CHAT_IDS` set on the VPS; run with `--no-telegram` to confirm synthesis works.
- *LLM 400 on tools+response_format* — the LiteLLM `strip_response_format` pre-call hook should catch this; if regressed see [runbooks/recovery.md](./runbooks/recovery.md).
- *Brief missed monitor-filed items* — date mismatch between filer timestamp and brief window. Re-run with explicit `--date`.

### `worker.monitor` — RSS poll (every 4 h VPS)

```bash
# Default (uses skills/worker.monitor/feeds.txt)
python -m ultra_brain --vault vault monitor

# Score items (LLM-rated relevance)
python -m ultra_brain --vault vault monitor --score
```

**Writes:** new items to `vault/_inbox/`, dedup state to `vault/_system/monitor-seen.json` (excluded from sync).

**Verify:** `ls vault/_inbox/` for new entries; tail `vault/_system/log.md`.

**Failure recovery:** if a feed URL 404s, the poll skips it — check `_system/log.md` for the error line and either fix the URL in `skills/worker.monitor/feeds.yaml` (canonical) and `feeds.txt` (CLI default) or remove it.

### Vault sync — local ↔ VPS (every 5 min macOS)

Bidirectional rsync. **Pull first** (VPS → Mac) so VPS-generated inbox items survive, then push with `--delete` (Mac → VPS).

```bash
# Manual run
bash ops/sync-vault-to-vps.sh

# Inspect last run
tail /tmp/uab-vault-sync.log /tmp/uab-vault-sync.err

# Reload LaunchAgent after editing the plist
launchctl unload ~/Library/LaunchAgents/com.ultraagents.vault-sync.plist
launchctl load   ~/Library/LaunchAgents/com.ultraagents.vault-sync.plist
```

**Excludes:** `.obsidian/`, `.trash/`, `_system/log.md`, `_system/lint-report.md`, `_system/{monitor,brief,bluesky}-seen.json`. These stay machine-local.

**Failure recovery:** see [runbooks/vault-sync.md](./runbooks/vault-sync.md). Most common cause: macOS Full Disk Access not granted to `/bin/bash`.

---

## On-demand flows

### `brain.ingest` — promote inbox to PARA

The human-in-the-loop refinement step. Claude (or you) reads `_inbox/` items, extracts entities/concepts, and files them under Projects/Areas/Resources.

```bash
# Single source
python -m ultra_brain --vault vault ingest <path-or-url> --via manual --cost 0.0 --model none

# Via Claude — invoke the brain.ingest skill from Claude Code
```

**Writes:** new note under `vault/Projects|Areas|Resources/...`, appends to `_system/cost-ledger.md`.

### `brain.query` — search the vault

Backed by `qmd` (local BM25 + vector). The `qmd` MCP serves the same index.

```bash
python -m ultra_brain --vault vault query "your question" --limit 8
```

**Maintenance:** when `qmd update` reports pending vectors, run `qmd embed` to refresh embeddings. See [qmd re-embed](#qmd-re-embed-cycle) below.

### `worker.research` — multi-worker research run

```bash
# Plan workers (prints task list)
python -m ultra_brain --vault vault research-plan "topic" --workers 5

# Aggregate worker outputs into a Research project
python -m ultra_brain --vault vault research-aggregate "topic" worker1.md worker2.md ...
```

**Writes:** `vault/Projects/Research/<topic>/`.

### `bluesky` — poll handles

```bash
python -m ultra_brain --vault vault bluesky --limit 10
```

Reads `skills/worker.monitor/bluesky-handles.txt` (one handle per line). **Not** in the VPS cron yet — see [CONNECTIONS-ROADMAP.md](./CONNECTIONS-ROADMAP.md).

### `telos.check` — goal alignment

```bash
python -m ultra_brain --vault vault telos-check "the action I'm considering"
```

Returns a 0–1 alignment score against the telos doc in `vault/_system/`.

### `telos.interview` — capture or update goals

```bash
# Start a session
python -m ultra_brain --vault vault telos-interview

# Answer the next question
python -m ultra_brain --vault vault telos-interview --session 3 --answer "..."
```

**Writes:** `vault/_system/telos-sessions.json`.

### AgentOS eval rows and live judging

The AgentOS eval surface uses three row shapes:

| Row | `eval_type` | Meaning |
|-----|-------------|---------|
| Live parent | `performance` | One metadata-only row for an agent/team run. Name is `live:<agent_id>`, score is `null`, and latency/model/status live in `eval_data`. |
| Suite case | `accuracy` | One scored row per eval-suite case. Run id is deterministic: `suite:<agent_id>:<case_id>:<git_identity>`. |
| Live judge child | `agent_as_judge` | Optional async judgment for a live parent row. Child rows link back through `eval_data.parent_run_id`. |

Live judging is disabled by default and never runs on the user-facing response path. Enable only when you are comfortable sending sampled run payloads to the configured judge tier:

```bash
EVAL_LIVE_JUDGE_ENABLED=true          # default false
EVAL_LIVE_SAMPLE_RATE=0.05            # default 0.0
EVAL_LIVE_SAMPLE_RATE_CHAT=0.10       # optional per-agent override
EVAL_LIVE_MAX_ATTEMPTS=3              # default 3
EVAL_LIVE_ALLOW_CONTENT_READ=false    # default false; ingest full-content judging requires true
EVAL_LIVE_MAX_PAYLOAD_CHARS=12000     # default 12000
```

Worker commands:

```bash
python -m agentos live-judge --once
python -m agentos live-judge --once --limit 10
python -m agentos live-judge --loop --interval 60 --limit 10
```

Privacy gate behavior:

- Rows with private-key, token, password, secret, authorization, or oversized payload markers are skipped before any judge call.
- Ingest full-content judging requires `EVAL_LIVE_ALLOW_CONTENT_READ=true`; otherwise only metadata is eligible.
- Worker failures increment parent `judge_attempts` and retry only up to `EVAL_LIVE_MAX_ATTEMPTS`.
- Historical `Untitled Evaluation` rows are not migrated, mutated, or deleted in this pass. Only new rows use the corrected semantics.

---

## Weekly flows

### `brain.review` — strategic review (Sun 18:00 VPS)

```bash
python3 -m ultra_brain --vault "$SECOND_BRAIN_DIR" review
```

**Writes:** `vault/_system/weekly-review.md`.

### Weekly lint sweep (Mon 07:15 VPS)

`scripts/lint-check.sh` — repo-side hygiene (separate from `brain.lint`, which is vault hygiene).

### `qmd` re-embed cycle

When you've added many new notes:

```bash
qmd update          # detect changes
qmd embed           # regenerate missing vectors
qmd status          # confirm 0 pending
```

The MCP server picks up new vectors automatically on next query.

---

## Monthly / quarterly

- **LiteLLM key rotation** — update keys in `.env` on VPS, restart container: `docker compose -f deploy/docker-compose.yml restart litellm`. Verify with `bash scripts/smoke-litellm.sh`.
- **Cost ledger review** — `cat vault/_system/cost-ledger.md` or run `python -m ultra_brain --vault vault cost-summary`. Hard cap is `DAILY_COST_CAP_USD` in `.env`.
- **Eval review** — query `ai.agno_eval_runs` in Postgres for recent eval rows; also check `vault/_system/experiences/` for accumulated learning notes written by the live judge.
- **Feed curation** — prune dead URLs from `skills/worker.monitor/feeds.yaml` and `feeds.txt`; refresh `bluesky-handles.txt`.

---

## Incident response

Use these when something's already broken:

- [runbooks/recovery.md](./runbooks/recovery.md) — general post-failure restore
- [runbooks/vault-sync.md](./runbooks/vault-sync.md) — rsync / launchd / dirty-vault issues
- [runbooks/obsidian.md](./runbooks/obsidian.md) — MCP vault access problems
- [runbooks/vps-foundation.md](./runbooks/vps-foundation.md) — VPS bootstrap and recovery

Quick triage commands:

```bash
bash scripts/health-check.sh                 # full health probe
bash scripts/smoke-litellm.sh                # LiteLLM round-trip
python scripts/smoke_agno.py                 # Agno framework smoke
docker compose -f deploy/docker-compose.yml ps   # container status
systemctl status uab-brain uab-telegram uab-digest.timer uab-monitor.timer uab-review.timer uab-live-judge.timer   # VPS services
```

---

## Adding a new …

### …RSS feed

1. Add URL to `skills/worker.monitor/feeds.txt` (CLI default) **and** `feeds.yaml` (canonical, includes metadata).
2. Run `python -m ultra_brain --vault vault monitor` locally to verify the feed parses.
3. Commit. VPS picks it up on next vault sync (5 min) → next cron poll (≤4 h).

### …Bluesky handle

1. Append `did:plc:...` or `handle.bsky.social` to `skills/worker.monitor/bluesky-handles.txt`.
2. `python -m ultra_brain --vault vault bluesky --limit 5` to verify.
3. Commit.

### …skill

1. Create `skills/<namespace>.<name>/SKILL.md` + any helpers (mirror `skills/brain.express/` shape).
2. Add the CLI subcommand to `ultra_brain/__main__.py` if it has a non-Claude invocation path.
3. Document its flow in this file under the right cadence section.

### …LLM endpoint

1. Add the model entry to `deploy/litellm/config.yaml`. If it's a slashed model ID (`org/model`), confirm the LiteLLM pinned tag in `.env` preserves the `nvidia_nim/` prefix.
2. Optionally point a tier alias at it via `LITELLM_*_MODEL` env vars.
3. Restart container, run `bash scripts/smoke-litellm.sh`.

### …agent

1. Add to `agentos/agents/`, give it an explicit `id=` (memory 21841–21846).
2. Decide auto-memory extraction: keep on for interactive agents, off for background agents (curator/ingest pattern).
3. Decide `enable_agentic_culture`: set `True` for interactive agents (chat, query, research) — all current interactive agents have it enabled. Background/worker agents do not need it.
4. Wire into `agentos/app.py` and verify with `python scripts/smoke_agno.py`.

---

## Verification checklist (end of any maintenance session)

- [ ] `bash scripts/health-check.sh` → "health check OK"
- [ ] `python -m ultra_brain --vault vault cost-summary` → today under cap
- [ ] `tail vault/_system/log.md` → no error lines since last clean run
- [ ] `git -C vault status` → clean (or `ALLOW_DIRTY_VAULT=1` if intentional)
- [ ] Last `/tmp/uab-vault-sync.log` entry within the last 5 min
