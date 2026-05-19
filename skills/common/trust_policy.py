#!/usr/bin/env python3
"""CLI wrapper for trust classification and approval prompts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultra_brain.trust import approval_prompt, classify_action  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action")
    parser.add_argument("--target-path", default="")
    parser.add_argument("--private-worker-available", action="store_true")
    parser.add_argument("--approval-prompt", action="store_true")
    parser.add_argument("--cost", type=float, default=0.0)
    args = parser.parse_args()

    decision = classify_action(args.action, target_path=args.target_path, private_worker_available=args.private_worker_available)
    if args.approval_prompt and decision.needs_approval:
        print(approval_prompt(args.action, decision, cost_estimate=args.cost))
    else:
        print(f"{decision.risk} allowed={decision.allowed} approval={decision.needs_approval} route={decision.route}: {decision.reason}")
    return 0 if decision.allowed else 2


if __name__ == "__main__":
    raise SystemExit(main())
