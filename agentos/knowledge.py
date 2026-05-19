"""Knowledge layer for ultra-brain.

Agno 2.x Knowledge wraps a vector store. We defer vector indexing (no embeddings
configured yet — local dev runs gemma-4-e4b only). For now, `kb.load()` enumerates
markdown files in the vault as a sanity check; vault retrieval goes through
`ultra_brain.query.query_vault` (wrapped as a tool in agentos/tools/vault.py).
"""

from __future__ import annotations

import os
from pathlib import Path

from agno.knowledge.knowledge import Knowledge

VAULT_PATH = Path(os.environ.get("UAB_VAULT_PATH", "./vault")).expanduser().resolve()


class VaultKnowledge:
    """Thin wrapper around Agno Knowledge with a markdown-only loader."""

    def __init__(self, vault_path: Path = VAULT_PATH) -> None:
        self.vault_path = vault_path
        self.knowledge = Knowledge(name="ultra-brain-vault", description="Second-brain markdown vault")
        self._loaded_files: list[Path] = []

    def load(self) -> list[Path]:
        if not self.vault_path.exists():
            self.vault_path.mkdir(parents=True, exist_ok=True)
        self._loaded_files = sorted(self.vault_path.rglob("*.md"))
        return self._loaded_files

    @property
    def file_count(self) -> int:
        return len(self._loaded_files)


kb = VaultKnowledge()
