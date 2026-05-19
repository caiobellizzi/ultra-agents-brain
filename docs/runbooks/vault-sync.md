# Vault Git Sync Runbook

This runbook documents the intended sync discipline for the Markdown vault.
It does not implement deployment scripts.

## Roles

- VPS: authoritative autonomous writer used by Hermes.
- GitHub private repository: transport and backup remote.
- Mac: Obsidian client and occasional human editor.

## Required Human Inputs

- Private GitHub repository URL.
- Auth method for the VPS: deploy key or fine-scoped token.
- Vault path on VPS.
- Vault path on Mac.
- Confirmation that secrets are not stored in the vault.

## VPS First-Time Setup

1. Create or clone the private vault repository on the VPS.
2. Copy the scaffolded `vault/` contents into that repository root if the vault repo is separate from this project.
3. Set Git identity for the Hermes writer.
4. Add the private GitHub remote.
5. Run an initial commit and push after human review.

## Hermes Write Discipline

Every Hermes skill that writes to the vault should follow this sequence:

1. Check working tree status.
2. Pull with rebase from the remote.
3. If conflicts exist, stop writes and notify Telegram.
4. Write files.
5. Append `_system/log.md` and `_system/cost-ledger.md` as needed.
6. Run lightweight vault lint checks.
7. Commit with a scoped message.
8. Push to the remote.

Suggested commit message shape:

```text
vault: ingest <short-topic>
vault: update project briefing <project-slug>
vault: lint report <yyyy-mm-dd>
```

## Auto-Commit Policy

Use a systemd timer or cron only after manual sync is proven.

- Pull before scheduled writes.
- Commit only meaningful changes.
- Push immediately after commit.
- Never auto-resolve merge conflicts.
- Notify Telegram when sync is blocked.

## Conflict Recovery

1. Stop Hermes writes.
2. Pull the latest remote state on the VPS.
3. Inspect conflicted files manually.
4. Preserve both human edits and agent additions where possible.
5. For logs and ledgers, keep both entries and order by timestamp.
6. For note body conflicts, prefer human-authored prose unless the agent has newer cited evidence.
7. Commit the resolved files with `vault: resolve sync conflict`.
8. Push and restart Hermes writes.

## Safety Rules

- Do not store secrets in Git.
- Do not force-push the vault remote during normal operation.
- Do not let multiple autonomous writers push to the same branch.
- Keep append-only files append-only.
- Archive stale material through normal Git history, not by destructive cleanup.

