# Query Synthesis Prompt

Answer the user's question using only the retrieved vault context.

Inputs:
- User question.
- Retrieval results with vault paths and excerpts.
- Vault schema/routing notes.

Output Markdown:
- `## Answer`: direct answer in 3-8 bullets or short paragraphs.
- `## Evidence`: cite each important claim with a vault-relative path.
- `## Uncertain or Missing`: say what the vault does not establish.
- `## Suggested Follow-up`: optional next query, ingest, or research task.
- `## Write-back Candidate`: only if the answer is durable enough to become a note.

Rules:
- Do not use outside knowledge unless the orchestrator explicitly permits web research.
- Do not hide weak evidence.
- Prefer precise file citations over generic references.
