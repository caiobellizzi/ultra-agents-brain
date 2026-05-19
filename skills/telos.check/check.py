#!/usr/bin/env python3
"""TELOS alignment wrapper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultra_brain.telos import score_alignment  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action")
    parser.add_argument("--system", default="vault/_system")
    args = parser.parse_args()
    result = score_alignment(args.action, Path(args.system))
    print(f"{result.score:.2f} {result.rationale}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
