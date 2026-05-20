# Roadmap — ultra-agents-brain

**Milestone:** v1.0 — Knowledge Layer on Agno
**Granularity:** Coarse (single phase, four waves)
**Created:** 2026-05-19

## Milestone v1.0

A Telegram-accessible AgentOS that wraps the existing `ultra_brain` package as Agno tools, runs autonomously on the Hostinger VPS, and serves as the foundational knowledge layer for future agent teams.

### Phase 01: ultra-brain-agno

**Status:** in_progress
**Goal:** Ship `ultra-brain` to production VPS — AgentOS + Telegram adapter + 3 systemd timers running, all verification matrix rows green.

**Requirements covered:** REQ-001 through REQ-013, REQ-100 through REQ-106, REQ-200 through REQ-204

**Plan:** `01-01-PLAN.md` (4 waves, imported from `plans/continue-from-las-session-tender-wand.md`)

**Waves:**
- **Wave 1** — Read Agno docs + LiteLLM smoke test (`scripts/smoke_agno.py` returns a reply via gemma-4-e4b)
- **Wave 2** — Local scaffolding (`agentos/` package: knowledge.py, tools/, 5 agents, app.py)
- **Wave 3** — Telegram adapter + local end-to-end ("hi" reply, ingest+approve, vault query)
- **Wave 4** — VPS deployment (rsync, systemd enable, cleanup hermes, end-to-end verification)

**UI hint:** No (server-side service + Telegram inline buttons only)

**Dependencies:** None (first phase of v1.0)

**Done when:**
- `systemctl status uab-brain uab-telegram` → both `active (running)`
- All 10 rows in the verification matrix pass
- Bot token rotated (REQ-204)
- `journalctl -u uab-brain --since "1h ago"` shows no errors

---

## Future milestones (preview, NOT in v1.0 scope)

### v2.0 — Channels

Add Discord and WhatsApp adapters using the `channels/` pattern. Webhook mode for Telegram (optional).

### v3.0 — ultra-workshop

Separate repo. Agno orchestrator + OpenHands coder sandbox. Reads from Brain via HTTP. Begins only after v1.0 has been running daily for 2–4 weeks.
