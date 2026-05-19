"""Weekly review helpers for project and area maintenance."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .telos import score_alignment


@dataclass(frozen=True)
class ReviewItem:
    kind: str
    path: Path
    recommendation: str
    requires_approval: bool = True


def _age_days(path: Path) -> int:
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(timezone.utc) - modified).days


def weekly_review(vault_root: Path, *, stale_project_days: int = 30, dormant_area_days: int = 90) -> list[ReviewItem]:
    items: list[ReviewItem] = []
    projects = vault_root / "00-Projects"
    if projects.exists():
        for project in sorted(path for path in projects.iterdir() if path.is_dir()):
            if _age_days(project) >= stale_project_days:
                items.append(ReviewItem("stale-project", project, "Review status; archive only after Telegram approval."))
            if not (project / "_briefing.md").exists():
                items.append(ReviewItem("missing-briefing", project, "Create or refresh project briefing."))
    areas = vault_root / "01-Areas"
    if areas.exists():
        for area in sorted(path for path in areas.iterdir() if path.is_dir()):
            if _age_days(area) >= dormant_area_days:
                items.append(ReviewItem("dormant-area", area, "Check whether this Area is still active."))
    return items


def write_weekly_review(vault_root: Path) -> Path:
    path = vault_root / "_system" / "weekly-review.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    items = weekly_review(vault_root)
    lines = ["# Weekly Review", ""]
    if not items:
        lines.append("No review findings.")
    for item in items:
        rel = item.path.relative_to(vault_root)
        telos = score_alignment(str(rel), vault_root / "_system")
        lines.append(f"- **{item.kind}** `{rel}`: {item.recommendation} TELOS {telos.score:.2f} ({telos.rationale})")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
