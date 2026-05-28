"""Vault retrieval and cited answer synthesis."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import llm

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchHit:
    path: Path
    line_no: int
    score: int
    snippet: str


def _terms(query: str) -> list[str]:
    return [term.lower() for term in query.split() if len(term) > 2]


class RipgrepRetriever:
    def __init__(self, vault_root: Path) -> None:
        self.vault_root = vault_root

    def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        terms = _terms(query)
        hits: list[SearchHit] = []
        for path in self.vault_root.rglob("*.md"):
            if ".obsidian" in path.parts:
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for idx, line in enumerate(lines, start=1):
                lower = line.lower()
                score = sum(1 for term in terms if term in lower)
                if score:
                    hits.append(SearchHit(path, idx, score, line.strip()[:240]))
        hits.sort(key=lambda hit: (-hit.score, str(hit.path), hit.line_no))
        return hits[:limit]


class QmdClient:
    def __init__(self, vault_root: Path) -> None:
        self.vault_root = vault_root

    def available(self) -> bool:
        return shutil.which("qmd") is not None

    def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        if not self.available():
            return RipgrepRetriever(self.vault_root).search(query, limit=limit)
        proc = subprocess.run(
            ["qmd", "search", query, "--limit", str(limit), str(self.vault_root)],
            check=False,
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            return RipgrepRetriever(self.vault_root).search(query, limit=limit)
        hits: list[SearchHit] = []
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            hits.append(SearchHit(self.vault_root, 0, 1, line.strip()))
        return hits[:limit]


class KnowledgeClient:
    """Query vault via Agno KnowledgeSurface (pgvector) when POSTGRES_DSN_KNOWLEDGE is set."""

    def __init__(self, vault_root: Path) -> None:
        self.vault_root = vault_root
        self._knowledge: object | None = None

    def available(self) -> bool:
        return bool(os.getenv("POSTGRES_DSN_KNOWLEDGE"))

    def _get_knowledge(self) -> object:
        if self._knowledge is None:
            from agentos.knowledge import make_knowledge  # local import to avoid circular
            self._knowledge = make_knowledge()
        return self._knowledge

    def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        knowledge = self._get_knowledge()
        if not getattr(knowledge, "vector_db", None):
            return []
        docs = knowledge.search(query, max_results=limit)
        hits: list[SearchHit] = []
        for doc in docs:
            rel = (doc.meta_data or {}).get("rel_path") or doc.name or ""
            path = self.vault_root / rel if rel else self.vault_root
            score = max(1, int((doc.reranking_score or 1.0) * 100))
            snippet = (doc.content or "")[:240].strip()
            hits.append(SearchHit(path, 0, score, snippet))
        return hits


def synthesize_answer(
    question: str,
    hits: list[SearchHit],
    *,
    vault_root: Path,
    llm_model: str | None = None,
) -> str:
    if not hits:
        return f"I do not have enough vault evidence to answer: {question}"

    # Build evidence block (used both for LLM context and heuristic fallback)
    evidence_lines: list[str] = []
    seen: set[tuple[Path, int]] = set()
    for hit in hits:
        key = (hit.path, hit.line_no)
        if key in seen:
            continue
        seen.add(key)
        try:
            rel = hit.path.relative_to(vault_root)
        except ValueError:
            rel = hit.path
        citation = f"{rel}:{hit.line_no}" if hit.line_no else str(rel)
        evidence_lines.append(f"[[{citation}]] {hit.snippet}")

    if llm_model is not None and os.getenv("LITELLM_BASE_URL", ""):
        try:
            context = "\n".join(evidence_lines)
            prompt = f"Evidence:\n{context}\n\nQuestion: {question}"
            return llm.complete(
                prompt,
                model=llm_model,
                system=(
                    "You are a second-brain query assistant. Answer the question using ONLY the "
                    "provided vault evidence. Cite each source as [[file:line]]. Be concise."
                ),
            )
        except Exception:
            pass  # fall through to heuristic

    lines = [f"Question: {question}", "", "Evidence-backed answer:"]
    for item in evidence_lines:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def query_vault(
    question: str,
    vault_root: Path,
    *,
    limit: int = 8,
    prefer_qmd: bool = True,
    llm_model: str | None = None,
) -> str:
    # Primary: pgvector KnowledgeSurface when POSTGRES_DSN_KNOWLEDGE is configured
    kc = KnowledgeClient(vault_root)
    if kc.available():
        try:
            hits = kc.search(question, limit=limit)
            if hits:
                return synthesize_answer(question, hits, vault_root=vault_root, llm_model=llm_model)
        except Exception as exc:
            log.warning("KnowledgeClient search failed, falling back to file-based: %s", exc)

    # Fallback: qmd CLI → ripgrep keyword search
    client = QmdClient(vault_root) if prefer_qmd else None
    hits = client.search(question, limit=limit) if client else RipgrepRetriever(vault_root).search(question, limit=limit)
    return synthesize_answer(question, hits, vault_root=vault_root, llm_model=llm_model)
