#!/usr/bin/env python3
"""File extracted content into the Markdown vault."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultra_brain.cost import CostLedger  # noqa: E402
from ultra_brain.ingest import Extractor, Filer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("--vault", default="vault")
    parser.add_argument("--via", default="manual")
    parser.add_argument("--cost", type=float, default=0.0)
    parser.add_argument("--model", default="none")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--entity", action="append", default=[])
    parser.add_argument("--concept", action="append", default=[])
    args = parser.parse_args()

    vault = Path(args.vault)
    ledger = CostLedger(vault / "_system" / "cost-ledger.md")
    extraction = Extractor().extract(args.source)
    result = Filer(vault, ledger=ledger).file(
        extraction,
        ingested_via=args.via,
        tags=args.tag,
        entities=args.entity,
        concepts=args.concept,
        cost_usd=args.cost,
        model=args.model,
    )
    print(result.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
