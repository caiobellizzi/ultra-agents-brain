#!/usr/bin/env python3
"""TELOS interview session wrapper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultra_brain.telos import TelosSessionStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", default="vault/_system/telos/sessions.json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("start")
    answer = sub.add_parser("answer")
    answer.add_argument("session_id", type=int)
    answer.add_argument("answer")
    args = parser.parse_args()

    store = TelosSessionStore(Path(args.state))
    result = store.start() if args.command == "start" else store.answer(args.session_id, args.answer)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
