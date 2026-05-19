"""RSS monitor and dedup helpers."""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class FeedItem:
    title: str
    url: str
    published: str = ""


def canonicalize_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    filtered = [(key, value) for key, value in query if not key.lower().startswith("utm_")]
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), urllib.parse.urlencode(filtered), ""))


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class DedupStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> set[str]:
        if not self.path.exists():
            return set()
        return set(json.loads(self.path.read_text(encoding="utf-8")).get("seen", []))

    def add_new(self, keys: list[str]) -> list[str]:
        seen = self.load()
        new = [key for key in keys if key not in seen]
        if new:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            seen.update(new)
            self.path.write_text(json.dumps({"seen": sorted(seen)}, indent=2) + "\n", encoding="utf-8")
        return new


def parse_rss(xml_text: str) -> list[FeedItem]:
    root = ET.fromstring(xml_text)
    items: list[FeedItem] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or item.findtext("published") or "").strip()
        if title and url:
            items.append(FeedItem(title, canonicalize_url(url), published))
    return items


def fetch_feed(url: str, *, timeout: int = 30) -> list[FeedItem]:
    request = urllib.request.Request(url, headers={"User-Agent": "ultra-agents-brain/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return parse_rss(response.read().decode("utf-8"))


def score_items(items: list[FeedItem], telos_root: Path) -> list[tuple[FeedItem, float]]:
    """Score feed items against TELOS alignment. Returns (item, score) pairs sorted desc."""
    from .telos import score_alignment
    results = []
    for item in items:
        try:
            check = score_alignment(item.title, telos_root)
            results.append((item, check.score))
        except Exception:
            results.append((item, 0.5))
    results.sort(key=lambda t: -t[1])
    return results


def run_poll(
    feeds_yaml: Path,
    vault_root: Path,
    *,
    dedup_path: Path | None = None,
    score: bool = False,
    telos_root: Path | None = None,
) -> list[FeedItem]:
    """
    Fetch all feeds, dedup against seen store, write new items to vault Inbox.
    Returns list of new FeedItem objects that were filed.

    feeds_yaml: plain text file with one feed URL per line (# comments and blank lines skipped)
    vault_root: Path to vault root directory
    dedup_path: Path to the JSON dedup store (default: vault_root/_system/monitor-seen.json)
    score: whether to TELOS-score items (requires telos_root)
    telos_root: vault_root/_system/ by default
    """
    from .markdown import append_log, slugify

    system_dir = vault_root / "_system"
    if dedup_path is None:
        dedup_path = system_dir / "monitor-seen.json"
    if telos_root is None:
        telos_root = system_dir

    # Read feed URLs — plain text, one per line, skip blanks and # comments
    raw_lines = feeds_yaml.read_text(encoding="utf-8").splitlines()
    feed_urls = [line.strip() for line in raw_lines if line.strip() and not line.strip().startswith("#")]

    # Fetch all feeds, tolerating per-feed errors
    all_items: list[FeedItem] = []
    for url in feed_urls:
        try:
            all_items.extend(fetch_feed(url))
        except Exception as exc:
            print(f"monitor: failed to fetch {url}: {exc}", file=sys.stderr)

    # Dedup
    store = DedupStore(dedup_path)
    keys = [content_hash(item.url) for item in all_items]
    new_keys = set(store.add_new(keys))
    new_items = [item for item, key in zip(all_items, keys) if key in new_keys]

    if not new_items:
        return []

    # Optionally score before filing
    if score:
        scored = score_items(new_items, telos_root)
        new_items = [item for item, _ in scored]

    # Write stub markdown files to Inbox
    today = date.today().isoformat()
    inbox_dir = vault_root / "Inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)
    log_path = system_dir / "log.md"

    for item in new_items:
        filename = f"{today}-{slugify(item.title)}.md"
        dest = inbox_dir / filename
        content = f"# {item.title}\n\nsource:: {item.url}\n"
        if item.published:
            content += f"published:: {item.published}\n"
        dest.write_text(content, encoding="utf-8")

    append_log(
        log_path,
        "monitor",
        f"filed {len(new_items)} new feed items",
        {"new_items": len(new_items), "feeds": len(feed_urls)},
    )

    return new_items
