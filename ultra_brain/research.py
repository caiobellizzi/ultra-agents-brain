"""Research worker planning and aggregation helpers."""

from __future__ import annotations

import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import llm
from .markdown import append_log, note_with_frontmatter, slugify
from .vault import ensure_vault


@dataclass(frozen=True)
class ResearchSubtask:
    id: str
    angle: str
    budget_usd: float
    timeout_seconds: int


def plan_research(topic: str, *, max_workers: int = 5, per_worker_budget: float = 1.0) -> list[ResearchSubtask]:
    angles = [
        "primary sources and official docs",
        "current open-source implementations",
        "architecture and integration patterns",
        "risks, failure modes, and operating costs",
        "alternatives and rejected options",
    ]
    return [
        ResearchSubtask(f"worker-{idx}", f"{topic}: {angle}", per_worker_budget, 1800)
        for idx, angle in enumerate(angles[:max_workers], start=1)
    ]


def _fetch_url(url: str, *, timeout: int = 30) -> str:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            return resp.read(8000).decode("utf-8", errors="replace")
    except Exception:
        return ""


def worker_summary(topic: str, angle: str, sources: list[str], *, llm_model: str | None = None) -> str:
    if llm_model and sources:
        try:
            context_parts: list[str] = []
            total = 0
            for url in sources[:3]:
                content = _fetch_url(url)
                if content:
                    chunk = f"URL: {url}\n{content}"
                    remaining = 5000 - total
                    if remaining <= 0:
                        break
                    context_parts.append(chunk[:remaining])
                    total += len(chunk[:remaining])
            if context_parts:
                context_block = "\n\n---\n\n".join(context_parts)
                return llm.complete(
                    f"Angle: {angle}\n\nTopic: {topic}\n\nSources:\n{context_block}",
                    model=llm_model,
                    system=(
                        "You are a research worker. Summarize the provided source content for the given research angle. "
                        "Focus on facts, cite sources by URL. Output clean Markdown."
                    ),
                    max_tokens=1024,
                )
        except Exception:
            pass

    lines = [f"# Worker Summary: {angle}", "", f"Topic: {topic}", "", "## Findings"]
    if sources:
        for source in sources:
            lines.append(f"- Review source: {source}")
    else:
        lines.append("- No live sources supplied; worker should search, extract, and cite sources before final aggregation.")
    lines.extend(["", "## Citations", *[f"- {source}" for source in sources]])
    return "\n".join(lines) + "\n"


def aggregate_research(topic: str, worker_outputs: list[str], vault_root: Path, *, project_slug: str | None = None) -> Path:
    ensure_vault(vault_root)
    slug = project_slug or f"{date.today().isoformat()}-{slugify(topic)}"
    project_dir = vault_root / "00-Projects" / slug
    (project_dir / "sources").mkdir(parents=True, exist_ok=True)
    (project_dir / "entities").mkdir(exist_ok=True)
    (project_dir / "concepts").mkdir(exist_ok=True)
    meta = {
        "id": slug,
        "type": "project",
        "title": topic,
        "status": "active",
        "created_at": date.today().isoformat(),
    }
    (project_dir / "_meta.yaml").write_text("\n".join(f"{key}: {value}" for key, value in meta.items()) + "\n", encoding="utf-8")
    synthesis_body = ["# Synthesis", "", f"Topic: {topic}", "", "## Worker Inputs"]
    briefing_body = ["# Briefing", "", f"Topic: {topic}", "", "## Bottom Line"]
    for idx, output in enumerate(worker_outputs, start=1):
        source_path = project_dir / "sources" / f"worker-{idx}.md"
        source_path.write_text(output, encoding="utf-8")
        synthesis_body.append(f"- [[worker-{idx}]] contributed findings.")
        briefing_body.append(f"- Worker {idx}: see `sources/worker-{idx}.md`.")
    (project_dir / "synthesis.md").write_text(
        note_with_frontmatter({"type": "synthesis", "title": topic, "status": "draft"}, "\n".join(synthesis_body)),
        encoding="utf-8",
    )
    (project_dir / "_briefing.md").write_text("\n".join(briefing_body) + "\n", encoding="utf-8")
    append_log(project_dir / "_log.md", "worker.research", f"aggregated research for {topic}", {"workers": len(worker_outputs)})
    append_log(vault_root / "_system" / "log.md", "worker.research", f"created project {slug}", {"path": project_dir.relative_to(vault_root)})
    return project_dir
