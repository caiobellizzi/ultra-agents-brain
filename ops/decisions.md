# Operations Decisions

Status: open prerequisites remain.
Date: 2026-05-18.

## Locked Or Assumed Decisions

- Primary runtime target: Hostinger VPS running Ubuntu 24.04 LTS.
- Vault format: Markdown, PARA layout, Git-synced to a private GitHub repository, readable by Obsidian on Mac.
- Secrets policy: secrets stay external to this repository and external to the vault.
- Telegram: bot token must be created through BotFather and stored outside the repo.
- Model gateway: LiteLLM proxy will route providers; provider API keys stay outside the repo.
- Daily model spend cap: USD 20.00, with warning threshold at USD 16.00.
- Hermes release pin: Hermes Agent v0.14.0, tag `v2026.5.16`, released May 16, 2026. This is documented from the parent agent's GitHub release check.

## Unresolved Human Prerequisites

- Confirm Hostinger VPS exists and Caio can SSH into it.
- Confirm target VPS specs meet minimum: Ubuntu 24.04, 2 vCPU, 4 GB RAM.
- Create Telegram bot and store token in the chosen secret manager or VPS environment.
- Confirm Anthropic key exists.
- Confirm at least one fallback provider key exists, preferably Groq.
- Create a private GitHub repository for the vault remote.
- Confirm Tailscale account and target tailnet.
- Decide whether Ollama-on-Mac is in v1 or only a fallback path.
- Decide exact vault remote URL and local paths on VPS and Mac.

## Secret Handling

Never commit real values for:

- Telegram bot token.
- Provider API keys.
- GitHub tokens or deploy keys.
- Tailscale auth keys.
- SSH private keys.
- Obsidian plugin credentials.
- VPS hostnames if Caio considers them sensitive.

Use `.env.example` for variable names only.

