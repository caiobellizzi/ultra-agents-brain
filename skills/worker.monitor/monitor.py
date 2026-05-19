#!/usr/bin/env python3
"""RSS monitor wrapper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultra_brain.monitor import DedupStore, canonicalize_url, fetch_feed  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("feed_url", nargs="?")
    parser.add_argument("--state", default="vault/_system/monitor-seen.json")
    parser.add_argument("--canonicalize")
    args = parser.parse_args()
    if args.canonicalize:
        print(canonicalize_url(args.canonicalize))
        return 0
    if not args.feed_url:
        parser.error("feed_url is required unless --canonicalize is used")
    items = fetch_feed(args.feed_url)
    store = DedupStore(Path(args.state))
    new_urls = store.add_new([item.url for item in items])
    print(json.dumps({"new": new_urls, "count": len(new_urls)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
