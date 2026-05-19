#!/usr/bin/env python3
"""qmd/ripgrep retrieval wrapper for brain.query."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultra_brain.query import query_vault  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--vault", default="vault")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--no-qmd", action="store_true")
    args = parser.parse_args()
    print(query_vault(args.question, Path(args.vault), limit=args.limit, prefer_qmd=not args.no_qmd), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
