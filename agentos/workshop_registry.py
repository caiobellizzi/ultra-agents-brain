"""Workshop repo-registry persistence — privileged writer for the Workshop pipeline.

The registry lives in the vault's ``_system/`` directory, which is owned by the
Brain service user (``uabrain``). The Workshop runs as a different user (``uws``)
and cannot write there, so it computes the full registry document locally (where
the schema logic and GitHub credentials live) and PUTs it to the Brain via the
localhost ``PUT /workshop/repos`` route. The Brain validates the shape and
atomically persists it.

The on-disk format is kept byte-identical to ultra-workshop's
``workshop.repo_registry.atomic_write_registry`` (json.dumps with indent=2,
sort_keys=True, trailing newline). A contract test guards that shape.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

DEFAULT_REGISTRY_PATH = Path("/srv/second-brain/_system/workshop-repos.json")
REGISTRY_ENV = "WORKSHOP_REPO_REGISTRY"

_FULL_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class WorkshopRegistryError(ValueError):
    """Raised when a posted registry document fails validation."""


def registry_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    return Path(os.environ.get(REGISTRY_ENV, DEFAULT_REGISTRY_PATH))


def validate_document(document: Any) -> dict[str, Any]:
    """Validate the posted registry document and return it normalized.

    The Workshop is the single source of truth for the schema; the Brain only
    enforces the structural invariants needed to keep the file safe to write
    and read back.
    """
    if not isinstance(document, dict):
        raise WorkshopRegistryError("registry document must be an object")

    version = document.get("version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise WorkshopRegistryError("registry document must have an integer 'version'")

    repos = document.get("repos")
    if not isinstance(repos, list):
        raise WorkshopRegistryError("registry document must contain a 'repos' list")

    seen: set[str] = set()
    for entry in repos:
        if not isinstance(entry, dict):
            raise WorkshopRegistryError("each repo entry must be an object")
        full_name = entry.get("full_name")
        if not isinstance(full_name, str) or not _FULL_NAME_RE.match(full_name):
            raise WorkshopRegistryError(f"invalid repo full_name: {full_name!r}")
        if full_name in seen:
            raise WorkshopRegistryError(f"duplicate repo full_name: {full_name}")
        seen.add(full_name)

    return {"version": version, "repos": repos}


def persist_registry(document: Any, path: str | Path | None = None) -> dict[str, Any]:
    """Validate and atomically write the registry document.

    Returns the validated document. The byte layout matches ultra-workshop's
    ``atomic_write_registry`` exactly so reads on either side are stable.
    """
    validated = validate_document(document)
    target = registry_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp")
    tmp.write_text(json.dumps(validated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(target)
    return validated


def register_workshop_routes(app: Any) -> None:
    """Attach the localhost-only ``PUT /workshop/repos`` route to a FastAPI app.

    The AgentOS app binds 127.0.0.1, so this route is only reachable from the
    Workshop process on the same host. The body is the complete registry
    document computed by the Workshop; the Brain replaces the file with it.
    """
    from fastapi import Body, HTTPException
    from fastapi.routing import APIRoute

    async def put_workshop_repos(payload: dict = Body(...)) -> dict[str, Any]:
        try:
            validated = persist_registry(payload)
        except WorkshopRegistryError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"ok": True, "repos": len(validated["repos"])}

    # Insert at the FRONT of the router. AgentOS mounts a catch-all sub-app at
    # "/", so an appended route would be shadowed; routes are matched in order.
    route = APIRoute("/workshop/repos", put_workshop_repos, methods=["PUT"])
    app.router.routes.insert(0, route)
