# Research Worker Summary Prompt

Summarize one bounded research subtask for aggregation.

Inputs:
- Subtask question.
- Search/fetch results.
- Extracted source text snippets.
- Budget/timeout status.

Output Markdown:
- `## Subtask`
- `## Bottom Line`
- `## Findings`
- `## Sources`
- `## Confidence`
- `## Gaps`
- `## Suggested Aggregation Tags`

Rules:
- Every non-obvious claim needs a citation.
- Separate source facts from your interpretation.
- Prefer recent primary sources when the topic is current.
- Be explicit when the search was incomplete.
