"""One-shot TELOS-scored inbox sweep.

Scores each Inbox item for telos_relevance (0.0–1.0) using keyword heuristics,
promotes high-relevance items (>=0.6) to 02-Resources/articles/, and archives
the rest to 03-Archives/inbox-sweep-YYYY-MM/.

Usage:
    python3 scripts/inbox_sweep.py --vault ~/Documents/second-brain [--dry-run]

The --dry-run flag prints the plan without moving any files or updating frontmatter.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ultra_brain.vault import trash_paths


# ---------------------------------------------------------------------------
# TELOS scoring keywords
# ---------------------------------------------------------------------------

HIGH_RELEVANCE_KEYWORDS: list[str] = [
    # AI agents and LLM tooling
    "agent", "agents", "agentic", "llm", "gpt", "claude", "anthropic", "openai",
    "gemini", "multi-agent", "multi agent", "mcp", "model context protocol",
    "langchain", "langgraph", "autogen", "crewai", "swarm", "tool use",
    "function call", "tool call", "rag", "retrieval", "embedding",
    # Coding agent workflows
    "codex", "cursor", "copilot", "coding agent", "code generation",
    "spec-driven", "spec driven", "specification", "agentos",
    # Brain / vault / knowledge management for agents
    "second brain", "pkm", "vault", "obsidian", "telos", "para",
    # Inference, model training relevant to agents
    "inference", "fine-tuning", "finetuning", "rlhf", "dpo", "sft",
    "distillation", "benchmark", "eval", "evals",
    # Developer tooling and platform
    "cli", "sdk", "api", "plugin", "extension", "webhook", "worker",
    "cron", "automation", "pipeline", "workflow",
    # Relevant product / company names
    "virgin atlantic codex", "kiro", "devin", "swe-bench",
    "constraint decay", "deepseek",
]

MEDIUM_RELEVANCE_KEYWORDS: list[str] = [
    # Software engineering patterns
    "software engineer", "architecture", "refactor", "clean code", "design pattern",
    "microservice", "distributed system", "event-driven", "ci/cd", "devops",
    "docker", "kubernetes", "terraform", "cloud", "aws", "gcp", "azure",
    # Performance and infra
    "performance", "latency", "throughput", "scalability", "memory", "cache",
    # Security (relevant if code-adjacent)
    "security", "vulnerability", "cve", "encryption", "auth",
    # Programming languages used in project
    "python", "rust", "typescript", "javascript",
    # Open source tooling
    "github", "git", "open source", "npm", "pypi",
]

# Negative prior categories (from dont-do.md)
NEGATIVE_PRIOR_KEYWORDS: list[str] = [
    # CS esoterica
    "apl", "scheme", "forth", "lisp", "80386", "6502", "dos source", "spacelab",
    "microcode", "isa", "retro computing", "retro-computing", "vintage hardware",
    "z386", "microcode disassembled", "dead test",
    # General news / politics / health
    "immigration", "visa", "green card", "uscis", "trump", "fbi", "cia", "nsa",
    "geopolit", "senate", "congress", "law", "lawsuit", "court",
    "health", "medical", "drug", "cancer", "cardiac", "seed oil", "vaccine",
    "salmon run", "kodiak", "fishing",
    "referendum", "canada", "election", "brexit",
    # Off-thesis tech (hardware, embedded, filesystem, retro)
    "wayland", "minecraft", "3d print", "3d-print", "cnc", "fpga",
    "hengefinder", "street alignment", "liquidation", "museum",
    "pasta", "gluten", "food",
    "cbs radio", "airbus", "boeing", "plane crash", "aircraft",
    "kindle", "e-reader", "ebook",
    "pratchett", "writerdeck", "blogging", "i miss",
    "desk setup", "keyboard shortcut",
    "limerick", "humor", "poetry",
    "forensic account", "money getting",
    "nordvpn", "vpn", "piracy",
    "oura", "wearable", "sleep apnea",
    "scammer", "spam", "phishing",
    "oil spill", "chemical leak",
    "baby on the subway",
]


def _extract_text(path: Path) -> tuple[str, str, str]:
    """Return (title, frontmatter_block, body) from a note."""
    text = path.read_text(encoding="utf-8")
    frontmatter = ""
    body = text

    # Handle YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            body = parts[2]

    # Try frontmatter title first
    title = ""
    for line in frontmatter.splitlines():
        if line.startswith("title:"):
            raw = line[len("title:"):].strip().strip('"').strip("'")
            if raw:
                title = raw
                break

    # Fall back to first markdown heading
    if not title:
        for line in body.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

    # Final fallback: filename stem
    if not title:
        title = path.stem

    return title, frontmatter, body


def _score_telos(title: str, body: str) -> float:
    """Score telos_relevance (0.0–1.0) using keyword heuristics.

    Strategy:
    - Start at 0.0
    - Add weight for high-relevance hits
    - Add smaller weight for medium-relevance hits
    - Subtract weight for negative prior hits (but don't go below 0)
    - Cap at 1.0
    """
    combined = (title + " " + body[:500]).lower()

    score = 0.0

    # High relevance: +0.3 per hit, up to 0.9
    high_hits = 0
    for kw in HIGH_RELEVANCE_KEYWORDS:
        if kw in combined:
            high_hits += 1
            if high_hits <= 3:
                score += 0.3

    # Medium relevance: +0.1 per hit, up to 0.2
    med_hits = 0
    for kw in MEDIUM_RELEVANCE_KEYWORDS:
        if kw in combined:
            med_hits += 1
            if med_hits <= 2:
                score += 0.1

    # Negative priors: -0.4 per hit
    for kw in NEGATIVE_PRIOR_KEYWORDS:
        if kw in combined:
            score -= 0.4
            break  # one negative prior is enough to suppress

    return max(0.0, min(1.0, score))


def _update_frontmatter_telos(path: Path, telos_relevance: float) -> None:
    """Write telos_relevance into the note's YAML frontmatter (in-place)."""
    text = path.read_text(encoding="utf-8")

    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            fm = parts[1]
            rest = parts[2]

            # Replace or insert telos_relevance
            if "telos_relevance:" in fm:
                fm = re.sub(
                    r"telos_relevance:\s*.*",
                    f"telos_relevance: {telos_relevance:.2f}",
                    fm,
                )
            else:
                fm = fm.rstrip("\n") + f"\ntelos_relevance: {telos_relevance:.2f}\n"

            path.write_text("---" + fm + "---" + rest, encoding="utf-8")
            return

    # No frontmatter — prepend minimal block
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    slug = path.stem
    fm = (
        f"---\n"
        f"id: {slug}\n"
        f"type: article\n"
        f"title: {path.stem.replace('-', ' ').title()}\n"
        f"ingested_at: {now}\n"
        f"ingested_via: worker\n"
        f"para_tier: Inbox\n"
        f"tags: []\n"
        f"telos_relevance: {telos_relevance:.2f}\n"
        f"status: captured\n"
        f"---\n"
    )
    path.write_text(fm + text, encoding="utf-8")


def _unique_dest(dest: Path) -> Path:
    """Return dest, or dest with a counter suffix if it already exists."""
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    i = 1
    while True:
        candidate = parent / f"{stem}-{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def _copy_for_move(source: Path, dest: Path) -> Path:
    """Copy source to dest, reusing an identical dest left by an interrupted run."""
    source_bytes = source.read_bytes()
    if dest.exists():
        if dest.read_bytes() == source_bytes:
            return dest
        dest = _unique_dest(dest)
    dest.write_bytes(source_bytes)
    return dest


def _append_log(log_path: Path, promoted: list[str], archived: list[str], total: int) -> None:
    """Append a batch log entry to vault/_system/log.md."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists():
        log_path.write_text("# Operations Log\n\n", encoding="utf-8")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = date.today().isoformat()
    entry_lines = [
        f"## [{today}] inbox.sweep | TELOS-scored sweep — {len(promoted)} promoted, {len(archived)} archived",
        f"- timestamp: {now}",
        "- actor: claude-code",
        "- scope: vault/Inbox/",
        "- cost_usd: 0.0000",
        "- status: ok",
        f"- total_scanned: {total}",
        f"- promoted: {len(promoted)}",
        f"- archived: {len(archived)}",
        f"- promoted_dest: vault/02-Resources/articles/",
        f"- archived_dest: vault/03-Archives/inbox-sweep-{today[:7]}/",
        f"- details: Heuristic TELOS scoring (no LLM). High-relevance threshold 0.6. "
        f"Promoted {len(promoted)} AI/agent-related items; archived {len(archived)} off-thesis items.",
    ]
    if promoted[:5]:
        entry_lines.append(f"- promoted_sample: {', '.join(promoted[:5])}")

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(entry_lines) + "\n\n")


_VPS_HOST = "root@31.97.130.253"
_VPS_VAULT = "/srv/second-brain"


def _delete_from_vps(vault_root: Path, paths: list[Path]) -> None:
    """Delete swept files from VPS so the next rsync pull doesn't restore them."""
    if not paths:
        return
    rel_paths = [str(p.relative_to(vault_root)) for p in paths]
    remote_cmd = "rm -f " + " ".join(shlex.quote(f"{_VPS_VAULT}/{rp}") for rp in rel_paths)
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", _VPS_HOST, remote_cmd],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            print(f"VPS cleanup: removed {len(rel_paths)} file(s).")
        else:
            print(f"WARNING: VPS cleanup failed (rc={result.returncode}): {result.stderr.strip()}", file=sys.stderr)
    except Exception as exc:
        print(f"WARNING: VPS cleanup skipped ({exc}); files may reappear after next sync.", file=sys.stderr)


def sweep(vault_root: Path, *, dry_run: bool = False) -> int:
    """Run the inbox sweep. Returns 0 on success."""
    inbox = vault_root / "Inbox"
    if not inbox.exists():
        print(f"ERROR: Inbox directory not found at {inbox}", file=sys.stderr)
        return 1

    items = sorted(
        p for p in inbox.glob("*.md")
        if p.name not in ("MOC.md", "README.md")
    )

    if not items:
        print("Inbox is already empty (only MOC.md / README.md remain).")
        return 0

    today_month = date.today().strftime("%Y-%m")
    promote_dir = vault_root / "02-Resources" / "articles"
    archive_dir = vault_root / "03-Archives" / f"inbox-sweep-{today_month}"

    promoted_names: list[str] = []
    archived_names: list[str] = []
    plan_rows: list[tuple[str, float, str]] = []

    print(f"Scanning {len(items)} inbox items...")
    print()

    for item in items:
        title, _fm, body = _extract_text(item)
        score = _score_telos(title, body)
        if score >= 0.6:
            action = "PROMOTE → 02-Resources/articles/"
        else:
            action = f"ARCHIVE → 03-Archives/inbox-sweep-{today_month}/"
        plan_rows.append((item.name, score, action))

    # Print plan table
    print(f"{'File':<75} {'Score':>5}  Action")
    print("-" * 110)
    for name, score, action in sorted(plan_rows, key=lambda r: -r[1]):
        print(f"{name:<75} {score:>5.2f}  {action}")
    print()

    promote_count = sum(1 for _, s, _ in plan_rows if s >= 0.6)
    archive_count = sum(1 for _, s, _ in plan_rows if s < 0.6)
    total = len(plan_rows)

    print(f"Summary: {total} scanned | {promote_count} to promote | {archive_count} to archive")
    assert promote_count + archive_count == total, "Count mismatch — BUG"

    if dry_run:
        print()
        print("[DRY RUN] No files moved or modified.")
        return 0

    # Execute moves
    promote_dir.mkdir(parents=True, exist_ok=True)
    archive_dir.mkdir(parents=True, exist_ok=True)
    trash_candidates: list[Path] = []

    for item in items:
        title, _fm, body = _extract_text(item)
        score = _score_telos(title, body)

        # Update frontmatter with score
        _update_frontmatter_telos(item, score)

        if score >= 0.6:
            # Promote: update para_tier + status in frontmatter, then move
            text = item.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    fm = parts[1]
                    rest = parts[2]
                    fm = re.sub(r"para_tier:\s*.*", "para_tier: 02-Resources", fm)
                    fm = re.sub(r"status:\s*.*", "status: ingested", fm)
                    item.write_text("---" + fm + "---" + rest, encoding="utf-8")

            # Force iCloud flush unconditionally — _update_frontmatter_telos and write_text
            # may have written to this path; read_bytes forces the OS to flush the iCloud buffer
            _ = item.read_bytes()

            _copy_for_move(item, promote_dir / item.name)
            trash_candidates.append(item)
            promoted_names.append(item.name)
        else:
            # Archive: move as-is (do NOT modify content)
            _copy_for_move(item, archive_dir / item.name)
            trash_candidates.append(item)
            archived_names.append(item.name)

    trash_paths(trash_candidates)
    still_present = [path.name for path in trash_candidates if path.exists()]
    if still_present:
        raise RuntimeError(
            f"Finder trash failed for {len(still_present)} item(s): {still_present[:5]} — manual cleanup required"
        )

    _delete_from_vps(vault_root, trash_candidates)

    print()
    print(f"Done: {len(promoted_names)} promoted, {len(archived_names)} archived.")

    # Verify inbox is clean
    remaining = [p.name for p in inbox.glob("*.md") if p.name not in ("MOC.md", "README.md")]
    if remaining:
        print(f"WARNING: {len(remaining)} item(s) still in Inbox after sweep: {remaining[:5]}", file=sys.stderr)
    else:
        print("Inbox clean: only MOC.md and README.md remain.")

    # Append log entry
    log_path = vault_root / "_system" / "log.md"
    _append_log(log_path, promoted_names, archived_names, total)
    print(f"Log entry appended to {log_path.relative_to(vault_root)}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="One-shot TELOS-scored inbox sweep for ultra-agents-brain vault.",
    )
    parser.add_argument(
        "--vault",
        required=True,
        type=Path,
        help="Path to vault root (e.g. ~/Documents/second-brain)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the plan without moving any files.",
    )
    args = parser.parse_args()

    vault_root = args.vault.expanduser().resolve()
    if not vault_root.exists():
        print(f"ERROR: vault root not found: {vault_root}", file=sys.stderr)
        sys.exit(1)

    sys.exit(sweep(vault_root, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
