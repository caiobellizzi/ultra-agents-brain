"""Command line entry points for local smoke tests and Hermes wrappers."""

from __future__ import annotations

import argparse
from pathlib import Path

from .cost import CostLedger
from .brief import daily_brief
from .express import daily_digest
from .ingest import Extractor, Filer
from .lint import write_lint_report
from .monitor import run_poll
from .query import query_vault
from .research import aggregate_research, plan_research, worker_summary
from .review import write_weekly_review
from .telos import TelosSessionStore, score_alignment
from .vault import ensure_vault


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ultra-brain")
    parser.add_argument("--vault", default="vault", help="Path to the Markdown second-brain vault")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("ensure-vault")

    ingest = sub.add_parser("ingest")
    ingest.add_argument("source")
    ingest.add_argument("--via", default="manual")
    ingest.add_argument("--cost", type=float, default=0.0)
    ingest.add_argument("--model", default="none")

    query = sub.add_parser("query")
    query.add_argument("question")
    query.add_argument("--limit", type=int, default=8)

    lint = sub.add_parser("lint")
    lint.add_argument("--report", action="store_true")

    sub.add_parser("digest")
    sub.add_parser("cost-summary")

    research = sub.add_parser("research-plan")
    research.add_argument("topic")
    research.add_argument("--workers", type=int, default=5)

    aggregate = sub.add_parser("research-aggregate")
    aggregate.add_argument("topic")
    aggregate.add_argument("worker_outputs", nargs="*")

    telos = sub.add_parser("telos-check")
    telos.add_argument("action")

    monitor_p = sub.add_parser("monitor")
    monitor_p.add_argument("--feeds", default="feeds.txt", help="Path to feeds text file (one URL per line)")
    monitor_p.add_argument("--score", action="store_true")

    bluesky_p = sub.add_parser("bluesky")
    bluesky_p.add_argument("--handles", default="skills/worker.monitor/bluesky-handles.txt", help="Path to handles file (one per line)")
    bluesky_p.add_argument("--limit", type=int, default=10, help="Max posts per handle")

    sub.add_parser("review")

    daily_b = sub.add_parser("daily-brief")
    daily_b.add_argument("--date", default=None, help="YYYY-MM-DD override (default: today)")
    daily_b.add_argument("--no-telegram", action="store_true", help="Skip Telegram delivery")
    daily_b.add_argument("--model", default=None, help="LLM model alias override")

    telos_i = sub.add_parser("telos-interview")
    telos_i.add_argument("--session", type=int, default=None)
    telos_i.add_argument("--answer", default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    vault = Path(args.vault)

    if args.command == "ensure-vault":
        ensure_vault(vault)
        print(f"Vault ensured at {vault}")
        return 0

    if args.command == "ingest":
        ledger = CostLedger(vault / "_system" / "cost-ledger.md")
        extraction = Extractor().extract(args.source)
        result = Filer(vault, ledger=ledger).file(extraction, ingested_via=args.via, cost_usd=args.cost, model=args.model)
        print(result.message)
        return 0

    if args.command == "query":
        print(query_vault(args.question, vault, limit=args.limit), end="")
        return 0

    if args.command == "lint":
        report = write_lint_report(vault)
        print(f"Lint report written to {report}")
        return 0

    if args.command == "digest":
        print(daily_digest(vault), end="")
        return 0

    if args.command == "cost-summary":
        print(CostLedger(vault / "_system" / "cost-ledger.md").rollup(), end="")
        return 0

    if args.command == "research-plan":
        for task in plan_research(args.topic, max_workers=args.workers):
            print(f"{task.id}\t${task.budget_usd:.2f}\t{task.timeout_seconds}s\t{task.angle}")
        return 0

    if args.command == "research-aggregate":
        outputs = []
        for item in args.worker_outputs:
            path = Path(item)
            outputs.append(path.read_text(encoding="utf-8") if path.exists() else worker_summary(args.topic, item, []))
        project = aggregate_research(args.topic, outputs or [worker_summary(args.topic, "general scan", [])], vault)
        print(f"Research project written to {project}")
        return 0

    if args.command == "telos-check":
        result = score_alignment(args.action, vault / "_system")
        print(f"{result.score:.2f} {result.rationale}")
        return 0

    if args.command == "monitor":
        feeds_path = Path(args.feeds)
        if not feeds_path.exists():
            print(f"No feeds file found at {feeds_path}. Create it with one RSS URL per line.")
            return 0
        new_items = run_poll(feeds_path, vault)
        print(f"Monitor: {len(new_items)} new items filed to Inbox")
        return 0

    if args.command == "bluesky":
        from .bluesky import run_poll_bluesky
        handles_path = Path(args.handles)
        if not handles_path.exists():
            print(f"No handles file at {handles_path}")
            return 0
        new_items = run_poll_bluesky(handles_path, vault, limit=args.limit)
        print(f"Bluesky: {len(new_items)} new posts filed to Inbox")
        return 0

    if args.command == "review":
        report = write_weekly_review(vault)
        print(f"Weekly review written to {report}")
        return 0

    if args.command == "daily-brief":
        from datetime import date as _date
        day = _date.fromisoformat(args.date) if args.date else None
        brief = daily_brief(vault, day=day, llm_model=args.model, send_telegram=not args.no_telegram)
        print(f"Brief written to {brief}")
        return 0

    if args.command == "telos-interview":
        store = TelosSessionStore(vault / "_system" / "telos-sessions.json")
        if args.session is None:
            session = store.start()
            print(f"Session {session['id']} started.")
            print(f"Q: {session['next_question']}")
        else:
            if args.answer:
                session = store.answer(args.session, args.answer)
                if session["next_question"]:
                    print(f"Q: {session['next_question']}")
                else:
                    print("TELOS interview complete. Review vault/_system/telos-sessions.json.")
            else:
                data = store.load()
                sessions = data.get("sessions", [])
                session = next((s for s in sessions if isinstance(s, dict) and s.get("id") == args.session), None)
                if session:
                    print(f"Session {args.session} — answers: {len(session.get('answers', []))}")
                    print(f"Next Q: {session.get('next_question', 'complete')}")
                else:
                    print(f"Session {args.session} not found")
        return 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
