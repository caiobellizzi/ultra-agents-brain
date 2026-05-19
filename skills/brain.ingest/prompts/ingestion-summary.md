# Ingestion Summary Prompt

You are summarizing a source for a personal Markdown second brain.

Inputs:
- Source metadata: title, author, URL, publication date, extraction method.
- User context: why this was sent, if provided.
- Extracted text.
- Vault schema excerpt from `CLAUDE.md`.

Output Markdown:
1. `## Summary`: 5-8 bullets capturing the source's durable claims.
2. `## Why It Matters`: 2-4 bullets tied to the user's projects, areas, or TELOS when available.
3. `## Entities`: wiki-link candidates as `[[name]]` with one-line rationale.
4. `## Concepts`: wiki-link candidates as `[[concept]]` with one-line rationale.
5. `## Filing Recommendation`: PARA tier, folder, confidence, and reason.
6. `## Caveats`: extraction gaps, uncertain claims, stale dates, or missing context.

Rules:
- Do not invent metadata.
- Preserve source uncertainty.
- Keep direct quotes short and only when unusually important.
- Strip or omit private content before cloud model use.
