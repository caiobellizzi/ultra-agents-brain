"""Daily brief synthesizer.

Reads today's Inbox stubs → LLM synthesis → vault file + Telegram summary.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from . import llm
from .markdown import append_log
from .monitor import DedupStore


_SYSTEM_PROMPT = (
    "You are an elite AI research analyst writing a daily brief for a senior engineering leader. "
    "Be direct, opinionated, and high-density. Skip generic summaries. "
    "Surface what actually matters and why it changed today."
)

_BRIEF_TEMPLATE = """\
Below are today's RSS feed items captured from AI/ML sources ({item_count} items, {feed_count} sources).
Synthesize them into a structured daily brief.

DATE: {date}

---ITEMS---
{items_text}
---END ITEMS---

Produce the brief in this EXACT format:

# Daily AI Brief — {date}

## 1) Executive Summary
[5-8 bullets. Each bullet: what happened + why it matters. Strongest signal only.]

## 2) Key Developments
[Group by: OpenAI | Anthropic | Models & Research | Tooling & Infra | Other]
[For each item worth covering:]
- **Headline**
  2-3 sentence summary. Why it matters. Your opinion. [Source]

## 3) What to act on this week
- 3 things to test or experiment with immediately
- 3 things to monitor
- 3 things to ignore unless they mature

## 4) Noise filter
[Items that look overhyped, duplicated, or low-signal. One line each with reason.]

---
Rules:
- Give your opinion on every item you include. Don't be neutral.
- Skip items that are clearly noise: minor bumps, marketing, obvious reposts.
- Anthropic has no RSS feed — use any HN items referencing Anthropic as proxy.
- Full brief under 2000 words.
"""


def _read_inbox_items(vault_root: Path, *, day: date) -> list[dict]:
    inbox_dir = vault_root / "Inbox"
    if not inbox_dir.exists():
        return []
    items = []
    for path in sorted(inbox_dir.glob(f"{day.isoformat()}-*.md")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        title = lines[0].lstrip("# ").strip() if lines else path.stem
        url = published = ""
        for line in lines[1:]:
            if line.startswith("source::"):
                url = line.split("::", 1)[1].strip()
            elif line.startswith("published::"):
                published = line.split("::", 1)[1].strip()
        items.append({"title": title, "url": url, "published": published})
    return items


def _filter_unseen(items: list[dict], store: DedupStore) -> list[dict]:
    seen = store.load()
    return [item for item in items if item["url"] not in seen]


def _format_items(items: list[dict]) -> str:
    lines = []
    for i, item in enumerate(items, 1):
        lines.append(f"{i}. {item['title']}")
        if item["url"]:
            lines.append(f"   {item['url']}")
        if item["published"]:
            lines.append(f"   {item['published']}")
    return "\n".join(lines)


def _telegram_summary(brief_text: str, day: date) -> str:
    lines = brief_text.splitlines()
    bullets: list[str] = []
    in_exec = False
    for line in lines:
        if "Executive Summary" in line:
            in_exec = True
            continue
        if in_exec:
            if line.startswith("## "):
                break
            if line.startswith("- "):
                bullets.append(line)
                if len(bullets) >= 5:
                    break
    header = f"🤖 *Daily AI Brief — {day.isoformat()}*\n\n"
    body = "\n".join(bullets) if bullets else "_No summary extracted._"
    footer = f"\n\n📂 `vault/00-Projects/daily-briefs/{day.isoformat()}.md`"
    return (header + body + footer)[:4096]


def daily_brief(
    vault_root: Path,
    *,
    day: date | None = None,
    llm_model: str | None = None,
    send_telegram: bool = True,
) -> Path:
    """Synthesize daily brief from today's Inbox items. Returns path to written file."""
    today = day or date.today()
    system_dir = vault_root / "_system"
    seen_store = DedupStore(system_dir / "brief-seen.json")
    brief_dir = vault_root / "00-Projects" / "daily-briefs"
    brief_dir.mkdir(parents=True, exist_ok=True)
    brief_path = brief_dir / f"{today.isoformat()}.md"

    all_items = _read_inbox_items(vault_root, day=today)
    new_items = _filter_unseen(all_items, seen_store)

    if not new_items:
        brief_path.write_text(
            f"# Daily AI Brief — {today.isoformat()}\n\nNo new Inbox items today.\n",
            encoding="utf-8",
        )
        return brief_path

    domains = {item["url"].split("/")[2] for item in new_items if item.get("url")}
    prompt = _BRIEF_TEMPLATE.format(
        date=today.isoformat(),
        item_count=len(new_items),
        feed_count=len(domains),
        items_text=_format_items(new_items),
    )

    model = llm_model or "default-worker"
    brief_text = llm.complete(prompt, model=model, system=_SYSTEM_PROMPT, max_tokens=3000, temperature=0.3)
    brief_path.write_text(brief_text, encoding="utf-8")

    seen_store.add_new([item["url"] for item in new_items if item.get("url")])

    append_log(
        system_dir / "log.md",
        "daily-brief",
        f"brief written — {len(new_items)} items from {len(domains)} sources",
        {"items": len(new_items), "path": str(brief_path)},
    )

    if send_telegram:
        try:
            from .telegram import send_message
            chat_id = os.getenv("TELEGRAM_ALERT_CHAT_ID", "")
            if chat_id:
                send_message(_telegram_summary(brief_text, today), chat_id=chat_id)
        except Exception as exc:
            print(f"brief: telegram delivery failed: {exc}")

    return brief_path
