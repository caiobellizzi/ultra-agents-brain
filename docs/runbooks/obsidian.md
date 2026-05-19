# Obsidian Setup And Conflict Recovery

This runbook documents how the Mac Obsidian client should read and edit the vault.

## Install

1. Install Obsidian on the Mac.
2. Clone the private vault repository to the chosen local path.
3. Open that folder as an Obsidian vault.
4. Install the Obsidian Git community plugin.
5. Install the Obsidian Web Clipper browser extension if capture from the browser is desired.

## Recommended Obsidian Git Settings

- Auto-pull on startup: enabled.
- Pull interval: 10 to 15 minutes.
- Auto-commit from Mac: disabled by default unless Caio intentionally edits from Obsidian.
- Auto-push from Mac: disabled by default.
- Commit message for manual Mac edits: `vault: obsidian edits`.

The VPS remains the normal autonomous writer. The Mac should primarily pull, read, and perform deliberate human edits.

## Web Clipper

- Default destination: `Inbox/`.
- Preserve source URL and capture timestamp.
- Do not clip pages containing credentials or private account details.
- File clipped notes during weekly review.

## Human Edit Workflow

1. Open Obsidian and let Git pull first.
2. Edit notes.
3. Commit manually through Obsidian Git or the terminal.
4. Push to the private remote.
5. Allow the VPS to pull before the next Hermes write.

## Conflict Recovery In Obsidian

1. Stop editing the conflicted note.
2. Open the conflicted file in source mode.
3. Keep human-written prose unless an agent addition has newer cited evidence.
4. For `_system/log.md` and `_system/cost-ledger.md`, keep both sides and sort by timestamp.
5. Remove conflict markers.
6. Commit with `vault: resolve obsidian conflict`.
7. Push and verify the VPS can pull cleanly.

## Private Content

- Use `<private>...</private>` around sensitive personal material that must remain in the note.
- Never store API keys, tokens, passwords, recovery codes, cookies, SSH keys, or account numbers.
- Notes marked `privacy: secret` must not be sent to remote LLM providers.

