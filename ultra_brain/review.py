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


# ---------------------------------------------------------------------------
# Weekly review draft + Telegram HITL
# ---------------------------------------------------------------------------

import json
import re
import shutil
import tempfile
import uuid
from datetime import date
from pathlib import Path as _Path

# Pending sweeps keyed by sweep_id: {"vault_root": str, "promote": [...], "archive": [...]}
# Also persisted to /tmp so the adapter process can load them after the CLI exits.
_PENDING_SWEEPS: dict[str, dict] = {}


def _sweep_file(sweep_id: str) -> _Path:
    return _Path(tempfile.gettempdir()) / f"ultra-brain-sweep-{sweep_id}.json"


def _read_inbox_items(vault_root: Path) -> list[dict]:
    """Return inbox items with telos_relevance and mtime from frontmatter."""
    inbox = vault_root / "Inbox"
    if not inbox.exists():
        return []
    result = []
    for p in sorted(inbox.glob("*.md")):
        if p.name in ("MOC.md", "README.md"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        score = 0.5  # default if no frontmatter
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                m = re.search(r"^telos_relevance:\s*([\d.]+)", parts[1], re.MULTILINE)
                if m:
                    score = float(m.group(1))
        result.append({"path": p, "score": score, "age_days": _age_days(p)})
    return result


def weekly_review_draft(vault_root: Path) -> tuple[str, str]:
    """Build the 5-section weekly review draft.

    Returns (draft_text, sweep_id). sweep_id keys _PENDING_SWEEPS for callback.
    """
    inbox_items = _read_inbox_items(vault_root)
    inbox_count = len(inbox_items)

    stale = [
        item for item in weekly_review(vault_root, stale_project_days=14)
        if item.kind == "stale-project"
    ]

    promotions = [i for i in inbox_items if 0.5 <= i["score"] < 0.6]
    archives = [i for i in inbox_items if i["score"] < 0.5 and i["age_days"] >= 7]

    lines = [
        "🧠 *Weekly Brain Review*",
        "",
        f"📥 Inbox: {inbox_count} item(s) awaiting decision",
    ]

    if stale:
        lines.append(f"📂 Stale projects (>14d): {len(stale)}")
        for item in stale[:3]:
            lines.append(f"  • `{item.path.name}`")
        if len(stale) > 3:
            lines.append(f"  …and {len(stale) - 3} more")
    else:
        lines.append("📂 Stale projects: none")

    if promotions:
        lines.append(f"\n⬆️ Suggested promotions ({len(promotions)}):")
        for i in promotions[:3]:
            lines.append(f"  • `{i['path'].stem}` ({i['score']:.2f})")
    if archives:
        lines.append(f"\n🗃 Suggested archives ({len(archives)}):")
        for i in archives[:3]:
            lines.append(f"  • `{i['path'].stem}` (age {i['age_days']}d, {i['score']:.2f})")

    lines.append(
        f"\n📊 Brain health: {inbox_count} inbox · {len(stale)} stale projects"
        f" · {len(promotions)} promotions ready"
    )

    sweep_id = uuid.uuid4().hex[:12]
    payload = {
        "vault_root": str(vault_root),
        "promote": [str(i["path"]) for i in promotions],
        "archive": [str(i["path"]) for i in archives],
    }
    _PENDING_SWEEPS[sweep_id] = payload
    _sweep_file(sweep_id).write_text(json.dumps(payload), encoding="utf-8")
    return "\n".join(lines), sweep_id


def apply_pending_sweep(sweep_id: str) -> int:
    """Apply the pending sweep for sweep_id. Returns number of files moved."""
    pending = _PENDING_SWEEPS.pop(sweep_id, None)
    if not pending:
        f = _sweep_file(sweep_id)
        if f.exists():
            pending = json.loads(f.read_text(encoding="utf-8"))
        else:
            return 0
    _sweep_file(sweep_id).unlink(missing_ok=True)
    vault_root = Path(pending["vault_root"])
    count = 0
    articles_dir = vault_root / "02-Resources" / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)
    for p in pending["promote"]:
        src = Path(p)
        if src.exists():
            shutil.move(str(src), str(articles_dir / src.name))
            count += 1
    culled_dir = vault_root / "03-Archives" / "auto-culled"
    culled_dir.mkdir(parents=True, exist_ok=True)
    for p in pending["archive"]:
        src = Path(p)
        if src.exists():
            shutil.move(str(src), str(culled_dir / src.name))
            count += 1
    return count


def cancel_pending_sweep(sweep_id: str) -> None:
    _PENDING_SWEEPS.pop(sweep_id, None)
    _sweep_file(sweep_id).unlink(missing_ok=True)


def send_weekly_review_telegram(vault_root: Path, *, chat_id: str | None = None) -> None:
    """Generate weekly draft and send to Telegram with ✅/🔍 HITL buttons."""
    from .telegram import send_message_with_buttons

    draft, sweep_id = weekly_review_draft(vault_root)
    send_message_with_buttons(
        draft,
        [
            ("✅ Apply sweep", f"review_sweep:apply:{sweep_id}"),
            ("🔍 Skip", f"review_sweep:skip:{sweep_id}"),
        ],
        chat_id=chat_id,
    )
