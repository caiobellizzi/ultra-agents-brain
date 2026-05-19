# Lint Report Prompt

Review the supplied vault excerpts for knowledge-base hygiene problems.

Find:
- Contradictions between notes.
- Claims that appear stale based on dates or source age.
- Orphan pages or missing reciprocal links.
- Duplicate or near-duplicate notes.
- Candidates for progressive summarization.

Output Markdown:
- `## Executive Summary`
- `## Findings`
- `## Suggested Actions`
- `## Progressive Summarization Queue`
- `## Needs Human Review`

For each finding include:
- Severity: high, medium, low.
- Affected vault paths.
- Evidence excerpt references.
- Confidence.
- Suggested action without applying it.
