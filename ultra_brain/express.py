"""Briefing and digest helpers."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from . import llm
from .cost import CostLedger


def daily_digest(vault_root: Path, *, day: date | None = None, llm_model: str | None = None) -> str:
    day_text = (day or date.today()).isoformat()
    log_path = vault_root / "_system" / "log.md"
    lines = [f"# Daily Digest for {day_text}", ""]
    if log_path.exists():
        entries = [line for line in log_path.read_text(encoding="utf-8").splitlines() if day_text in line]
        lines.extend(entries or ["No logged operations today."])
    else:
        lines.append("No operations log found.")
    ledger = CostLedger(vault_root / "_system" / "cost-ledger.md")
    if ledger.path.exists():
        lines.extend(["", ledger.rollup(day=day).strip()])

    if llm_model is not None:
        raw_text = "\n".join(lines)
        try:
            summary = llm.complete(
                raw_text,
                model=llm_model,
                system=(
                    "You are a personal assistant writing a concise daily briefing for a developer. "
                    "Summarize the day's operations in 3-5 bullet points. "
                    "Focus on what got done, costs, and anything notable."
                ),
                max_tokens=512,
            )
            return f"# Daily Digest for {day_text}\n\n{summary.strip()}\n"
        except Exception:
            pass

    return "\n".join(lines) + "\n"


def project_briefing(project_dir: Path) -> str:
    briefing = project_dir / "_briefing.md"
    if briefing.exists():
        return briefing.read_text(encoding="utf-8")
    synthesis = project_dir / "synthesis.md"
    if synthesis.exists():
        return synthesis.read_text(encoding="utf-8")[:4000]
    return f"No briefing found for {project_dir.name}."


def tts_placeholder(text: str, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("TTS placeholder. Configure OpenAI or ElevenLabs before generating audio.\n\n" + text, encoding="utf-8")
    return output_path
