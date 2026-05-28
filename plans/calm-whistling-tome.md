# Plan: Auto-sync second-brain → VPS + pgvector reindex

## Context

Phase 17 built a pipeline where `second-brain/aggregate.yml` commits nightly `repos/<name>.md`
prose summaries to the `second-brain` repo. The Telegram `/query` agent searches pgvector, so
those files are only answerable once they (a) land on the VPS and (b) are embedded into pgvector.

During Phase 17 smoke testing, both steps had to be done **by hand** (scp the file, then
`python -m agentos.knowledge --reindex`). This plan automates both so any push to `second-brain`
flows to the VPS and into pgvector with no manual intervention.

Two facts discovered during investigation reshaped the design:

1. **Deploy-to-VPS is already 90% built.** A `uabrain` cron runs every 5 min:
   `git-sync.sh push "<msg>" && git-sync.sh pull`. `git-sync.sh pull` already fast-forward-merges
   `origin/main` into `/srv/second-brain`. So `repos/*.md` already reaches the VPS within 5 min —
   the only missing step is the reindex after the merge.

2. **`second-brain` was just made private**, which **broke** the auto-pull: the VPS remote is
   anonymous HTTPS, and a private repo returns `could not read Username`. The 5-min cron is now
   failing on every run (both push and pull). Restoring auth is a prerequisite, not optional.

Decisions (locked via grilling):
- Reindex trigger: **pull-based**, implemented by extending the version-controlled `git-sync.sh`
  plus a new `scripts/reindex-vault.sh` helper (not a raw `.git/hooks/post-merge`).
- VPS auth: **SSH deploy key, write-enabled** (keeps the existing push half of the cron working so
  VPS-generated vault content still propagates to GitHub).

## Part A — Restore VPS↔GitHub auth (SSH deploy key, write-enabled)

Prerequisite. Until this is done the 5-min cron fails and nothing syncs.

1. Generate an ed25519 keypair on the VPS owned by `uabrain`:
   `sudo -u uabrain ssh-keygen -t ed25519 -f /home/uabrain/.ssh/second_brain_deploy -N ""`
   (confirm `uabrain`'s home dir first; create `~/.ssh` with `700` if missing).
2. Configure `uabrain`'s SSH to use that key for github.com — append to `/home/uabrain/.ssh/config`:
   ```
   Host github.com
     IdentityFile ~/.ssh/second_brain_deploy
     IdentitiesOnly yes
   ```
   chmod `600` the config; add github.com to `known_hosts`
   (`ssh-keyscan github.com >> /home/uabrain/.ssh/known_hosts`).
3. Register the **public** key as a write-enabled deploy key (do from this session via gh):
   `gh repo deploy-key add <pubkey> --repo caiobellizzi/second-brain --title vps-uabrain --allow-write`
4. Switch the VPS remote from HTTPS back to SSH:
   `git -C /srv/second-brain remote set-url origin git@github.com:caiobellizzi/second-brain.git`
5. Verify both directions as `uabrain`:
   `sudo -u uabrain git -C /srv/second-brain fetch origin main` (pull auth) and a no-op
   `git-sync.sh push` cycle (push auth).

## Part B — Reindex helper script (new, version-controlled)

New file: `scripts/reindex-vault.sh`. Responsibilities:
- `flock -n` guard on `/tmp/uab-reindex.lock` so overlapping 5-min cron runs can't double-reindex
  (the reindex walk takes ~50s; skip if one is already running).
- Source `/opt/ultra-agents-brain/.env` (provides `POSTGRES_DSN_KNOWLEDGE`, without which reindex
  silently no-ops — confirmed during investigation).
- Run `"$APP_DIR/.venv/bin/python" -m agentos.knowledge --reindex` (the venv python has
  `sentence-transformers`; system python3 does not).
- Log to a `uabrain`-writable path (e.g. `/opt/ultra-agents-brain/logs/reindex.log`, created with
  `uabrain` ownership during deploy).
- **Always exit 0** — a reindex failure must never break the git-sync cron.

Reuses the existing idempotent reindex in `agentos/knowledge.py` (`cli_main` → `reindex()`), which
sha256-skips unchanged files, so re-running is cheap for already-embedded content.

## Part C — Trigger reindex from git-sync.sh pull

Edit `scripts/git-sync.sh`, `pull)` branch only. Capture HEAD before and after the
fast-forward merge; if the merge advanced HEAD **and** any changed path ends in `.md`, invoke the
helper:

```bash
pull)
  git fetch "$REMOTE" "$BRANCH" --quiet
  BEFORE=$(git rev-parse HEAD)
  git merge --ff-only "$REMOTE/$BRANCH" --quiet || {
    echo "git-sync: fast-forward failed; manual merge required" >&2
    exit 1
  }
  AFTER=$(git rev-parse HEAD)
  if [ "$BEFORE" != "$AFTER" ] && git diff --name-only "$BEFORE" "$AFTER" | grep -q '\.md$'; then
    "$(dirname "$0")/reindex-vault.sh" || true
  fi
  ;;
```

`set -euo pipefail` stays satisfied: the `grep -q` lives in an `if` condition, and the helper call
is `|| true`-guarded. Reindex only fires when a pull actually brought new/changed markdown, so
Inbox-only or no-op pulls stay fast.

The `push)` branch is unchanged — it keeps propagating VPS-side vault changes upward (the
write-enabled deploy key from Part A keeps it working).

## Part D — Deploy to VPS

`/opt/ultra-agents-brain` is **not** a git checkout (code ships by file copy), so deploy the two
scripts directly:
- `scp scripts/git-sync.sh root@31.97.130.253:/opt/ultra-agents-brain/scripts/git-sync.sh`
- `scp scripts/reindex-vault.sh root@31.97.130.253:/opt/ultra-agents-brain/scripts/reindex-vault.sh`
- `ssh ... "chmod +x /opt/ultra-agents-brain/scripts/reindex-vault.sh; mkdir -p /opt/ultra-agents-brain/logs && chown uabrain /opt/ultra-agents-brain/logs"`

No service restart needed — the cron picks up the new scripts on its next 5-min tick.

## Critical files

| File | Change |
|------|--------|
| `scripts/reindex-vault.sh` | **new** — flock-guarded reindex wrapper |
| `scripts/git-sync.sh` | edit `pull)` branch to trigger reindex on `.md` change |
| VPS `/home/uabrain/.ssh/{second_brain_deploy,config,known_hosts}` | new SSH deploy key + config |
| VPS `/srv/second-brain` git remote | HTTPS → SSH |
| GitHub `caiobellizzi/second-brain` deploy keys | add write-enabled `vps-uabrain` key |

## Verification (end-to-end)

1. **Auth restored:** `sudo -u uabrain git -C /srv/second-brain fetch origin main` succeeds (no
   `could not read Username`); a `git-sync.sh push` no-op cycle succeeds.
2. **Reindex fires on .md change:** append a sentinel line to a `repos/*.md` on GitHub (or re-run
   `aggregate.yml`), then run `sudo -u uabrain /opt/ultra-agents-brain/scripts/git-sync.sh pull`.
   Confirm `logs/reindex.log` shows a fresh `OBS-01 knowledge write ... action: indexed` line for
   the changed file.
3. **No reindex on no-op:** run `git-sync.sh pull` again with nothing new; confirm the helper is
   not invoked (HEAD unchanged) and no new log entry appears.
4. **Concurrency guard:** while a reindex is running, a second `reindex-vault.sh` invocation logs
   "another reindex in progress; skipping" and exits 0.
5. **Live query proof:** hit the same endpoint Telegram uses with a fresh session and a term unique
   to a newly-synced repo file:
   `curl -s -X POST http://127.0.0.1:7000/agents/query/runs --data-urlencode 'message=<unique term>'
   --data-urlencode 'session_id=verify-<rand>' --data-urlencode 'user_id=verify' --data-urlencode
   'stream=false'` and confirm the answer cites the new `repos/<name>.md`. (Use a fresh session_id
   to avoid the poisoned-history short-circuit seen in Phase 17.)
6. **Full loop:** let the 5-min cron run unattended once; confirm a GitHub-side `repos/` change
   appears in pgvector within ~5 min with no manual action.

## Out of scope

- Redesigning the multi-master sync topology (Mac rsync ↔ VPS ↔ GitHub) — unchanged.
- Auto-deploying ultra-agents-brain **code** to the VPS (separate gap; code still ships via scp).
- Push-based GitHub Actions→VPS SSH trigger (rejected in favor of the existing pull cron).
