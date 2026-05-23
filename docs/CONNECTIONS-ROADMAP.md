# CONNECTIONS ROADMAP

What to add next to improve the second brain, ranked by **effort × value**. Cross-references [SOURCES.md](./SOURCES.md) (current state) and [MAINTENANCE.md](./MAINTENANCE.md) (operator surface). Each item lists the gap, the win, and the work.

---

## 1. Activate what's already configured (hours, not days)

These are zero-design tasks — keys and login flows that have been sitting waiting.

### 1.1 NotebookLM login
- **Gap:** MCP installed (`~/.local/bin/notebooklm-mcp`), registered in `~/.claude.json`, but never authenticated.
- **Win:** Tier-1 in the knowledge hierarchy. Curated notebooks become queryable from any Claude session — biggest hallucination reduction available.
- **Work:** `nlm login` (interactive browser), then `claude mcp list | grep notebooklm` should show it healthy. ~10 min.

### 1.2 Perplexity API key
- **Gap:** `PERPLEXITY_API_KEY` missing from `.env` (memory 21772). MCP `@perplexity-ai/mcp-server` is registered globally and waiting.
- **Win:** Tier-4 fresh-web search without leaving the agent loop. Replaces ad-hoc `WebSearch` for time-sensitive queries.
- **Work:** Add the key, restart Claude session. ~5 min + cost of a Perplexity plan.

### 1.3 VPS API key audit
- **Gap:** Memory 21770 flagged `ANTHROPIC_API_KEY` and `GROQ_API_KEY` empty on the VPS, which silently broke fallback routing.
- **Win:** Restores the full LiteLLM tier chain.
- **Work:** `ssh root@31.97.130.253 'grep -E "^(ANTHROPIC|GROQ|OPENAI|OPENROUTER)_API_KEY=" /opt/ultra-agents-brain/.env'`. Backfill anything empty; restart the LiteLLM container.

### 1.4 Bluesky in cron
- **Gap:** `bluesky` CLI works but isn't scheduled. Today it requires a manual `python -m ultra_brain --vault vault bluesky` run.
- **Win:** Bluesky feeds get the same passive ingestion as RSS.
- **Work:** One line in `deploy/cron/ultra-agents-brain.cron`. ~5 min.

```cron
30 */4 * * * uabrain python3 -m ultra_brain --vault "$SECOND_BRAIN_DIR" bluesky --limit 10
```

(Offset by 30 min from the RSS poll to avoid synchronized load.)

---

## 2. High-value gaps with low effort (a day)

### 2.1 Unify `feeds.yaml` and `feeds.txt`
- **Gap:** Two source-of-truth files for the RSS list. `feeds.yaml` has 126 entries with metadata; `feeds.txt` has 27 (CLI default). Maintainers have to update both.
- **Win:** Single canonical list; CLI reads `feeds.yaml`.
- **Work:** Add `--feeds-yaml` flag to the `monitor` subcommand and switch the default. Migrate `feeds.txt` consumers; delete `feeds.txt`. Update the cron entry.

### 2.2 Brief reads filed monitor items by date, not by inbox state
- **Gap:** Memory 21808 captured an incident where the daily brief missed monitor-filed items because the date match window was off.
- **Win:** Brief reliably picks up everything monitor filed in the brief window.
- **Work:** Change the brief's source query to "items with `filed_at` in [yesterday 20:00, today 20:00)" rather than "items still in `_inbox/`". ~half a day including a regression test.

### 2.3 Auto-`qmd embed` after `/refine`
- **Gap:** When the refine pipeline updates an article, `qmd update` reports the change but vectors aren't regenerated until someone runs `qmd embed` manually. The MCP serves a stale vector until then.
- **Win:** Search reflects fresh content within minutes of refinement.
- **Work:** Add a post-batch hook in `/refine` (or a launchd timer) that runs `qmd embed` after each refine session.

### 2.4 Decide Hermes: finish removal or restore
- **Gap:** Hermes is "nearly eliminated" (memory 20353) but `.env` still has 6 Hermes vars and `scripts/health-check.sh` still probes its `/health`. The probe will alarm if no one's listening.
- **Win:** Clean health check, simpler `.env`.
- **Work:** Either rip the remaining vars + the `check_url Hermes` line + the `check_docker_service hermes` line out of `scripts/health-check.sh`, or restore the container in `docker-compose.yml`. Currently the health check warns on every run.

---

## 3. Medium-effort additions (a few days)

### 3.1 Telegram capture → `_inbox/` round-trip
- **Gap:** Telegram inbound exists, but the path "forward a message in Telegram → it lands as a vault inbox item with source URL preserved" isn't documented or end-to-end tested. The capture flow is the most natural mobile-first ingest.
- **Win:** Phone becomes a first-class inbox.
- **Work:** Smoke-test the existing `channels/telegram_adapter.py` flow; document in `MAINTENANCE.md`; add a Telegram-source dedup file analogous to `monitor-seen.json`.

### 3.2 AgentOS UI wiring — evaluations, memory, knowledge, approvals
- **Gap:** Memory S603 diagnosed missing surfaces in the os.agno.com UI. The agents are instrumented (`eval_recorder`, `instrumented_memory`, `instrumented_knowledge`) but the UI doesn't render the data.
- **Win:** Observability becomes visual, not just structured logs.
- **Work:** Per S603 diagnosis — wire the existing recorder outputs into AgentOS's expected schemas.

### 3.3 Reproducible `_inbox/` refinement workflow
- **Gap:** "Refinement" today is whoever-is-driving + Claude reading inbox notes. The distill_layer-2 pattern (S597, S598) exists for the external second-brain vault but isn't tied to `brain.ingest`.
- **Win:** Inbox refinement is a documented skill with per-article approval, not an ad-hoc Claude prompt.
- **Work:** Port the `/refine` skill pattern into `skills/brain.ingest/` as a structured sub-command; require human approval per item.

### 3.4 Inbox volume guardrail
- **Gap:** No alert when `_inbox/` grows unbounded. RSS at 4 h × ~30 items can overwhelm if refinement lapses.
- **Win:** Early warning that the second-brain pipeline is backed up.
- **Work:** Add a check to `scripts/health-check.sh`: `find _inbox -name '*.md' | wc -l` > threshold → Telegram alert.

---

## 4. Defer / skip — with reasoning

| Item | Status | Why |
|------|--------|-----|
| X / Twitter ingestion | ⛔ | Per S604: no clean public-post API; cost/upkeep > value |
| LinkedIn ingestion | ⛔ | Same reasoning; harder anti-scraping |
| TTS-on by default in daily brief | 🟡 | Medium-trust (paid provider). Keep behind explicit flag |
| Full custom MCP for second-brain | ⏸ | Obsidian MCP + qmd MCP cover read/search; a custom MCP duplicates without adding |

---

## 5. Observability — what's missing after InstrumentedKnowledge

Recent commits (`13-02` series, ending 26703b6) shipped read-path observability for Knowledge. Gaps remaining for full coverage:

- **Write-path Knowledge instrumentation** — InstrumentedKnowledge wraps reads; writes still go through raw Agno paths.
- **Memory extraction events** — `InstrumentedMemoryManager` (memory 21850, 21851) logs decisions but doesn't surface them in the AgentOS UI (see 3.2).
- **Cross-agent eval correlation** — `eval_recorder` writes per-agent rows; nothing joins them into a "supervisor team turn" view.
- **Cost ledger per skill, not just per call** — `cost-ledger.md` is an append log. A weekly rollup by skill (not by call) would make over-spending obvious.

These are the natural next-pass items for the EVAL/OBS workstream.
