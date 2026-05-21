"""Knowledge layer for ultra-brain.

Uses PgVector with SentenceTransformerEmbedder (all-MiniLM-L6-v2, local, no API cost)
and hybrid search. The VaultKnowledge class preserves the legacy interface used by
existing tests (vault_path= constructor, load() returning list[Path], file_count property).
"""

from __future__ import annotations

import os
from pathlib import Path

from agno.knowledge.knowledge import Knowledge
from agno.vectordb.pgvector import PgVector, SearchType
from agno.knowledge.embedder.sentence_transformer import SentenceTransformerEmbedder
from agno.knowledge.reranker.sentence_transformer import SentenceTransformerReranker

VAULT_PATH = Path(os.getenv("VAULT_PATH", "vault"))
POSTGRES_DSN_KNOWLEDGE = os.getenv("POSTGRES_DSN_KNOWLEDGE")


def make_knowledge() -> Knowledge:
    vector_db = PgVector(
        table_name="vault",
        db_url=POSTGRES_DSN_KNOWLEDGE,
        embedder=SentenceTransformerEmbedder(
            id="sentence-transformers/all-MiniLM-L6-v2"
        ),
        search_type=SearchType.hybrid,
        reranker=SentenceTransformerReranker(),
    )
    return Knowledge(vector_db=vector_db)


class VaultKnowledge:
    """Backward-compatible wrapper: preserves load() → list[Path] interface for tests,
    and exposes a real Knowledge instance for agent RAG when POSTGRES_DSN_KNOWLEDGE is set."""

    def __init__(self, vault_path: Path = VAULT_PATH) -> None:
        self.vault_path = vault_path
        self._loaded_files: list[Path] = []
        # Build real Knowledge only when a DB DSN is available
        if POSTGRES_DSN_KNOWLEDGE:
            self.knowledge = make_knowledge()
        else:
            self.knowledge = Knowledge(name="ultra-brain-vault")

    def load(self) -> list[Path]:
        if not self.vault_path.exists():
            self.vault_path.mkdir(parents=True, exist_ok=True)
        self._loaded_files = sorted(self.vault_path.rglob("*.md"))
        return self._loaded_files

    async def aload(self) -> None:
        self.load()

    @property
    def file_count(self) -> int:
        return len(self._loaded_files)


kb = VaultKnowledge()


if __name__ == "__main__":
    import sys
    if "--reindex" in sys.argv:
        vault = VaultKnowledge()
        vault.load()
        print(f"Vault reindex complete. {vault.file_count} files loaded.")
    else:
        print("Usage: python -m agentos.knowledge --reindex")
