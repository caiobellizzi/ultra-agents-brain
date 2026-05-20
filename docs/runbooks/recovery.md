# Recovery Runbook

## Restore From VPS Snapshot

1. Restore the Hostinger VPS snapshot.
2. SSH into the restored VPS.
3. Confirm base services:

```bash
sudo systemctl status docker tailscaled
docker compose -f /opt/ultra-agents-brain/deploy/docker-compose.yml ps
```

4. Rejoin Tailscale if the node identity changed:

```bash
sudo tailscale up
```

5. Restart the stack:

```bash
sudo systemctl restart uab-brain.service
```

6. Run:

```bash
/opt/ultra-agents-brain/scripts/health-check.sh
```

## Restore Vault From GitHub Remote

If `/srv/second-brain` is missing or corrupt:

```bash
sudo systemctl stop uab-brain.service
sudo mv /srv/second-brain /srv/second-brain.broken.$(date -u +%Y%m%dT%H%M%SZ)
sudo git clone <private-vault-github-url> /srv/second-brain
sudo chown -R uabrain:uabrain /srv/second-brain
sudo systemctl start uab-brain.service
```

Then run:

```bash
/opt/ultra-agents-brain/scripts/health-check.sh
```

## Restore Hermes State

Hermes state lives under `/var/lib/ultra-agents-brain/hermes`. If restoring from snapshot is not possible, recreate the directory and let Hermes rebuild session state:

```bash
sudo mkdir -p /var/lib/ultra-agents-brain/hermes
sudo chown -R uabrain:uabrain /var/lib/ultra-agents-brain/hermes
sudo systemctl restart uab-brain.service
```

The second brain remains the source of durable knowledge. SQLite session loss should not delete vault content.

## API Key Rotation

1. Generate the replacement key at the provider.
2. SSH into the VPS.
3. Edit `/opt/ultra-agents-brain/.env`.
4. Replace the relevant value:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY`
- `LITELLM_MASTER_KEY`
- `TELEGRAM_BOT_TOKEN`

5. Restart services:

```bash
sudo systemctl restart uab-brain.service
```

6. Validate:

```bash
cd /opt/ultra-agents-brain
set -a
. ./.env
set +a
./scripts/smoke-litellm.sh
./scripts/health-check.sh
```

7. Revoke the old key after validation.

If rotating `LITELLM_MASTER_KEY`, update every client that calls LiteLLM, including Hermes and local smoke scripts.

## Hermes Upgrade Process

Current pinned tag: `ghcr.io/nousresearch/hermes-agent:v2026.5.16`.

1. Read the Hermes release notes for config and gateway changes.
2. Update `HERMES_IMAGE` in `/opt/ultra-agents-brain/.env` to the candidate tag.
3. Pull and restart:

```bash
cd /opt/ultra-agents-brain/deploy
docker compose pull hermes
sudo systemctl restart uab-brain.service
```

4. Validate:

```bash
/opt/ultra-agents-brain/scripts/health-check.sh
```

5. Send a Telegram `hi` message and confirm a direct response.
6. Confirm Hermes sees `/hermes-config/skills` and preserves `/var/lib/hermes`.
7. If validation fails, roll back `HERMES_IMAGE` to `ghcr.io/nousresearch/hermes-agent:v2026.5.16` and restart the service.

## Cost and Lint Operations

Daily cost rollup:

```bash
/opt/ultra-agents-brain/scripts/cost-check.sh
```

Weekly lint wrapper:

```bash
/opt/ultra-agents-brain/scripts/lint-check.sh
```

Both scripts send Telegram alerts when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALERT_CHAT_ID` are set.
