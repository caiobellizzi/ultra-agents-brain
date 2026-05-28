# Investigation: Claude Opus 4.8 missing from `/model` picker

## Context

User reports that Anthropic published https://www.anthropic.com/news/claude-opus-4-8 announcing **Claude Opus 4.8** (released 2026-05-28, today), but the local `/model` picker in Claude Code does not list it — only Opus 4.7 appears. User suspects a settings bug.

## Findings

1. **Opus 4.8 is real.** WebFetch of the announcement URL confirms:
   - Title: *Introducing Claude Opus 4.8*
   - Date: May 28, 2026
   - Model ID: `claude-opus-4-8`
   - Same price as 4.7 ($5/$25 per MTok)

2. **Local Claude Code is already on the latest published version.** `claude --version` and `npm view @anthropic-ai/claude-code version` both report `2.1.153`. There is no newer CLI to upgrade to right now.

3. **This is NOT a `settings.json` bug.** Grep of `~/.claude/settings.json` shows no `models[]` array — the picker reads its model list from the CLI binary itself, not from user settings. The only model-related config is `CLAUDE_CODE_SUBAGENT_MODEL=claude-sonnet-4-6`, which is unrelated.

4. **Root cause: stale model catalog bundled in CLI 2.1.153.** The CLI was published before today's 4.8 announcement. Its hardcoded model list still tops out at Opus 4.7. The session's system prompt also still describes 4.7 as the latest — confirming the harness metadata has not refreshed.

5. **This is a known pattern, not a configuration error on your side.** Anthropic typically ships a CLI update within hours/days of a model launch that adds the new model to `/model`. Memory observation #23870 (today, 2:10 PM) captured the same confusion.

## Recommendation

No action required on your settings — they are correct. Two options:

- **Wait for the CLI patch release** (likely 2.1.154 or similar) that will add `claude-opus-4-8` to the picker. Run `npm i -g @anthropic-ai/claude-code` periodically, or wait for the auto-update.
- **Use it now via flag**, bypassing the picker:
  ```bash
  claude --model claude-opus-4-8
  ```
  This works because the API accepts the model ID directly even when the CLI's local list is stale. (Not tested live in this session — interrupted by user.)

## Verification

After upgrading the CLI:
```bash
claude --version          # expect > 2.1.153
claude                    # /model should list "Opus 4.8"
```

Or, to test the model ID right now without upgrading:
```bash
claude --model claude-opus-4-8 --print "ping"
```
A normal response confirms the model works; an "unknown model" error confirms the CLI shells the rejection back from the API (in which case wait for the patch).
