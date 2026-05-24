"""`python -m agentos` — run the AgentOS FastAPI server or workers."""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
load_dotenv()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m agentos")
    subparsers = parser.add_subparsers(dest="command")
    live_judge = subparsers.add_parser("live-judge", help="Judge pending live performance eval rows")
    mode = live_judge.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="Run one worker pass and exit")
    mode.add_argument("--loop", action="store_true", help="Run continuously")
    live_judge.add_argument("--interval", type=int, default=60, help="Loop sleep interval in seconds")
    live_judge.add_argument("--limit", type=int, default=10, help="Maximum parent rows to scan per pass")

    args = parser.parse_args(argv)
    if args.command == "live-judge":
        from agentos.live_judge import live_judge_cli

        return live_judge_cli(args)

    import uvicorn

    host = os.environ.get("AGENTOS_HOST", "127.0.0.1")
    port = int(os.environ.get("AGENTOS_PORT", "7000"))
    uvicorn.run("agentos.app:app", host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
