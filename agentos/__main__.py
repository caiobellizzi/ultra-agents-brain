"""`python -m agentos` — run the AgentOS FastAPI server."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("AGENTOS_HOST", "127.0.0.1")
    port = int(os.environ.get("AGENTOS_PORT", "7000"))
    uvicorn.run("agentos.app:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
