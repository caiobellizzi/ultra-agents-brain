# VPS Foundation Runbook

## Purpose

This runbook prepares a Hostinger Ubuntu 24.04 VPS for the ultra-agents-brain runtime: Docker Compose, LiteLLM, Telegram gateway, Tailscale, logs, and the second-brain vault checkout.

> **Note — Hermes status:** Hermes (the external agent gateway at port 8787) is currently in limbo — mostly eliminated from the runtime path but not fully removed. Env vars and the image pin are retained for compatibility. A decision is needed: finish removal or restore. See `docs/SOURCES.md` § "Hermes gateway".

## First Bootstrap

1. SSH into the VPS as a sudo-capable user.
2. Copy this repository to `/opt/ultra-agents-brain`.
3. Run the bootstrap script:

```bash
sudo /opt/ultra-agents-brain/scripts/vps-bootstrap.sh
```

The script installs Docker, Compose, Tailscale, GitHub CLI, ripgrep, SQLite, curl, jq, and UFW. It creates:

- `/opt/ultra-agents-brain` for deployment files
- `/opt/ultra-agents-brain/hermes` for Hermes config and skills
- `/var/lib/ultra-agents-brain/hermes` for persistent Hermes state
- `/srv/second-brain` for the Git-backed Obsidian vault
- `/var/log/ultra-agents-brain` for service logs

## Tailscale

Run:

```bash
sudo tailscale up
tailscale status
```

Use the tailnet IP for private Ollama access from the VPS to the Mac. Set `OLLAMA_API_BASE` in `.env`, for example:

```bash
OLLAMA_API_BASE=http://100.x.y.z:11434
```

## Environment

Create `/opt/ultra-agents-brain/.env` from `.env.example` and fill secrets on the VPS only:

- `LITELLM_MASTER_KEY`
- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GROQ_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_CHAT_IDS`
- `TELEGRAM_ALERT_CHAT_ID`
- `TELEGRAM_WEBHOOK_SECRET`
- `HERMES_TELEGRAM_WEBHOOK_URL`

Keep `.env` out of source control.

## Services

Copy all systemd units to the system directory and enable them:

```bash
sudo cp /opt/ultra-agents-brain/deploy/systemd/uab-brain.service /etc/systemd/system/
sudo cp /opt/ultra-agents-brain/deploy/systemd/uab-telegram.service /etc/systemd/system/
sudo cp /opt/ultra-agents-brain/deploy/systemd/uab-digest.service /etc/systemd/system/
sudo cp /opt/ultra-agents-brain/deploy/systemd/uab-digest.timer /etc/systemd/system/
sudo cp /opt/ultra-agents-brain/deploy/systemd/uab-monitor.service /etc/systemd/system/
sudo cp /opt/ultra-agents-brain/deploy/systemd/uab-monitor.timer /etc/systemd/system/
sudo cp /opt/ultra-agents-brain/deploy/systemd/uab-review.service /etc/systemd/system/
sudo cp /opt/ultra-agents-brain/deploy/systemd/uab-review.timer /etc/systemd/system/
sudo cp /opt/ultra-agents-brain/deploy/systemd/uab-live-judge.service /etc/systemd/system/
sudo cp /opt/ultra-agents-brain/deploy/systemd/uab-live-judge.timer /etc/systemd/system/
sudo cp /opt/ultra-agents-brain/deploy/cron/ultra-agents-brain.cron /etc/cron.d/ultra-agents-brain
sudo systemctl daemon-reload
sudo systemctl enable --now uab-brain.service
sudo systemctl enable --now uab-telegram.service
sudo systemctl enable --now uab-digest.timer
sudo systemctl enable --now uab-monitor.timer
sudo systemctl enable --now uab-review.timer
sudo systemctl enable --now uab-live-judge.timer
```

Check service state:

```bash
docker compose -f /opt/ultra-agents-brain/deploy/docker-compose.yml ps
/opt/ultra-agents-brain/scripts/health-check.sh
```

## LiteLLM Smoke Test

Run:

```bash
cd /opt/ultra-agents-brain
set -a
. ./.env
set +a
./scripts/smoke-litellm.sh
```

The expected result is an `ok` line for each alias: `orchestrator`, `default-worker`, `cheap-worker`, `private-worker`, and `fallback`.

## Telegram Webhook

> **Note — Hermes in limbo:** The port below (`127.0.0.1:8787`) belongs to the Hermes gateway, which is currently not active in the normal runtime path. The `uab-telegram.service` handles Telegram in its place. See the Hermes note at the top of this file.

```text
127.0.0.1:8787
```

Set `HERMES_TELEGRAM_WEBHOOK_URL` to the public HTTPS webhook URL that maps to `/telegram/webhook`.

## Firewall

The bootstrap allows SSH, HTTP, and HTTPS. LiteLLM and Hermes are bound to `127.0.0.1` in Docker Compose, so they are not directly exposed publicly.

## Acceptance Checklist

- `docker version` works.
- `docker compose version` works.
- `tailscale status` shows the VPS.
- `rg`, `sqlite3`, `git`, `gh`, `jq`, and `curl` are installed.
- `./scripts/smoke-litellm.sh` succeeds.
- `./scripts/health-check.sh` succeeds or reports a concrete missing dependency.
