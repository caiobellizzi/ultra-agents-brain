"""Ingestion extraction and vault filing."""

from __future__ import annotations

import hashlib
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from . import llm
from .cost import CostLedger
from .markdown import append_log, first_heading, note_with_frontmatter, slugify
from .vault import ensure_vault, unique_path


URL_RE = re.compile(r"^https?://", re.IGNORECASE)


@dataclass(frozen=True)
class ExtractionResult:
    title: str
    markdown: str
    source_url: str = ""
    canonical_url: str = ""
    method: str = "text"
    content_hash: str = ""


@dataclass(frozen=True)
class IngestResult:
    note_path: Path
    log_path: Path
    cost_warning: bool
    message: str


class Extractor:
    def __init__(self, *, crawl4ai_endpoint: str | None = None, enable_jina: bool = True, timeout: int = 30) -> None:
        self.crawl4ai_endpoint = crawl4ai_endpoint or os.getenv("CRAWL4AI_ENDPOINT", "")
        self.enable_jina = enable_jina
        self.timeout = timeout

    def extract(self, source: str | Path) -> ExtractionResult:
        text = str(source)
        if URL_RE.match(text):
            return self._extract_url(text)
        path = Path(text).expanduser()
        if path.exists():
            body = path.read_text(encoding="utf-8")
            title = first_heading(body) or path.stem
            return self._result(title, body, method="file")
        title = first_heading(text) or text.strip().splitlines()[0][:80] if text.strip() else "Untitled note"
        return self._result(title, text, method="pasted-text")

    def _extract_url(self, url: str) -> ExtractionResult:
        if self.crawl4ai_endpoint:
            try:
                return self._extract_crawl4ai(url)
            except (OSError, ValueError, urllib.error.URLError):
                pass
        if self.enable_jina:
            try:
                return self._extract_jina(url)
            except (OSError, ValueError, urllib.error.URLError):
                pass
        body = f"# {url}\n\nExtraction could not be completed in this environment. Source URL: {url}\n"
        return self._result(url, body, source_url=url, canonical_url=url, method="url-placeholder")

    def _extract_crawl4ai(self, url: str) -> ExtractionResult:
        payload = f'{{"url": "{url}"}}'.encode("utf-8")
        request = urllib.request.Request(
            self.crawl4ai_endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
        title = first_heading(body) or url
        return self._result(title, body, source_url=url, canonical_url=url, method="crawl4ai")

    def _extract_jina(self, url: str) -> ExtractionResult:
        jina_url = "https://r.jina.ai/http://" + url.removeprefix("http://").removeprefix("https://")
        request = urllib.request.Request(jina_url, headers={"User-Agent": "ultra-agents-brain/0.1"})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = response.read().decode("utf-8")
        title = first_heading(body) or url
        return self._result(title, body, source_url=url, canonical_url=url, method="jina-reader")

    @staticmethod
    def _result(
        title: str,
        markdown: str,
        *,
        source_url: str = "",
        canonical_url: str = "",
        method: str = "text",
    ) -> ExtractionResult:
        digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()[:16]
        return ExtractionResult(title.strip() or "Untitled note", markdown, source_url, canonical_url or source_url, method, digest)


class Filer:
    def __init__(self, vault_root: Path, *, ledger: CostLedger | None = None, llm_model: str | None = None) -> None:
        self.vault_root = vault_root
        self.ledger = ledger
        self.llm_model = llm_model
        ensure_vault(vault_root)

    def file(
        self,
        extraction: ExtractionResult,
        *,
        ingested_via: str = "manual",
        para_tier: str | None = None,
        tags: list[str] | None = None,
        entities: list[str] | None = None,
        concepts: list[str] | None = None,
        cost_usd: float = 0.0,
        model: str = "none",
    ) -> IngestResult:
        tier = para_tier or self._choose_tier(extraction)
        today = date.today().isoformat()
        slug = slugify(extraction.title)
        rel_dir = self._target_dir(tier)
        note_path = unique_path(self.vault_root / rel_dir / f"{today}-{slug}.md")
        note_path.parent.mkdir(parents=True, exist_ok=True)
        metadata = {
            "id": f"{today}-{slug}",
            "type": "article" if extraction.source_url else "note",
            "title": extraction.title,
            "author": "",
            "source_url": extraction.source_url,
            "canonical_url": extraction.canonical_url,
            "published_at": "",
            "ingested_at": date.today().isoformat(),
            "ingested_via": ingested_via,
            "para_tier": tier,
            "tags": tags or [],
            "entities": [f"[[{item}]]" for item in (entities or [])],
            "concepts": [f"[[{item}]]" for item in (concepts or [])],
            "distill_layer": 0,
            "telos_relevance": 0,
            "status": "ingested",
            "ingest_cost": cost_usd,
            "content_hash": extraction.content_hash,
        }
        body = (
            f"# {extraction.title}\n\n"
            f"Source: {extraction.source_url or 'manual'}\n\n"
            f"Extraction method: {extraction.method}\n\n"
            "## Content\n\n"
            f"{extraction.markdown.strip()}\n"
        )
        note_path.write_text(note_with_frontmatter(metadata, body), encoding="utf-8")
        self._update_entity_pages(entities or [], note_path)
        log_path = self.vault_root / "_system" / "log.md"
        append_log(
            log_path,
            "brain.ingest",
            f"filed {extraction.title}",
            {"path": note_path.relative_to(self.vault_root), "method": extraction.method, "cost_usd": cost_usd},
        )
        warning = False
        if self.ledger and cost_usd > 0:
            gate = self.ledger.record(scope="ingest", operation="brain.ingest", model=model, cost_usd=cost_usd, notes=str(note_path))
            warning = gate.warning
        rel = note_path.relative_to(self.vault_root)
        return IngestResult(note_path, log_path, warning, f"Filed `{rel}` (${cost_usd:.4f})")

    _VALID_TIERS = frozenset({"00-Projects", "01-Areas", "02-Resources", "Inbox"})

    def _choose_tier(self, extraction: ExtractionResult) -> str:
        if self.llm_model:
            try:
                response = llm.complete(
                    f"Title: {extraction.title}\n\nContent preview:\n{extraction.markdown[:500]}",
                    model=self.llm_model,
                    system=(
                        "You are a PARA filing assistant. Given a document title and first 500 "
                        "characters, reply with exactly one of: 00-Projects, 01-Areas, "
                        "02-Resources, Inbox. Nothing else."
                    ),
                    max_tokens=10,
                ).strip()
                if response in self._VALID_TIERS:
                    return response
            except Exception:
                pass  # fall through to heuristic
        # Heuristic fallback
        title = extraction.title.lower()
        if "research" in title or "project" in title:
            return "00-Projects"
        if extraction.source_url:
            return "02-Resources"
        return "Inbox"

    @staticmethod
    def _target_dir(tier: str) -> Path:
        if tier == "02-Resources":
            return Path("02-Resources/articles")
        if tier == "00-Projects":
            return Path("00-Projects") / slugify("ad-hoc-research")
        if tier in {"01-Areas", "03-Archives", "Inbox"}:
            return Path(tier)
        return Path("Inbox")

    def _update_entity_pages(self, entities: list[str], source_path: Path) -> None:
        for entity in entities:
            path = self.vault_root / "01-Areas" / "ai-tooling-landscape" / "entities" / f"{slugify(entity)}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text(
                    note_with_frontmatter(
                        {"type": "entity", "title": entity, "status": "stub"},
                        f"# {entity}\n\n## Sources\n\n- [[{source_path.stem}]]\n",
                    ),
                    encoding="utf-8",
                )
            else:
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(f"- [[{source_path.stem}]]\n")


def ingest_source(source: str, vault_root: Path, **kwargs: object) -> IngestResult:
    extraction = Extractor().extract(source)
    return Filer(vault_root).file(extraction, **kwargs)
