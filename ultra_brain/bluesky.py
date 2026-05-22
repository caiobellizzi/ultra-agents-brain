"""Bluesky public API poller — no auth required for public author feeds."""

from __future__ import annotations

import json
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from .monitor import DedupStore, FeedItem


_PUBLIC_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"


def _ssl_ctx() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_author_feed(handle: str, *, limit: int = 10, timeout: int = 15) -> list[FeedItem]:
    """Fetch recent posts from a Bluesky handle. Returns FeedItem list."""
    params = urllib.parse.urlencode({"actor": handle, "limit": limit})
    url = f"{_PUBLIC_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "ultra-agents-brain/0.1"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    items: list[FeedItem] = []
    for entry in data.get("feed", []):
        post = entry.get("post", {})
        record = post.get("record", {})
        # Skip reposts and replies — only original posts
        if entry.get("reason") or record.get("reply"):
            continue
        text = (record.get("text") or "").strip()
        if not text:
            continue
        # at://did:.../app.bsky.feed.post/<rkey>  →  https://bsky.app/profile/<handle>/post/<rkey>
        uri = post.get("uri", "")
        rkey = uri.rsplit("/", 1)[-1] if uri else ""
        if not rkey:
            continue
        web_url = f"https://bsky.app/profile/{handle}/post/{rkey}"
        # Use first line / 140 chars as title
        title = text.splitlines()[0][:140]
        published = record.get("createdAt", "")
        items.append(FeedItem(title=f"[{handle}] {title}", url=web_url, published=published))
    return items


def run_poll_bluesky(
    handles_file: Path,
    vault_root: Path,
    *,
    dedup_path: Path | None = None,
    limit: int = 10,
) -> list[FeedItem]:
    """Poll each handle, dedup, write new items to Inbox/. Returns new FeedItems."""
    from .markdown import append_log, slugify

    system_dir = vault_root / "_system"
    if dedup_path is None:
        dedup_path = system_dir / "bluesky-seen.json"

    raw = handles_file.read_text(encoding="utf-8").splitlines()
    handles = [line.strip() for line in raw if line.strip() and not line.strip().startswith("#")]

    all_items: list[FeedItem] = []
    for handle in handles:
        try:
            all_items.extend(fetch_author_feed(handle, limit=limit))
        except Exception as exc:
            print(f"bluesky: failed to fetch {handle}: {exc}", file=sys.stderr)

    store = DedupStore(dedup_path)
    new_keys = set(store.add_new([item.url for item in all_items]))
    new_items = [item for item in all_items if item.url in new_keys]

    if not new_items:
        return []

    today = date.today().isoformat()
    inbox_dir = vault_root / "Inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    for item in new_items:
        # bsky- prefix in filename so refine flow can distinguish
        filename = f"{today}-bsky-{slugify(item.title)}.md"
        dest = inbox_dir / filename
        content = f"# {item.title}\n\nsource:: {item.url}\n"
        if item.published:
            content += f"published:: {item.published}\n"
        dest.write_text(content, encoding="utf-8")

    append_log(
        system_dir / "log.md",
        "bluesky",
        f"filed {len(new_items)} new posts from {len(handles)} handles",
        {"new_items": len(new_items), "handles": len(handles)},
    )

    return new_items
