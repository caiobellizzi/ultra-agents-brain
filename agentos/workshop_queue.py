"""Workshop queue dispatched-ACK route — privileged writer for the Workshop pipeline.

The queue file lives at ``vault/_system/.workshop-queue.jsonl`` (owned by uabrain).
The Workshop (uws) marks entries as dispatched via this route after acting on them.

Route: PUT /workshop/queue/{entry_id}/dispatched
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_QUEUE_PATH = Path("/srv/second-brain/_system/.workshop-queue.jsonl")
QUEUE_ENV = "WORKSHOP_QUEUE_PATH"


def queue_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    return Path(os.environ.get(QUEUE_ENV, DEFAULT_QUEUE_PATH))


def register_queue_routes(app: Any) -> None:
    """Attach the ``PUT /workshop/queue/{entry_id}/dispatched`` route to a FastAPI app.

    The AgentOS app binds 127.0.0.1, so this route is only reachable from the
    Workshop process on the same host. The Workshop calls this after acting on
    a queue entry to mark it as dispatched so the fast-poll service skips it.
    """
    from fastapi import HTTPException
    from fastapi.routing import APIRoute

    async def put_queue_entry_dispatched(entry_id: str) -> dict[str, Any]:
        q_path = queue_path()

        if not q_path.exists():
            raise HTTPException(
                status_code=404,
                detail={"ok": False, "error": "queue file not found"},
            )

        lines = q_path.read_text(encoding="utf-8").splitlines()
        entries: list[dict[str, Any]] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            entries.append(json.loads(stripped))

        # Find the target entry
        target_idx = None
        for i, entry in enumerate(entries):
            if str(entry.get("id", "")) == entry_id:
                target_idx = i
                break

        if target_idx is None:
            raise HTTPException(
                status_code=404,
                detail={"ok": False, "error": "entry not found"},
            )

        # Mark as dispatched
        entries[target_idx]["dispatched"] = True

        # Atomic write: write to temp file in same directory, then rename
        tmp_fd, tmp_name = tempfile.mkstemp(dir=q_path.parent, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                for entry in entries:
                    f.write(json.dumps(entry) + "\n")
            os.replace(tmp_name, q_path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

        log.info("Queue entry %r marked as dispatched", entry_id)
        return {"ok": True, "entry_id": entry_id}

    # Insert at the FRONT of the router. AgentOS mounts a catch-all sub-app at
    # "/", so an appended route would be shadowed; routes are matched in order.
    route = APIRoute(
        "/workshop/queue/{entry_id}/dispatched",
        put_queue_entry_dispatched,
        methods=["PUT"],
    )
    app.router.routes.insert(0, route)
