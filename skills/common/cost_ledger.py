#!/usr/bin/env python3
"""CLI wrapper for the shared cost ledger helper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultra_brain.cost import CostLedger  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default="vault/_system/cost-ledger.md")
    parser.add_argument("--scope", default="manual")
    parser.add_argument("--operation", default="manual")
    parser.add_argument("--model", default="none")
    parser.add_argument("--cost", type=float, default=0.0)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    ledger = CostLedger(Path(args.ledger))
    if args.summary:
        print(ledger.rollup(), end="")
        return 0
    gate = ledger.record(scope=args.scope, operation=args.operation, model=args.model, cost_usd=args.cost)
    print(gate.reason)
    return 0 if gate.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
