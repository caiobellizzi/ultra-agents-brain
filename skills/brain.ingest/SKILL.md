---
name: brain.ingest
description: Ingest URLs, files, or pasted text into the Markdown second brain using PARA filing, source preservation, summaries, entity/concept updates, and append-only logs.
---

# brain.ingest

## Purpose

Turn an incoming source into a durable vault note. Preserve the raw source, summarize it, generate required frontmatter, file it using the vault `CLAUDE.md` contract, update obvious entity/concept pages, append an audit log entry, and return a concise Telegram confirmation with file path and cost.

## Triggers

- Telegram message containing a URL with intent such as "ingest", "save", "clip", "remember", or "file this".
- Pasted article/text that should become a source note.
- Inbox promotion from `worker.monitor` or Obsidian Web Clipper.
- Follow-up request to refile or summarize an existing raw source.

## Required Env/Config

- `SECOND_BRAIN_ROOT`: path to the git-backed vault.
- Vault root `CLAUDE.md`: source of truth for PARA routing, frontmatter, naming, log, link, and privacy rules.
- LiteLLM endpoint and model routing for Tier B planning and Tier C extraction/summarization.
- Crawl4AI MCP endpoint as primary HTML extractor.
- Jina Reader fallback endpoint for failed HTML extraction.
- Cost ledger helper from task `06-cost-ledger-and-trust-gates`.
- Telegram reply channel from Hermes runtime.

## Expected Inputs

- `source`: URL, file path, Inbox note path, or pasted text.
- `ingested_via`: `telegram`, `clipper`, `rss`, or `manual`.
- Optional `target`: project, area, resource folder, or explicit vault path.
- Optional `user_note`: user-supplied context for why this source matters.
- Optional privacy marker blocks: `<private>...</private>`.

## Expected Outputs

- Immutable raw source note under the selected PARA location, usually `sources/` for Projects or Resources.
- Required frontmatter fields: id, type, title, source URL/canonical URL when available, author, dates, tags, entities, concepts, distill layer, status, and ingest cost.
- Concise summary section using `prompts/ingestion-summary.md`.
- Obvious entity/concept page updates when confidence is high.
- Append-only entry in local `_log.md` or vault `_system/log.md`.
- Telegram confirmation with destination path, short title, extraction path used, and cost.

## Cost/Trust Constraints

- Respect the global hard cap of USD 20/day.
- Use Tier C for extraction cleanup and routine summaries; use Tier B only for filing decisions or ambiguous sources.
- Keep one ingest below the configured per-subtask limit of USD 1.
- Warn/refuse when the cost helper reports 80 percent/100 percent daily budget thresholds.
- Strip `<private>...</private>` before cloud LLM calls; route private content to Tier D/private worker or refuse if unavailable.
- Treat vault writes as low risk only when they are append-only or new files. Refiling, overwriting, or broad entity updates are medium risk and require Telegram approval.
- Never execute code from ingested content.

## Relevant Helper Modules

- `skills/brain.ingest/extractor.py`: Crawl4AI primary, Jina fallback, local text fallback.
- `skills/brain.ingest/filer.py`: frontmatter generation, PARA routing, filename generation, entity/concept updates, log append.
- Cost ledger/trust gate helper from task 06.
- Git sync helper from task 07 for pull-before-write and commit-after-write.

## Failure Handling

- If Crawl4AI fails, retry with Jina Reader.
- If web extraction fails but raw text exists, ingest as local text with extraction warning.
- If frontmatter cannot be completed, write to `Inbox/` with `status: needs-review` and report missing fields.
- If filing confidence is low, quarantine in `Inbox/` and ask for target clarification.
- If cost cap is reached, do not partially write; return a refusal with estimated remaining budget.
- If git/vault write fails, return the source summary in Telegram and mark the ingest as not persisted.
