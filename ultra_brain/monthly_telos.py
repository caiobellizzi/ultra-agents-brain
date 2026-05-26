"""Monthly TELOS recheck — scores vault/00-Projects/ against quarter-goals and flags drift."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .telos import score_alignment
from .telegram import send_message


def monthly_telos_recheck(
    vault_root: Path,
    *,
    drift_threshold: float = 0.5,
    send_telegram: bool = True,
    chat_id: str | None = None,
) -> list[dict]:
    """Score all vault/00-Projects/ directories against telos goals.

    Returns list of dicts: {project, score, rationale, drifting}.
    Sends Telegram message listing drifting projects if send_telegram=True and drift found.
    """
    projects_dir = vault_root / "00-Projects"
    telos_root = vault_root / "_system"

    if not projects_dir.exists():
        print(f"WARNING: {projects_dir} does not exist — no projects to check")
        return []

    results: list[dict] = []
    for entry in projects_dir.iterdir():
        if not entry.is_dir():
            continue
        check = score_alignment(entry.name, telos_root)
        results.append(
            {
                "project": entry.name,
                "score": check.score,
                "rationale": check.rationale,
                "drifting": check.score < drift_threshold,
            }
        )

    # Sort: drifting first, then by score ascending
    results.sort(key=lambda r: (not r["drifting"], r["score"]))

    # Print summary report
    today = date.today().isoformat()
    print(f"Monthly TELOS Recheck — {today}")
    print("-" * 50)
    for r in results:
        tag = "[DRIFT]" if r["drifting"] else "[ok]"
        print(f"  {r['project']}: {r['score']:.2f} {tag} — {r['rationale']}")
    drifting = [r for r in results if r["drifting"]]
    print("-" * 50)
    print(f"Drifting: {len(drifting)} / {len(results)}")

    if drifting and send_telegram:
        drift_lines = "\n".join(
            f"• {r['project']}: {r['score']:.2f}" for r in drifting
        )
        msg = (
            f"⚠️ Monthly TELOS Drift Report\n\n"
            f"{drift_lines}\n\n"
            f"{len(drifting)} project(s) drifting from quarter goals."
        )
        send_message(msg, chat_id=chat_id)

    return results
