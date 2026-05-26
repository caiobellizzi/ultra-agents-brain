"""Contract tests for the workshop registry persister.

These guard the on-disk byte format against drift from ultra-workshop's
``workshop.repo_registry.atomic_write_registry``. If the Workshop changes the
JSON shape, the golden assertion here must change in lockstep — that failure is
the contract alarm.
"""

from __future__ import annotations

import json

import pytest

from agentos.workshop_registry import (
    WorkshopRegistryError,
    persist_registry,
    validate_document,
)

# A document in exactly the shape ultra-workshop produces (entry field set from
# workshop.repo_registry.entry_from_gh_metadata / seed_entry).
GOLDEN_DOCUMENT = {
    "version": 1,
    "repos": [
        {
            "full_name": "caiobellizzi/test-workshop-sandbox",
            "active": True,
            "default_branch": "main",
            "visibility": "public",
            "viewer_permission": "ADMIN",
            "source": "add",
            "created_at": "2026-05-24T19:37:22.372174+00:00",
            "updated_at": "2026-05-24T19:38:10.912650+00:00",
            "last_used_at": None,
        }
    ],
}

# The exact bytes atomic_write_registry would emit: indent=2, sort_keys=True,
# trailing newline.
GOLDEN_BYTES = json.dumps(GOLDEN_DOCUMENT, indent=2, sort_keys=True) + "\n"


def test_persist_writes_byte_identical_sorted_json(tmp_path):
    target = tmp_path / "workshop-repos.json"
    persist_registry(GOLDEN_DOCUMENT, target)
    assert target.read_text(encoding="utf-8") == GOLDEN_BYTES


def test_persist_creates_file_and_parent_when_absent(tmp_path):
    target = tmp_path / "nested" / "_system" / "workshop-repos.json"
    persist_registry(GOLDEN_DOCUMENT, target)
    assert target.exists()
    reloaded = json.loads(target.read_text(encoding="utf-8"))
    assert reloaded == GOLDEN_DOCUMENT


def test_persist_is_atomic_no_tmp_left_behind(tmp_path):
    target = tmp_path / "workshop-repos.json"
    persist_registry(GOLDEN_DOCUMENT, target)
    assert not (tmp_path / ".workshop-repos.json.tmp").exists()


def test_persist_overwrites_existing(tmp_path):
    target = tmp_path / "workshop-repos.json"
    persist_registry(GOLDEN_DOCUMENT, target)
    smaller = {"version": 1, "repos": []}
    persist_registry(smaller, target)
    assert json.loads(target.read_text(encoding="utf-8")) == smaller


@pytest.mark.parametrize(
    "bad",
    [
        [],  # not an object
        {"repos": []},  # missing version
        {"version": "1", "repos": []},  # version not int
        {"version": True, "repos": []},  # bool is not a valid version
        {"version": 1},  # missing repos
        {"version": 1, "repos": {}},  # repos not a list
        {"version": 1, "repos": ["nope"]},  # entry not an object
        {"version": 1, "repos": [{"full_name": "no-slash"}]},  # bad full_name
        {"version": 1, "repos": [{"full_name": 123}]},  # full_name not a string
    ],
)
def test_validate_rejects_malformed(bad):
    with pytest.raises(WorkshopRegistryError):
        validate_document(bad)


def test_validate_rejects_duplicate_full_name():
    doc = {
        "version": 1,
        "repos": [
            {"full_name": "caiobellizzi/a"},
            {"full_name": "caiobellizzi/a"},
        ],
    }
    with pytest.raises(WorkshopRegistryError):
        validate_document(doc)


def test_route_persists_and_reports_count(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from agentos.workshop_registry import register_workshop_routes

    target = tmp_path / "workshop-repos.json"
    monkeypatch.setenv("WORKSHOP_REPO_REGISTRY", str(target))

    app = FastAPI()
    register_workshop_routes(app)
    client = TestClient(app)

    resp = client.put("/workshop/repos", json=GOLDEN_DOCUMENT)
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "repos": 1}
    assert target.read_text(encoding="utf-8") == GOLDEN_BYTES


def test_route_rejects_malformed_with_422(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from agentos.workshop_registry import register_workshop_routes

    monkeypatch.setenv("WORKSHOP_REPO_REGISTRY", str(tmp_path / "r.json"))
    app = FastAPI()
    register_workshop_routes(app)
    client = TestClient(app)

    resp = client.put("/workshop/repos", json={"version": 1, "repos": [{"full_name": "bad"}]})
    assert resp.status_code == 422
