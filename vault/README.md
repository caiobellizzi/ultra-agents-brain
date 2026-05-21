# Second Brain

Personal knowledge vault — PARA structure + Karpathy wiki operations.

## Layout

| Dir | Purpose |
|-----|---------|
| `00-Projects/` | Active efforts with a specific end-state |
| `01-Areas/` | Ongoing domains of responsibility |
| `02-Resources/` | Durable reference material |
| `03-Archives/` | Completed / dormant work |
| `Inbox/` | Unfiled captures (clear weekly) |
| `_system/` | Agent operational state (logs, ledger, lint) |

## Quick start

```bash
# Ingest a URL
python3 -m ultra_brain --vault ~/Documents/second-brain ingest https://example.com

# Ask a question
python3 -m ultra_brain --vault ~/Documents/second-brain query "what do I know about X?"

# Daily digest
python3 -m ultra_brain --vault ~/Documents/second-brain digest

# Begin TELOS interview
python3 -m ultra_brain --vault ~/Documents/second-brain telos-interview
```
