# Weekly Review Prompt

Review the vault state for the requested period.

Inputs:
- Recent global and project logs.
- Current Projects and Areas inventory.
- Latest lint report.
- Cost summary.
- Optional TELOS files.

Output Markdown:
- `## Week Summary`
- `## Active Projects`
- `## Stale or Blocked`
- `## Archive Candidates`
- `## Areas Needing Attention`
- `## TELOS Alignment`
- `## Recommended Approvals`

Rules:
- Propose actions; do not apply them.
- Be explicit about missing TELOS or insufficient evidence.
- Keep Telegram summary separate from full review notes.
