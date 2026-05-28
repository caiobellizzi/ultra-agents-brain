# Plan: Fix Empty Daily Briefs Since May 25

## Context

Daily briefs in `00-Projects/daily-briefs/` have shown "No new Inbox items today." since May 25, 2026. The root cause is a two-part failure on the VPS:

1. **Monitor cron stopped** — The VPS cron runs `monitor` every 4h, but the last log entry in `_system/log.md` is `2026-05-24T16:00:12Z`. No Inbox items were filed May 25, 26, or 28. The 827 May-27 items are from a one-off manual run, not the cron.

2. **`daily-brief` is not in the cron** — The cron only has `digest` (ops log summary) at 20:00, not `daily-brief` (the Inbox→LLM→vault pipeline). The brief only triggers via Telegram `/brief` or manually. So even when monitor runs, the brief file is never auto-generated.

Root cause for the monitor stoppage: `$SECOND_BRAIN_DIR` likely isn't set in the cron environment. Cron strips most env vars; if the crontab doesn't export `SECOND_BRAIN_DIR=/srv/second-brain`, the `--vault "$SECOND_BRAIN_DIR"` argument resolves to `--vault ""` and the monitor quietly fails.

## Fix Plan

### Step 1 — Diagnose cron environment on VPS (SSH)

```bash
ssh root@31.97.130.253
crontab -l -u uabrain          # view current crontab
# Check if SECOND_BRAIN_DIR is declared at top of crontab
```

Expected missing piece: no `SECOND_BRAIN_DIR=...` line at the top of the crontab.

### Step 2 — Fix the crontab

Edit `/var/spool/cron/crontabs/uabrain` (or `crontab -u uabrain -e`) to:

```cron
SECOND_BRAIN_DIR=/srv/second-brain

# Monitor: every 4h
0 */4 * * *  uabrain  python3 -m ultra_brain --vault /srv/second-brain monitor

# Daily brief: 08:00 and 20:00 (morning + evening)
0 8,20 * * *  uabrain  python3 -m ultra_brain --vault /srv/second-brain daily-brief
```

Changes:
- Hardcode the vault path (don't rely on env var interpolation in cron)
- Add `daily-brief` at 08:00 and 20:00 so briefs auto-generate without needing Telegram trigger

### Step 3 — Catchup run on VPS

```bash
# Run monitor to file today's items
python3 -m ultra_brain --vault /srv/second-brain monitor

# Generate today's brief (2-day lookback covers May 27 items)
python3 -m ultra_brain --vault /srv/second-brain daily-brief
```

### Step 4 — Verify and sync to Mac

```bash
# On Mac — sync VPS vault back to local
bash ops/sync-vault-to-vps.sh   # Pass 1 pulls from VPS
```

Check that a new `2026-05-28.md` brief appears in `vault/00-Projects/daily-briefs/` with real content.

### Step 5 — Fix the cron source file in repo

File: `deploy/cron/ultra-agents-brain.cron`

Update from:
```
0 */4 * * *  uabrain  python3 -m ultra_brain --vault "$SECOND_BRAIN_DIR" monitor
0 20  * * *  uabrain  python3 -m ultra_brain --vault "$SECOND_BRAIN_DIR" digest
```

To:
```
# Variables not interpolated in cron — use literal paths
0 */4 * * *   uabrain  python3 -m ultra_brain --vault /srv/second-brain monitor
0 8,20 * * *  uabrain  python3 -m ultra_brain --vault /srv/second-brain daily-brief
```

Commit + redeploy via rsync so the repo and VPS stay in sync.

## Files to modify

- `deploy/cron/ultra-agents-brain.cron` — fix paths, add `daily-brief`

## Verification

1. SSH to VPS, run `python3 -m ultra_brain --vault /srv/second-brain monitor` → check `_system/log.md` shows new entry dated today
2. Run `python3 -m ultra_brain --vault /srv/second-brain daily-brief` → check `00-Projects/daily-briefs/2026-05-28.md` has real content
3. Sync to Mac → open Obsidian → confirm today's brief is populated
4. Wait for the next cron window (or set a test cron 2 min out) and verify it fires automatically
