"""Brief → SPEC.md generator.

Produces a structured SPEC.md from a vault briefing dict and a repo
ARCHITECTURE.md string.  Pure Python, no LLM call, no new dependencies.

Public interface
----------------
    generate_spec(briefing, architecture_md, repo_path="") -> str

CLI entry point
---------------
    python3 -m ultra_brain spec-gen \\
        --briefing <path-to-briefing.md> \\
        --repo <slug> \\
        --vault <vault_path>

Future enhancement
------------------
    PgVector retrieval via agentos/knowledge.py is intentionally deferred.
    When DATABASE_URL is available, call knowledge.search_sources(concepts)
    to enrich the References section with semantically related vault notes.
"""

from __future__ import annotations

import re
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Helpers ──────────────────────────────────────────────────────────────────


def _first_code_block(text: str) -> str:
    """Return the first fenced code block found in *text*, or empty string."""
    match = re.search(r"```[^\n]*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(0)
    return ""


def _wrap_list(items: list[str], bullet: str = "-") -> str:
    """Format a list of strings as a markdown bullet list."""
    if not items:
        return f"{bullet} _(none specified)_"
    return "\n".join(f"{bullet} {item}" for item in items)


def _ears_criterion(goal: str, index: int = 1) -> str:
    """Convert a plain-language goal into an EARS placeholder criterion."""
    goal = goal.strip().rstrip(".")
    # If the goal already starts with "When", use it directly
    if goal.lower().startswith("when "):
        return goal if "the system shall" in goal.lower() else f"{goal}, the system shall _(complete)_."
    return (
        f"When {goal.lower()[:120]},\n"
        f"the system shall _(complete acceptance criterion {index})_."
    )


def _extract_code_style(architecture_md: str, repo_path: str = "") -> str:
    """Return a code style example block from ARCHITECTURE.md or a placeholder."""
    block = _first_code_block(architecture_md)
    if block:
        ref = f"_Source: `{repo_path}/ARCHITECTURE.md`_" if repo_path else "_Source: `ARCHITECTURE.md`_"
        return f"{block}\n\n{ref}"
    return textwrap.dedent("""\
        ```python
        # No code block found in ARCHITECTURE.md — add a representative snippet here.
        # Show the target pattern: function signature, types, return value.
        def example(input: str) -> str:
            ...
        ```

        _Add a real snippet from the codebase that exemplifies the expected style._
    """)


# ── Public API ────────────────────────────────────────────────────────────────


def generate_spec(
    briefing: dict[str, Any],
    architecture_md: str,
    repo_path: str = "",
) -> str:
    """Return SPEC.md content as a string.

    Parameters
    ----------
    briefing:
        Vault briefing frontmatter + body.  Expected keys (all optional with
        graceful fallback): title, body/content, concepts, source_notes,
        telos_relevance, tags, goal.
    architecture_md:
        Full text of vault/repos/<repo>/ARCHITECTURE.md.
    repo_path:
        Repo slug or relative path used in reference links.

    Returns
    -------
    str
        Complete SPEC.md content including all 8 required sections.
    """
    # ── Extract fields with safe defaults ────────────────────────────────────
    title: str = briefing.get("title") or "Untitled Spec"
    body: str = briefing.get("body") or briefing.get("content") or ""
    concepts: list[str] = briefing.get("concepts") or []
    source_notes: list[str] = briefing.get("source_notes") or []
    telos_relevance: float | None = briefing.get("telos_relevance")
    tags: list[str] = briefing.get("tags") or []
    goal: str = briefing.get("goal") or ""
    project: str = briefing.get("project") or repo_path or "_(project)_"
    created_at: str = briefing.get("created_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ── Section: Problem & Context ────────────────────────────────────────────
    context_body = body.strip() if body.strip() else "_(Describe the problem and its context here.)_"
    concept_links = _wrap_list([f"[[{c}]]" if not c.startswith("[[") else c for c in concepts])
    telos_line = f"- **TELOS relevance:** {telos_relevance:.2f}" if telos_relevance is not None else ""
    tags_line = f"- **Tags:** {', '.join(tags)}" if tags else ""

    problem_section = f"""\
## Problem & Context

{context_body}

**Related concepts:**
{concept_links}
{telos_line}
{tags_line}
""".strip()

    # ── Section: In-Scope ─────────────────────────────────────────────────────
    in_scope_section = """\
## In-Scope

- _(List the features and behaviours explicitly included in this spec.)_
- _(Be concrete: name the function, endpoint, or user action.)_"""

    # ── Section: Out-of-Scope ─────────────────────────────────────────────────
    out_of_scope_section = """\
## Out-of-Scope

- _(List what is explicitly excluded to prevent scope creep.)_
- _(Example: "LLM-assisted scoring — future enhancement.")_"""

    # ── Section: Interfaces ───────────────────────────────────────────────────
    interfaces_section = """\
## Interfaces

```python
# ── Public function signatures ─────────────────────────────────────────────
# Replace with real typed interfaces.

def main_entry(input: dict) -> str:
    \"\"\"Primary interface — describe what it does.\"\"\"
    ...
```

_All public functions must have concrete Python type annotations._"""

    # ── Section: Acceptance Criteria (EARS) ───────────────────────────────────
    ears_items: list[str] = []
    if goal:
        ears_items.append(_ears_criterion(goal, 1))
    # Always provide at least 3 EARS criteria placeholders
    for i in range(len(ears_items) + 1, 4):
        ears_items.append(
            f"When _(trigger condition {i})_,\n"
            f"the system shall _(expected behaviour {i})_."
        )

    ears_list = "\n\n".join(f"{i + 1}. {c}" for i, c in enumerate(ears_items))
    acceptance_section = f"""\
## Acceptance Criteria

_Each criterion must follow EARS format: "When X, the system shall Y."_

{ears_list}"""

    # ── Section: References ───────────────────────────────────────────────────
    ref_lines: list[str] = []
    for note in source_notes:
        ref_lines.append(note if note.startswith("[[") else f"[[{note}]]")
    if not ref_lines:
        ref_lines.append("_(add vault wikilinks here)_")
    if repo_path:
        ref_lines.append(f"`{repo_path}/ARCHITECTURE.md`")
    else:
        ref_lines.append("_(add repo file paths here)_")

    refs_body = _wrap_list(ref_lines)
    references_section = f"""\
## References

{refs_body}"""

    # ── Section: Rails (Always / Ask-First / Never) ────────────────────────────
    rails_section = """\
## Rails

| Category  | Rule |
|-----------|------|
| **Always** | _(what the implementation must always do)_ |
| **Always** | _(add as many rows as needed)_ |
| **Ask-First** | _(what requires human confirmation before doing)_ |
| **Ask-First** | _(example: delete any note without asking first)_ |
| **Never** | _(what the implementation must never do)_ |
| **Never** | _(example: write outside vault/repos/<repo>/)_ |"""

    # ── Section: Code Style Example ───────────────────────────────────────────
    code_style_content = _extract_code_style(architecture_md, repo_path)
    code_style_section = f"""\
## Code Style Example

{code_style_content}"""

    # ── Frontmatter ───────────────────────────────────────────────────────────
    frontmatter = f"""\
---
title: "SPEC: {title}"
project: "{project}"
source: "{briefing.get('id', '')}"
created_at: "{created_at}"
status: draft
---"""

    # ── Assemble ──────────────────────────────────────────────────────────────
    sections = [
        frontmatter,
        f"# SPEC: {title}",
        problem_section,
        in_scope_section,
        out_of_scope_section,
        interfaces_section,
        acceptance_section,
        references_section,
        rails_section,
        code_style_section,
    ]

    return "\n\n".join(sections) + "\n"


# ── CLI entry point ───────────────────────────────────────────────────────────


def _cli() -> None:
    """CLI: python3 -m ultra_brain spec-gen --briefing <path> --repo <slug> --vault <vault_path>"""
    import argparse
    import json
    import sys

    parser = argparse.ArgumentParser(description="Generate SPEC.md from a vault briefing")
    parser.add_argument("--briefing", required=True, help="Path to briefing .md file or directory")
    parser.add_argument("--repo", default="", help="Repo slug for reference links")
    parser.add_argument("--vault", default="", help="Vault root path (default: ~/Documents/second-brain)")
    args = parser.parse_args()

    vault_root = Path(args.vault or (Path.home() / "Documents" / "second-brain"))
    briefing_path = Path(args.briefing)

    # If path is a directory, find the first _briefing.md or any .md
    if briefing_path.is_dir():
        candidates = list(briefing_path.glob("*_briefing.md")) or list(briefing_path.glob("*.md"))
        if not candidates:
            print(f"[spec-gen] ERROR: no .md files found in {briefing_path}", file=sys.stderr)
            sys.exit(1)
        briefing_path = candidates[0]

    # Parse frontmatter + body
    briefing = _parse_briefing_file(briefing_path)

    # Load ARCHITECTURE.md if available
    arch_path = vault_root / "repos" / args.repo / "ARCHITECTURE.md"
    if not arch_path.exists():
        # Try without /repos/
        arch_path = vault_root / args.repo / "ARCHITECTURE.md"
    architecture_md = arch_path.read_text() if arch_path.exists() else ""

    spec = generate_spec(briefing, architecture_md, repo_path=args.repo)
    print(spec)


def _parse_briefing_file(path: Path) -> dict:
    """Parse a vault markdown file with YAML frontmatter into a briefing dict."""
    import yaml  # PyYAML — already in requirements.txt via agentos deps

    text = path.read_text()
    briefing: dict = {}

    # Extract YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                briefing = yaml.safe_load(parts[1]) or {}
            except Exception:
                pass
            briefing["body"] = parts[2].strip()
    else:
        briefing["body"] = text.strip()
        briefing["title"] = path.stem.replace("-", " ").replace("_", " ").title()

    return briefing
