# ops

Operational scripts and system configuration for ultra-agents-brain.

## Contents

- `systemd/` — systemd unit files for VPS deployment
- `com.ultraagents.vault-sync.plist` — macOS LaunchAgent for vault sync
- `sync-vault-to-vps.sh` — rsync script to push Obsidian vault to VPS
- `decisions.md` — operational decision log

## Vault Reindex

After deploying Wave 3 (PgVector knowledge layer), seed the vault:

```bash
# On VPS, inside the venv:
python -m agentos.knowledge --reindex
```

This inserts all `vault/**/*.md` files into the `agno_knowledge` Postgres database.
Subsequent vault writes by the curator agent are incremental.
