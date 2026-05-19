#!/usr/bin/env python3
"""TTS placeholder wrapper for brain.express."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultra_brain.express import tts_placeholder  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("text")
    parser.add_argument("--output", default="vault/_system/tts-placeholder.txt")
    args = parser.parse_args()
    print(tts_placeholder(args.text, Path(args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
