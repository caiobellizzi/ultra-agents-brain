"""Deterministic vault lint passes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import llm
from .markdown import extract_wikilinks, parse_frontmatter


@dataclass(frozen=True)
class LintFinding:
    severity: str
    path: Path
    message: str


def run_lint(vault_root: Path) -> list[LintFinding]:
    findings: list[LintFinding] = []
    markdown_files = [path for path in vault_root.rglob("*.md") if ".obsidian" not in path.parts]
    inbound: dict[str, int] = {}
    parsed: list[tuple[Path, dict[str, str], str]] = []
    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        parsed.append((path, meta, body))
        for link in extract_wikilinks(text):
            inbound[link] = inbound.get(link, 0) + 1
        if "<private>" in text.lower():
            findings.append(LintFinding("error", path, "private block present; verify it is stripped before cloud LLM calls"))
        if path.name not in {"README.md", "CLAUDE.md"} and not meta and not path.name.startswith("_"):
            findings.append(LintFinding("warning", path, "missing frontmatter"))
        if meta.get("type") in {"article", "paper"} and not meta.get("source_url"):
            findings.append(LintFinding("warning", path, "source note is missing source_url"))
    for path, meta, body in parsed:
        if path.name.startswith("_") or path.name in {"README.md", "CLAUDE.md"}:
            continue
        title = meta.get("title") or path.stem
        has_links = bool(extract_wikilinks(body))
        if inbound.get(title, 0) == 0 and not has_links:
            findings.append(LintFinding("info", path, "orphan candidate: no wikilinks or inbound links detected"))
    return findings


def run_llm_lint(vault_root: Path, *, llm_model: str = "default-worker") -> list[LintFinding]:
    findings: list[LintFinding] = []
    markdown_files = [path for path in vault_root.rglob("*.md") if ".obsidian" not in path.parts]
    candidates: list[Path] = []
    for path in markdown_files:
        try:
            text = path.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            distill_layer = meta.get("distill_layer")
            if distill_layer is None or str(distill_layer) == "0":
                candidates.append(path)
        except Exception:
            continue

    for path in candidates[:20]:
        try:
            text = path.read_text(encoding="utf-8")
            response = llm.complete(
                text[:3000],
                model=llm_model,
                system=(
                    "You are a knowledge vault linter. Identify stale claims (dates >1 year old stated as current) "
                    "and potential contradictions with common knowledge. For each finding output a line like: "
                    "STALE: <summary> or CONTRADICTION: <summary>. If none found, output: OK"
                ),
                max_tokens=200,
            )
            for line in response.splitlines():
                line = line.strip()
                if line.startswith("STALE:"):
                    findings.append(LintFinding("warning", path, line[len("STALE:"):].strip()))
                elif line.startswith("CONTRADICTION:"):
                    findings.append(LintFinding("warning", path, line[len("CONTRADICTION:"):].strip()))
        except Exception:
            continue

    return findings


def write_lint_report(vault_root: Path, findings: list[LintFinding] | None = None, *, llm: bool = False) -> Path:
    findings = run_lint(vault_root) if findings is None else findings
    if llm:
        findings = list(findings) + run_llm_lint(vault_root)
    report = vault_root / "_system" / "lint-report.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Lint Report", ""]
    if not findings:
        lines.append("No findings.")
    for finding in findings:
        try:
            rel = finding.path.relative_to(vault_root)
        except ValueError:
            rel = finding.path
        lines.append(f"- **{finding.severity}** `{rel}`: {finding.message}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
