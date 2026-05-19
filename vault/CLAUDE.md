# Vault Schema-as-Config

This file is the source of truth for Hermes skills and human operators writing to this vault.
When this file conflicts with another note, follow this file.

## Directory Contract

- `00-Projects/`: active efforts with a specific outcome, owner, status, and review cadence.
- `01-Areas/`: ongoing domains of responsibility or interest with no fixed end date.
- `02-Resources/`: durable reference material, articles, papers, books, prompts, and reusable examples.
- `03-Archives/`: completed, inactive, deprecated, or superseded projects and resources.
- `Inbox/`: unfiled captures. Nothing should remain here after weekly review unless blocked.
- `_system/`: append-only operational files, indices, lint outputs, cost ledger, and TELOS.

## Path And Naming Rules

- Use lowercase kebab-case for filenames and directories.
- Prefix dated project folders with `YYYY-MM-` when the start month matters.
- Use `_briefing.md`, `_log.md`, and `_meta.yaml` for project-local control files.
- Store immutable extracted source notes under `sources/`.
- Store canonical entities under `entities/`.
- Store reusable idea pages under `concepts/`.
- Do not rename or move notes just to improve aesthetics; preserve inbound links unless filing is clearly wrong.

Recommended project shape:

```text
00-Projects/yyyy-mm-topic/
├── _briefing.md
├── _log.md
├── _meta.yaml
├── sources/
├── entities/
├── concepts/
└── synthesis.md
```

## Frontmatter Schemas

All machine-written notes must include YAML frontmatter. Unknown optional fields may be omitted, but required fields must be present.

### Article

```yaml
---
id: yyyy-mm-dd-source-slug
type: article
title: ""
author: ""
source_url: ""
canonical_url: ""
published_at: null
ingested_at: yyyy-mm-ddThh:mm:ssZ
ingested_via: telegram
para_tier: 02-Resources
tags: []
entities: []
concepts: []
distill_layer: 0
telos_relevance: null
status: ingested
ingest_cost: 0.0
privacy: public
---
```

### Paper

```yaml
---
id: yyyy-mm-dd-paper-slug
type: paper
title: ""
authors: []
source_url: ""
canonical_url: ""
published_at: null
ingested_at: yyyy-mm-ddThh:mm:ssZ
ingested_via: telegram
para_tier: 02-Resources
tags: []
entities: []
concepts: []
distill_layer: 0
telos_relevance: null
status: ingested
ingest_cost: 0.0
privacy: public
---
```

### Book

```yaml
---
id: book-slug
type: book
title: ""
author: ""
source_url: ""
canonical_url: ""
published_at: null
ingested_at: yyyy-mm-ddThh:mm:ssZ
ingested_via: manual
para_tier: 02-Resources
tags: []
entities: []
concepts: []
distill_layer: 0
telos_relevance: null
status: ingested
ingest_cost: 0.0
privacy: public
---
```

### Concept

```yaml
---
id: concept-slug
type: concept
title: ""
created_at: yyyy-mm-ddThh:mm:ssZ
updated_at: yyyy-mm-ddThh:mm:ssZ
para_tier: 00-Projects
tags: []
entities: []
concepts: []
source_notes: []
distill_layer: 1
telos_relevance: null
status: active
privacy: public
---
```

### Entity

```yaml
---
id: entity-slug
type: entity
title: ""
entity_kind: tool
created_at: yyyy-mm-ddThh:mm:ssZ
updated_at: yyyy-mm-ddThh:mm:ssZ
para_tier: 00-Projects
tags: []
aliases: []
source_notes: []
distill_layer: 1
telos_relevance: null
status: active
privacy: public
---
```

Allowed `entity_kind` values: `person`, `company`, `tool`, `project`, `protocol`, `community`, `other`.

### Briefing

```yaml
---
id: yyyy-mm-dd-briefing-slug
type: briefing
title: ""
created_at: yyyy-mm-ddThh:mm:ssZ
project: ""
para_tier: 00-Projects
tags: []
source_notes: []
audience: caio
status: draft
privacy: public
---
```

### Log

```yaml
---
id: log-slug
type: log
title: ""
created_at: yyyy-mm-ddThh:mm:ssZ
scope: global
append_only: true
privacy: operational
---
```

## Field Conventions

- `id`: stable kebab-case identifier; do not change after creation.
- `type`: one of `article`, `paper`, `book`, `concept`, `entity`, `briefing`, `log`, `moc`, `index`, `ledger`, `runbook`.
- `ingested_via`: one of `telegram`, `clipper`, `rss`, `manual`, `worker`, `system`.
- `para_tier`: one of `00-Projects`, `01-Areas`, `02-Resources`, `03-Archives`, `Inbox`, `_system`.
- `distill_layer`: `0` raw, `1` highlighted, `2` summarized, `3` executive.
- `status`: prefer `captured`, `ingested`, `distilled`, `linted`, `active`, `draft`, `archived`, or `blocked`.
- `privacy`: one of `public`, `personal`, `private`, `secret`, `operational`.

## Cross-Link Conventions

- Link entities as `[[entity-name]]`.
- Link concepts as `[[concept-name]]`.
- Prefer canonical lowercase kebab-case page names.
- Add aliases in frontmatter instead of creating duplicate pages.
- Cite source notes with wiki links plus source URL where available.
- Do not create a link for every noun; link only pages worth maintaining.

## Tags

- Use tags for broad retrieval buckets, not sentence-level meaning.
- Prefer lowercase kebab-case: `llm-cost`, `agent-observability`, `personal-finance`.
- Keep TELOS-alignment data in `telos_relevance`, not tags.

## Append-Only Log Format

Logs are append-only. Add new entries at the bottom.

```markdown
## [YYYY-MM-DD] operation | short description

- timestamp: YYYY-MM-DDThh:mm:ssZ
- actor: hermes | caio | worker.<name>
- scope: global | path/to/note.md
- cost_usd: 0.0000
- status: ok | blocked | failed
- links: [[note-one]], [[note-two]]
- details: one concise paragraph
```

Never rewrite prior log entries except to fix formatting that prevents parsing.

## Private Content Rules

- Secrets never belong in the vault. Store tokens, API keys, SSH keys, passwords, cookies, and recovery codes externally.
- Wrap sensitive personal content as `<private>...</private>` when it must remain in a note.
- Before sending note content to remote LLM providers, strip every `<private>...</private>` block.
- Notes with `privacy: secret` must not be sent to any remote model. Use local-only tooling or ask Caio.
- If a source includes credentials, discard the secret text and log only that a secret was redacted.

## Filing Decision Tree

1. Is it a secret, token, credential, or key?
   - Do not write it. Add a redacted operational note if needed.
2. Is it unprocessed capture or uncertain?
   - Write to `Inbox/` with `status: captured`.
3. Does it support an active outcome with a deadline or deliverable?
   - File under `00-Projects/<project-slug>/`.
4. Is it an ongoing domain Caio maintains over time?
   - File under `01-Areas/<area-slug>/`.
5. Is it reusable reference material without an active owner?
   - File under `02-Resources/<resource-kind>/`.
6. Is it completed, dormant, or superseded?
   - File under `03-Archives/`.
7. Is it operational state for the agent system?
   - File under `_system/`.

When uncertain between Project and Area, choose Project only if a concrete end-state exists.
When uncertain between Area and Resource, choose Area only if Caio is actively maintaining it.

