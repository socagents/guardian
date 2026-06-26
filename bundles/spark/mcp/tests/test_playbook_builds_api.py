"""Playbook-build history — REST routes + MCP tool round-trip (v0.2.50).

Covers two surfaces over the same playbook_build_store:

  * the 5 REST routes registered by api.playbook_builds.register_
    playbook_build_routes — list (empty / populated / status filter),
    create (success + 400 on missing use_case), get (200 / 404),
    patch (200 / 404), delete (200 / 404).
  * the 5 MCP tool functions in usecase.builtin_components.playbook_tools
    (playbook_builds_list / _get / playbook_build_record / _update /
    _delete) round-tripping against a store wired via
    set_playbook_build_store.

Repo has NO pytest-asyncio — async route handlers are driven via
asyncio.run() (mirrors tests/test_audit_batch_v0275.py). The route
tests import api.playbook_builds, which imports `fastmcp`; that module
is absent from the local venv but present in CI's in-image build, so
each route test is marked skipif-no-fastmcp (and the route module is
imported lazily inside the fixture, never at collection time). The tool
round-trip tests need ONLY the store (no fastmcp) and run everywhere.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.builtin_components import playbook_tools as pt  # noqa: E402
from usecase.playbook_build_store import (  # noqa: E402
    PlaybookBuildStore,
    set_playbook_build_store,
)


@pytest.fixture()
def wired(tmp_path):
    """A real store wired via the singleton, the way the tools resolve it."""
    store = PlaybookBuildStore(db_path=str(tmp_path / "playbook_builds.db"))
    set_playbook_build_store(store)
    yield store
    set_playbook_build_store(None)


# ═════════════════════════════════════════════════════════════════
# MCP tool round-trip — store-only, runs locally (no fastmcp needed).
# ═════════════════════════════════════════════════════════════════


def test_tool_record_get_update_delete_round_trip(wired):
    # record → full dict incl. the YAML + created_by attribution.
    rec = pt.playbook_build_record(
        use_case="contain phishing",
        product="xsoar",
        playbook_name="Phish Containment",
        playbook_yaml="id: phish\nname: Phish\n",
        status="drafted",
    )
    assert "error" not in rec
    bid = rec["id"]
    assert rec["use_case"] == "contain phishing"
    assert rec["playbook_yaml"] == "id: phish\nname: Phish\n"
    assert rec["status"] == "drafted"
    # resolve_tool_actor() falls back to "agent" with no forwarded actor.
    assert rec["created_by"] == "agent"

    # get → full record (YAML present).
    got = pt.playbook_builds_get(bid)
    assert got["id"] == bid
    assert got["playbook_yaml"] == "id: phish\nname: Phish\n"

    # update → advance lifecycle + attach deploy detail.
    upd = pt.playbook_build_update(
        bid, status="deployed", deploy_summary="imported to xsoar v6",
        test_incident_id="9001",
    )
    assert upd["status"] == "deployed"
    assert upd["deploy_summary"] == "imported to xsoar v6"
    assert upd["test_incident_id"] == "9001"

    # delete → gone.
    out = pt.playbook_build_delete(bid)
    assert out == {"deleted": True, "build_id": bid}
    assert pt.playbook_builds_get(bid) == {"error": "not found", "build_id": bid}


def test_tool_list_compact_and_status_filter(wired):
    a = pt.playbook_build_record(use_case="a", playbook_yaml="y", status="drafted")["id"]
    pt.playbook_build_record(use_case="b", status="drafted")
    pt.playbook_build_update(a, status="deployed")

    listed = pt.playbook_builds_list()
    assert listed["count"] == 2
    # Compact view drops the large fields.
    for b in listed["builds"]:
        assert "playbook_yaml" not in b
        assert "deploy_summary" not in b

    only_deployed = pt.playbook_builds_list(status="deployed")
    assert only_deployed["count"] == 1
    assert only_deployed["builds"][0]["id"] == a


def test_tool_get_and_update_not_found(wired):
    assert pt.playbook_builds_get("nope") == {"error": "not found", "build_id": "nope"}
    assert pt.playbook_build_update("nope", status="deployed") == {
        "error": "not found", "build_id": "nope",
    }
    assert pt.playbook_build_delete("nope") == {"deleted": False, "build_id": "nope"}


def test_tools_error_when_store_unset():
    set_playbook_build_store(None)
    err = {"error": "playbook build store not initialized"}
    assert pt.playbook_builds_list() == err
    assert pt.playbook_builds_get("x") == err
    assert pt.playbook_build_record(use_case="x") == err
    assert pt.playbook_build_update("x", status="deployed") == err
    assert pt.playbook_build_delete("x") == err


# ═════════════════════════════════════════════════════════════════
# REST routes — need fastmcp (CI in-image build); skipped locally.
# ═════════════════════════════════════════════════════════════════

# api.playbook_builds does `from fastmcp import FastMCP` at module top,
# absent from the local venv but present in CI's in-image build. Probe
# for it WITHOUT importing the route module at collection time, so the
# tool round-trip tests above still run locally; only the route tests
# below are skipped when fastmcp is missing.
import importlib.util  # noqa: E402

_HAS_FASTMCP = importlib.util.find_spec("fastmcp") is not None
_needs_fastmcp = pytest.mark.skipif(
    not _HAS_FASTMCP, reason="fastmcp only present in CI in-image build",
)

from starlette.requests import Request  # noqa: E402


class _CapturingMcp:
    """Captures the handlers register_playbook_build_routes wires up so the
    test can invoke them directly (keyed by '<METHOD> <path>')."""

    def __init__(self) -> None:
        self.routes: dict[str, Any] = {}

    def custom_route(self, path: str, methods: list[str], **_kw: Any):
        def deco(fn):
            for m in methods:
                self.routes[f"{m} {path}"] = fn
            return fn

        return deco


def _make_request(
    method: str, path: str, *, build_id: str | None = None,
    query: bytes = b"", body: bytes = b"",
) -> Request:
    """Build a Starlette Request carrying the bearer (+ optional body)."""
    headers = [(b"authorization", b"Bearer test-mcp-token")]
    if body:
        headers.append((b"content-type", b"application/json"))
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": headers,
        "path_params": ({"build_id": build_id} if build_id is not None else {}),
        "query_string": query,
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


@pytest.fixture()
def routes(tmp_path, monkeypatch):
    """Wire the routes against a real store + pass the bearer check."""
    # Lazy import — api.playbook_builds pulls in fastmcp, absent locally.
    from api.playbook_builds import register_playbook_build_routes
    from config.config import config as cfg
    monkeypatch.setattr(cfg, "mcp_token", "test-mcp-token", raising=False)
    store = PlaybookBuildStore(db_path=str(tmp_path / "playbook_builds.db"))
    set_playbook_build_store(store)
    mcp = _CapturingMcp()
    register_playbook_build_routes(mcp, store)
    yield mcp, store
    set_playbook_build_store(None)


def _json_body(resp) -> Any:
    import json
    return json.loads(bytes(resp.body))


@_needs_fastmcp
def test_route_list_empty(routes):
    mcp, _store = routes
    handler = mcp.routes["GET /api/v1/playbook-builds"]
    resp = asyncio.run(handler(_make_request("GET", "/api/v1/playbook-builds")))
    assert resp.status_code == 200
    assert _json_body(resp) == {"builds": [], "count": 0}


@_needs_fastmcp
def test_route_create_then_list_and_status_filter(routes):
    mcp, _store = routes
    create = mcp.routes["POST /api/v1/playbook-builds"]
    resp = asyncio.run(create(_make_request(
        "POST", "/api/v1/playbook-builds",
        body=b'{"use_case": "contain phishing", "product": "xsoar", '
             b'"playbook_yaml": "id: p\\nname: P\\n"}',
    )))
    assert resp.status_code == 201
    created = _json_body(resp)
    bid = created["id"]
    assert created["use_case"] == "contain phishing"
    assert created["playbook_yaml"] == "id: p\nname: P\n"
    # No X-Guardian-Actor header → actor_from_request default.
    assert created["created_by"] == "user:operator"

    # A second build, deployed, so the status filter has something to narrow.
    resp2 = asyncio.run(create(_make_request(
        "POST", "/api/v1/playbook-builds", body=b'{"use_case": "b", "status": "deployed"}',
    )))
    assert resp2.status_code == 201

    listed = mcp.routes["GET /api/v1/playbook-builds"]
    resp3 = asyncio.run(listed(_make_request("GET", "/api/v1/playbook-builds")))
    payload = _json_body(resp3)
    assert payload["count"] == 2
    # List view is compact — no large fields.
    for b in payload["builds"]:
        assert "playbook_yaml" not in b
        assert "deploy_summary" not in b

    resp4 = asyncio.run(listed(_make_request(
        "GET", "/api/v1/playbook-builds", query=b"status=deployed",
    )))
    filtered = _json_body(resp4)
    assert filtered["count"] == 1
    assert filtered["builds"][0]["use_case"] == "b"


@_needs_fastmcp
def test_route_create_missing_use_case_400(routes):
    mcp, _store = routes
    create = mcp.routes["POST /api/v1/playbook-builds"]
    # Absent.
    resp = asyncio.run(create(_make_request(
        "POST", "/api/v1/playbook-builds", body=b'{"product": "xsoar"}',
    )))
    assert resp.status_code == 400
    assert "use_case" in _json_body(resp)["error"]
    # Empty / whitespace.
    resp2 = asyncio.run(create(_make_request(
        "POST", "/api/v1/playbook-builds", body=b'{"use_case": "   "}',
    )))
    assert resp2.status_code == 400


@_needs_fastmcp
def test_route_get_200_and_404(routes):
    mcp, _store = routes
    create = mcp.routes["POST /api/v1/playbook-builds"]
    created = _json_body(asyncio.run(create(_make_request(
        "POST", "/api/v1/playbook-builds",
        body=b'{"use_case": "x", "playbook_yaml": "id: x\\nname: X\\n"}',
    ))))
    bid = created["id"]

    get = mcp.routes["GET /api/v1/playbook-builds/{build_id}"]
    resp = asyncio.run(get(_make_request(
        "GET", f"/api/v1/playbook-builds/{bid}", build_id=bid,
    )))
    assert resp.status_code == 200
    full = _json_body(resp)
    assert full["id"] == bid
    # Full record carries the YAML.
    assert full["playbook_yaml"] == "id: x\nname: X\n"

    resp404 = asyncio.run(get(_make_request(
        "GET", "/api/v1/playbook-builds/nope", build_id="nope",
    )))
    assert resp404.status_code == 404
    assert _json_body(resp404) == {"error": "not found"}


@_needs_fastmcp
def test_route_patch_200_and_404(routes):
    mcp, _store = routes
    create = mcp.routes["POST /api/v1/playbook-builds"]
    bid = _json_body(asyncio.run(create(_make_request(
        "POST", "/api/v1/playbook-builds", body=b'{"use_case": "x"}',
    ))))["id"]

    patch = mcp.routes["PATCH /api/v1/playbook-builds/{build_id}"]
    resp = asyncio.run(patch(_make_request(
        "PATCH", f"/api/v1/playbook-builds/{bid}", build_id=bid,
        body=b'{"status": "deployed", "deploy_summary": "done", '
             b'"test_incident_id": "42"}',
    )))
    assert resp.status_code == 200
    upd = _json_body(resp)
    assert upd["status"] == "deployed"
    assert upd["deploy_summary"] == "done"
    assert upd["test_incident_id"] == "42"

    resp404 = asyncio.run(patch(_make_request(
        "PATCH", "/api/v1/playbook-builds/nope", build_id="nope",
        body=b'{"status": "deployed"}',
    )))
    assert resp404.status_code == 404
    assert _json_body(resp404) == {"error": "not found"}


@_needs_fastmcp
def test_route_delete_200_and_404(routes):
    mcp, _store = routes
    create = mcp.routes["POST /api/v1/playbook-builds"]
    bid = _json_body(asyncio.run(create(_make_request(
        "POST", "/api/v1/playbook-builds", body=b'{"use_case": "x"}',
    ))))["id"]

    delete = mcp.routes["DELETE /api/v1/playbook-builds/{build_id}"]
    resp = asyncio.run(delete(_make_request(
        "DELETE", f"/api/v1/playbook-builds/{bid}", build_id=bid,
    )))
    assert resp.status_code == 200
    assert _json_body(resp) == {"deleted": True}

    resp404 = asyncio.run(delete(_make_request(
        "DELETE", "/api/v1/playbook-builds/nope", build_id="nope",
    )))
    assert resp404.status_code == 404
    assert _json_body(resp404) == {"error": "not found"}
