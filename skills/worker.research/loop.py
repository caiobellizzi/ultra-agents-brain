#!/usr/bin/env python3
"""Research worker planning and aggregation wrapper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ultra_brain.research import aggregate_research, plan_research, worker_summary  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default="vault")
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan")
    plan.add_argument("topic")
    plan.add_argument("--workers", type=int, default=5)
    summarize = sub.add_parser("summary")
    summarize.add_argument("topic")
    summarize.add_argument("angle")
    summarize.add_argument("--source", action="append", default=[])
    aggregate = sub.add_parser("aggregate")
    aggregate.add_argument("topic")
    aggregate.add_argument("worker_outputs", nargs="*")
    args = parser.parse_args()

    if args.command == "plan":
        for task in plan_research(args.topic, max_workers=args.workers):
            print(f"{task.id}\t${task.budget_usd:.2f}\t{task.angle}")
        return 0
    if args.command == "summary":
        print(worker_summary(args.topic, args.angle, args.source), end="")
        return 0
    outputs = []
    for item in args.worker_outputs:
        path = Path(item)
        outputs.append(path.read_text(encoding="utf-8") if path.exists() else item)
    project = aggregate_research(args.topic, outputs, Path(args.vault))
    print(project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
