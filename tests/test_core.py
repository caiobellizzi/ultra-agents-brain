from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ultra_brain.cost import CostLedger
from ultra_brain.ingest import Extractor, Filer
from ultra_brain.lint import run_lint, write_lint_report
from ultra_brain.monitor import DedupStore, canonicalize_url, parse_rss
from ultra_brain.query import query_vault
from ultra_brain.research import aggregate_research, plan_research, worker_summary
from ultra_brain.review import write_weekly_review
from ultra_brain.telos import TelosSessionStore, score_alignment
from ultra_brain.trust import classify_action
from ultra_brain.vault import ensure_vault


class CoreTest(unittest.TestCase):
    def test_ingest_files_markdown_logs_cost_and_query_finds_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            ensure_vault(vault)
            ledger = CostLedger(vault / "_system" / "cost-ledger.md")
            extraction = Extractor().extract("# Prompt Caching\n\nAnthropic prompt caching reduces repeated context cost.")
            result = Filer(vault, ledger=ledger).file(
                extraction,
                ingested_via="test",
                tags=["llm-cost"],
                entities=["Anthropic"],
                concepts=["prompt-caching"],
                cost_usd=0.01,
                model="default-worker",
            )

            self.assertTrue(result.note_path.exists())
            text = result.note_path.read_text(encoding="utf-8")
            self.assertIn("prompt-caching", text)
            self.assertIn("brain.ingest", (vault / "_system" / "log.md").read_text(encoding="utf-8"))
            self.assertIn("0.010000", ledger.path.read_text(encoding="utf-8"))
            answer = query_vault("prompt caching cost", vault, prefer_qmd=False)
            self.assertIn("Prompt Caching", answer)
            self.assertIn("Evidence-backed answer", answer)

    def test_query_skips_unreadable_files_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            ensure_vault(vault)
            (vault / "readable.md").write_text("# Topic\n\nVisible vault content here.", encoding="utf-8")
            unreadable = vault / "locked.md"
            unreadable.write_text("# Hidden\n\nUnreadable content.", encoding="utf-8")
            unreadable.chmod(0o000)
            try:
                answer = query_vault("visible vault content", vault, prefer_qmd=False)
            finally:
                unreadable.chmod(0o600)
            self.assertIn("Evidence-backed answer", answer)
            self.assertIn("readable.md", answer)
            self.assertNotIn("locked.md", answer)

    def test_cost_gate_warns_and_refuses_at_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = CostLedger(Path(tmp) / "cost-ledger.md", limits={"per_day_total": 1.0, "warn_at_pct": 0.8})
            first = ledger.record(scope="test", operation="a", model="m", cost_usd=0.79)
            self.assertTrue(first.allowed)
            self.assertFalse(first.warning)
            second = ledger.record(scope="test", operation="b", model="m", cost_usd=0.10)
            self.assertTrue(second.allowed)
            self.assertTrue(second.warning)
            refused = ledger.record(scope="test", operation="c", model="m", cost_usd=0.20)
            self.assertFalse(refused.allowed)

    def test_trust_strips_private_and_blocks_high_risk(self) -> None:
        private = classify_action("summarize <private>secret</private>", private_worker_available=False)
        self.assertFalse(private.allowed)
        self.assertNotIn("secret", private.sanitized_text)
        high = classify_action("run shell rm -rf /")
        self.assertFalse(high.allowed)
        self.assertEqual(high.risk, "high")

    def test_research_aggregation_creates_project_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            tasks = plan_research("agent observability", max_workers=3)
            self.assertEqual(len(tasks), 3)
            outputs = [worker_summary("agent observability", task.angle, [f"https://example.com/{task.id}"]) for task in tasks]
            project = aggregate_research("agent observability", outputs, vault)
            self.assertTrue((project / "synthesis.md").exists())
            self.assertTrue((project / "_briefing.md").exists())
            self.assertTrue((project / "_log.md").exists())

    def test_lint_report_detects_private_blocks_and_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            ensure_vault(vault)
            note = vault / "02-Resources" / "articles" / "bad.md"
            note.write_text("---\ntype: article\ntitle: Bad\n---\n\n<private>hide</private>\n", encoding="utf-8")
            findings = run_lint(vault)
            messages = "\n".join(f.message for f in findings)
            self.assertIn("private block", messages)
            self.assertIn("source_url", messages)
            report = write_lint_report(vault, findings)
            self.assertIn("Lint Report", report.read_text(encoding="utf-8"))

    def test_telos_session_and_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            system = Path(tmp) / "_system"
            store = TelosSessionStore(system / "telos" / "sessions.json")
            session = store.start()
            updated = store.answer(int(session["id"]), "Prioritize async research and AI tooling.")
            self.assertTrue(updated["answers"])
            (system / "telos").mkdir(parents=True, exist_ok=True)
            (system / "telos" / "mission.md").write_text("Async research for AI tooling.", encoding="utf-8")
            score = score_alignment("research AI tooling", system)
            self.assertGreater(score.score, 0.5)

    def test_monitor_dedup_and_rss_parse(self) -> None:
        xml = """<?xml version="1.0"?><rss><channel><item><title>A</title><link>https://x.test/a?utm_source=n</link><pubDate>now</pubDate></item></channel></rss>"""
        items = parse_rss(xml)
        self.assertEqual(items[0].url, "https://x.test/a")
        self.assertEqual(canonicalize_url("HTTPS://X.TEST/a/?utm_campaign=x&q=1"), "https://x.test/a?q=1")
        with tempfile.TemporaryDirectory() as tmp:
            store = DedupStore(Path(tmp) / "seen.json")
            self.assertEqual(store.add_new(["a", "b"]), ["a", "b"])
            self.assertEqual(store.add_new(["b"]), [])

    def test_weekly_review_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            ensure_vault(vault)
            (vault / "00-Projects" / "demo").mkdir(parents=True)
            report = write_weekly_review(vault)
            self.assertTrue(report.exists())
            self.assertIn("Weekly Review", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
