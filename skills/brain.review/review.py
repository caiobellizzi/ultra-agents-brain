#!/usr/bin/env python3
"""Weekly review wrapper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultra_brain.review import write_weekly_review  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default="vault")
    args = parser.parse_args()
    print(write_weekly_review(Path(args.vault)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
