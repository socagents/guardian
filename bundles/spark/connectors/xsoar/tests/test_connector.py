"""xsoar connector — unit tests.

No network. Two layers under test:

  1. _xsoar_client.XSOARFetcher — base-URL + header construction for
     BOTH generations:
       v6 (no api_id)  → base unchanged, no x-xdr-auth-id header.
       v8 (api_id set) → /xsoar/public/v1 prefix + x-xdr-auth-id header.
     The actual httpx call is monkeypatched so we assert the URL +
     headers + body the fetcher would send, never opening a socket.

  2. connector tool functions — the error-envelope wrapper, and the
     request-shaping of list_incidents / get_incident / close_incident
     (the Fetcher is monkeypatched to record the path + body and return
     a canned reply).

Run with:
  cd bundles/spark/connectors/xsoar && python3 -m pytest tests/ -x
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Optional

import pytest

# Make the connector package importable. Mirrors how the embedded MCP's
# connector_loader injects the bundle path at boot.
SRC_PARENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_PARENT))

from src import connector  # noqa: E402
from src._xsoar_client import (  # noqa: E402
    XSOARAuthError,
    XSOARError,
    XSOARFetcher,
    XSOARRateLimitError,
    XSOARRequestError,
    XSOARServerError,
)


def run(coro):
    """Drive an async coroutine to completion from a sync test."""
    return asyncio.run(coro)


# ─── Fake httpx plumbing (no sockets) ────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code: int, json_body: Any = None, text: str = ""):
        self.status_code = status_code
        self._json = json_body
        self.text = text
        # `content` truthiness gates the empty-body branch in _parse.
        self.content = b"x" if json_body is not None else b""

    def json(self):
        if self._json is None:
            import json as _json
            raise _json.JSONDecodeError("no json", "", 0)
        return self._json


class _FakeAsyncClient:
    """Records the last request + returns a queued response.

    Captures `verify` (TLS toggle) at construction and the post/get
    args so tests can assert URL + headers + body without a network.
    """

    last: dict = {}

    def __init__(self, *args, **kwargs):
        _FakeAsyncClient.last["verify"] = kwargs.get("verify")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None):
        _FakeAsyncClient.last.update(
            {"method": "POST", "url": url, "headers": headers, "json": json}
        )
        return _FakeAsyncClient.queued

    async def get(self, url, headers=None, params=None):
        _FakeAsyncClient.last.update(
            {"method": "GET", "url": url, "headers": headers, "params": params}
        )
        return _FakeAsyncClient.queued


def _patch_httpx(monkeypatch, response: _FakeResponse):
    """Point the client's httpx.AsyncClient at the fake + queue a response."""
    import src._xsoar_client as client_mod

    _FakeAsyncClient.queued = response
    _FakeAsyncClient.last = {}
    monkeypatch.setattr(client_mod.httpx, "AsyncClient", _FakeAsyncClient)


# ═══════════════════════════════════════════════════════════════════
# 1. XSOARFetcher — dual-generation base-URL + headers
# ═══════════════════════════════════════════════════════════════════


def test_v6_no_prefix_no_auth_id_header(monkeypatch):
    """v6: api_id None → base unchanged, NO x-xdr-auth-id, NO prefix."""
    _patch_httpx(monkeypatch, _FakeResponse(200, {"ok_field": 1}))
    f = XSOARFetcher("https://xsoar.example.com/", "KEY6", api_id=None)
    assert f.is_v8 is False

    out = run(f.post("/incidents/search", {"filter": {"size": 1}}))
    assert out == {"ok_field": 1}

    sent = _FakeAsyncClient.last
    assert sent["url"] == "https://xsoar.example.com/incidents/search"
    assert sent["headers"]["Authorization"] == "KEY6"
    assert "x-xdr-auth-id" not in sent["headers"]
    assert sent["headers"]["Content-Type"] == "application/json"
    assert sent["json"] == {"filter": {"size": 1}}


def test_v8_prefix_and_auth_id_header(monkeypatch):
    """v8: api_id set → /xsoar/public/v1 prefix + x-xdr-auth-id header."""
    _patch_httpx(monkeypatch, _FakeResponse(200, {"total": 0, "data": []}))
    f = XSOARFetcher(
        "https://api-tenant.xdr.us.paloaltonetworks.com",
        "KEY8",
        api_id="42",
    )
    assert f.is_v8 is True

    out = run(f.post("/incidents/search", {"filter": {}}))
    assert out == {"total": 0, "data": []}

    sent = _FakeAsyncClient.last
    assert sent["url"] == (
        "https://api-tenant.xdr.us.paloaltonetworks.com"
        "/xsoar/public/v1/incidents/search"
    )
    assert sent["headers"]["Authorization"] == "KEY8"
    assert sent["headers"]["x-xdr-auth-id"] == "42"


def test_v8_empty_api_id_is_treated_as_v6(monkeypatch):
    """An empty-string api_id (blank form field) must NOT switch to v8."""
    _patch_httpx(monkeypatch, _FakeResponse(200, {}))
    f = XSOARFetcher("https://xsoar.example.com", "K", api_id="")
    assert f.is_v8 is False
    run(f.get("/health"))
    sent = _FakeAsyncClient.last
    assert sent["url"] == "https://xsoar.example.com/health"
    assert "x-xdr-auth-id" not in sent["headers"]


def test_v8_does_not_double_prefix(monkeypatch):
    """If a caller passes an already-prefixed path, v8 must not double it."""
    _patch_httpx(monkeypatch, _FakeResponse(200, {}))
    f = XSOARFetcher("https://api-x.example.com", "K", api_id="7")
    run(f.post("/xsoar/public/v1/incidents/search", {}))
    sent = _FakeAsyncClient.last
    assert sent["url"] == "https://api-x.example.com/xsoar/public/v1/incidents/search"


def test_version_v8_explicit_sets_prefix_and_auth_id(monkeypatch):
    """version='v8' (with api_id) → is_v8, /xsoar/public/v1 prefix, x-xdr-auth-id."""
    _patch_httpx(monkeypatch, _FakeResponse(200, {"total": 0, "data": []}))
    f = XSOARFetcher(
        "https://api-tenant.xdr.us.paloaltonetworks.com",
        "KEY8",
        api_id="42",
        version="v8",
    )
    assert f.is_v8 is True

    run(f.post("/incidents/search", {"filter": {}}))
    sent = _FakeAsyncClient.last
    assert sent["url"] == (
        "https://api-tenant.xdr.us.paloaltonetworks.com"
        "/xsoar/public/v1/incidents/search"
    )
    assert sent["headers"]["x-xdr-auth-id"] == "42"


def test_version_v6_overrides_api_id_inference(monkeypatch):
    """version='v6' with api_id ALSO set → v6: NO prefix, NO x-xdr-auth-id.

    Explicit version pins the generation, overriding the legacy
    api_id-presence inference even though an api_id is configured.
    """
    _patch_httpx(monkeypatch, _FakeResponse(200, {}))
    f = XSOARFetcher(
        "https://xsoar.example.com",
        "KEY6",
        api_id="42",
        version="v6",
    )
    assert f.is_v8 is False

    run(f.post("/incidents/search", {"filter": {}}))
    sent = _FakeAsyncClient.last
    assert sent["url"] == "https://xsoar.example.com/incidents/search"
    assert "x-xdr-auth-id" not in sent["headers"]


def test_version_unset_with_api_id_infers_v8(monkeypatch):
    """version unset + api_id set → v8 (inference fallback unchanged)."""
    _patch_httpx(monkeypatch, _FakeResponse(200, {}))
    f = XSOARFetcher("https://api-x.example.com", "K", api_id="9")
    assert f.is_v8 is True
    run(f.post("/incidents/search", {}))
    sent = _FakeAsyncClient.last
    assert sent["url"] == "https://api-x.example.com/xsoar/public/v1/incidents/search"
    assert sent["headers"]["x-xdr-auth-id"] == "9"


def test_version_unset_blank_api_id_infers_v6(monkeypatch):
    """version unset + api_id blank → v6 (inference fallback)."""
    _patch_httpx(monkeypatch, _FakeResponse(200, {}))
    f = XSOARFetcher("https://xsoar.example.com", "K", api_id="", version=None)
    assert f.is_v8 is False
    run(f.post("/incidents/search", {}))
    sent = _FakeAsyncClient.last
    assert sent["url"] == "https://xsoar.example.com/incidents/search"
    assert "x-xdr-auth-id" not in sent["headers"]


def test_verify_ssl_passed_to_client(monkeypatch):
    """verify_ssl=False must reach httpx.AsyncClient(verify=...)."""
    _patch_httpx(monkeypatch, _FakeResponse(200, {}))
    f = XSOARFetcher("https://xsoar.example.com", "K", verify_ssl=False)
    run(f.get("/health"))
    assert _FakeAsyncClient.last["verify"] is False


def test_get_request_shape(monkeypatch):
    """GET applies the same prefix/header rules as POST."""
    _patch_httpx(monkeypatch, _FakeResponse(200, [{"cliName": "x"}]))
    f = XSOARFetcher("https://api-x.example.com", "K", api_id="9")
    out = run(f.get("/incidentfields/associatedTypes/Phishing"))
    # bare-array body is normalized into {"data": [...]}.
    assert out == {"data": [{"cliName": "x"}]}
    sent = _FakeAsyncClient.last
    assert sent["method"] == "GET"
    assert sent["url"] == (
        "https://api-x.example.com"
        "/xsoar/public/v1/incidentfields/associatedTypes/Phishing"
    )


# ─── Status-code → typed exception mapping ───────────────────────────


@pytest.mark.parametrize(
    "code,exc",
    [
        (401, XSOARAuthError),
        (403, XSOARAuthError),
        (429, XSOARRateLimitError),
        (500, XSOARServerError),
        (503, XSOARServerError),
        (404, XSOARRequestError),
        (409, XSOARRequestError),
        (400, XSOARRequestError),
    ],
)
def test_status_code_maps_to_typed_exception(monkeypatch, code, exc):
    _patch_httpx(monkeypatch, _FakeResponse(code, None, text="boom"))
    f = XSOARFetcher("https://xsoar.example.com", "K")
    with pytest.raises(exc):
        run(f.post("/incidents/search", {}))


def test_network_error_becomes_xsoar_error(monkeypatch):
    """An httpx transport error surfaces as the base XSOARError."""
    import src._xsoar_client as client_mod

    class _Boom:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *e):
            return False

        async def post(self, *a, **k):
            raise client_mod.httpx.ConnectError("refused")

    monkeypatch.setattr(client_mod.httpx, "AsyncClient", _Boom)
    f = XSOARFetcher("https://xsoar.example.com", "K")
    with pytest.raises(XSOARError):
        run(f.post("/x", {}))


# ═══════════════════════════════════════════════════════════════════
# 2. Connector tools — request shaping + error envelope
# ═══════════════════════════════════════════════════════════════════


class _RecordingFetcher:
    """Stand-in for XSOARFetcher that records calls + returns canned data."""

    def __init__(self, post_reply: Optional[dict] = None,
                 get_reply: Optional[dict] = None, is_v8: bool = False,
                 multipart_reply: Optional[dict] = None,
                 multipart_exc: Optional[Exception] = None):
        self.post_reply = post_reply if post_reply is not None else {}
        self.get_reply = get_reply if get_reply is not None else {}
        self.is_v8 = is_v8
        self.multipart_reply = multipart_reply
        self.multipart_exc = multipart_exc
        self.calls: list[tuple[str, str, Any]] = []

    async def post(self, path, body=None, **kw):
        self.calls.append(("POST", path, body))
        return self.post_reply

    async def get(self, path, **kw):
        self.calls.append(("GET", path, kw.get("params")))
        return self.get_reply

    async def post_multipart(self, path, files, **kw):
        self.calls.append(("POST_MULTIPART", path, files))
        if self.multipart_exc is not None:
            raise self.multipart_exc
        return self.multipart_reply if self.multipart_reply is not None else self.post_reply


def _install_fetcher(monkeypatch, fetcher: _RecordingFetcher):
    monkeypatch.setattr(connector, "_get_fetcher", lambda: fetcher)


class _ScriptedFetcher:
    """Fake fetcher whose post/get replies are keyed by path suffix.

    The command engine posts to /entry (DeleteContext), /entry/execute/sync
    (run), and /investigation/{id}/context (retrieve) in one call — a single
    canned reply can't serve them. Match by exact path or path suffix.
    """

    def __init__(self, replies: dict, get_replies: Optional[dict] = None, is_v8: bool = False):
        self.replies = replies
        self.get_replies = get_replies or {}
        self.is_v8 = is_v8
        self.calls: list[tuple[str, str, Any]] = []

    def _match(self, table: dict, path: str):
        if path in table:
            return table[path]
        for key, val in table.items():
            if path.endswith(key):
                return val
        return {}

    async def post(self, path, body=None, **kw):
        self.calls.append(("POST", path, body))
        return self._match(self.replies, path)

    async def get(self, path, **kw):
        self.calls.append(("GET", path, kw.get("params")))
        return self._match(self.get_replies, path)


# ─── list_incidents ──────────────────────────────────────────────────


def test_list_incidents_request_shape(monkeypatch):
    rf = _RecordingFetcher(post_reply={
        "total": 2,
        "data": [
            {"id": "1", "name": "Phish", "type": "Phishing", "severity": 3,
             "status": 1, "owner": "alice", "created": "t0", "modified": "t1"},
            {"id": "2", "name": "Mal", "type": "Malware", "severity": 4,
             "status": 1, "owner": "bob", "created": "t2", "modified": "t3"},
        ],
    })
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_list_incidents(status=[1], severity=[3, 4], page_size=10))
    assert out["ok"] is True
    assert out["total"] == 2
    assert len(out["incidents"]) == 2
    assert out["incidents"][0] == {
        "id": "1", "name": "Phish", "type": "Phishing", "severity": 3,
        "status": 1, "owner": "alice", "created": "t0", "modified": "t1",
    }

    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/incidents/search")
    filt = body["filter"]
    assert filt["status"] == [1]
    assert filt["level"] == [3, 4]          # severity → level
    assert filt["size"] == 10
    assert filt["sort"] == [
        {"field": "created", "asc": False, "fieldType": "date"}
    ]


def test_list_incidents_scalar_status_is_wrapped(monkeypatch):
    """A bare scalar status must be wrapped into a list."""
    rf = _RecordingFetcher(post_reply={"total": 0, "data": []})
    _install_fetcher(monkeypatch, rf)
    run(connector.xsoar_list_incidents(status=1))
    assert rf.calls[0][2]["filter"]["status"] == [1]


def test_list_incidents_clamps_page_size(monkeypatch):
    """page_size over the cap clamps to 200; None degrades to default 50."""
    rf = _RecordingFetcher(post_reply={"total": 0, "data": []})
    _install_fetcher(monkeypatch, rf)
    run(connector.xsoar_list_incidents(page_size=9999))
    assert rf.calls[0][2]["filter"]["size"] == 200
    rf.calls.clear()
    run(connector.xsoar_list_incidents(page_size=None))  # runtime passes None
    assert rf.calls[0][2]["filter"]["size"] == 50


# ─── get_incident ────────────────────────────────────────────────────


def test_get_incident_uses_search_filter_id(monkeypatch):
    rf = _RecordingFetcher(post_reply={"data": [{"id": "55", "version": 7}]})
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_get_incident("55"))
    assert out["ok"] is True
    assert out["incident"] == {"id": "55", "version": 7}

    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/incidents/search")
    assert body["filter"]["id"] == ["55"]
    assert body["filter"]["size"] == 1


def test_get_incident_not_found_returns_error(monkeypatch):
    rf = _RecordingFetcher(post_reply={"data": []})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_get_incident("999"))
    assert out["ok"] is False
    assert "not found" in out["error"]


# ─── close_incident ──────────────────────────────────────────────────


def test_close_incident_per_id_shape(monkeypatch):
    rf = _RecordingFetcher(post_reply={"closed": True})
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_close_incident(
        incident_ids=["10", "11"],
        close_reason="Resolved",
        close_notes="benign",
    ))
    assert out["ok"] is True
    assert out["closed_count"] == 2
    assert out["incident_ids"] == ["10", "11"]

    # one POST /incident/close per id (no batchClose — not on Cortex 8)
    assert [(m, p) for (m, p, _b) in rf.calls] == [
        ("POST", "/incident/close"),
        ("POST", "/incident/close"),
    ]
    assert rf.calls[0][2] == {"id": "10", "closeReason": "Resolved", "closeNotes": "benign"}
    assert rf.calls[1][2]["id"] == "11"


def test_close_incident_wraps_bare_id(monkeypatch):
    rf = _RecordingFetcher(post_reply={})
    _install_fetcher(monkeypatch, rf)
    run(connector.xsoar_close_incident(incident_ids="77", close_reason="Other"))
    assert rf.calls[0][1] == "/incident/close"
    assert rf.calls[0][2]["id"] == "77"


def test_close_incident_requires_reason(monkeypatch):
    rf = _RecordingFetcher(post_reply={})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_close_incident(incident_ids=["1"], close_reason=""))
    assert out["ok"] is False
    assert "close_reason" in out["error"]


# ─── update_incident — version requirement ───────────────────────────


def test_update_incident_reads_then_posts_full_object(monkeypatch):
    # post_reply serves both calls: the read (.get("data")) and the
    # final upsert (.get("id")/.get("version")).
    rf = _RecordingFetcher(post_reply={
        "data": [{"id": "5", "version": 7, "labels": [{"type": "X", "value": "y"}],
                  "name": "case", "severity": 1}],
        "id": "5", "version": 8,
    })
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_update_incident(
        incident_id="5", version=7, severity=4, owner="alice",
        labels=[{"type": "New", "value": "lbl"}],
        custom_fields={"detectionsource": "Guardian"},
    ))
    assert out["ok"] is True and out["updated"] is True
    # first call reads the full incident, last call upserts /incident
    assert rf.calls[0][0:2] == ("POST", "/incidents/search")
    assert rf.calls[0][2] == {"filter": {"id": ["5"]}}
    method, path, body = rf.calls[-1]
    assert (method, path) == ("POST", "/incident")
    assert body["id"] == "5"
    assert body["version"] == 7
    assert body["severity"] == 4
    assert body["owner"] == "alice"
    # existing label preserved + new one appended
    assert {"type": "X", "value": "y"} in body["labels"]
    assert {"type": "New", "value": "lbl"} in body["labels"]
    assert body["CustomFields"] == {"detectionsource": "Guardian"}


# ─── add_note — two-step (entry then pin) ────────────────────────────


def test_add_note_pins_created_entry(monkeypatch):
    rf = _RecordingFetcher(post_reply={"id": "entry-1", "version": 3})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_add_note("5", "conclusion"))
    assert out["ok"] is True and out["note"] is True and out["entry_id"] == "entry-1"
    # Two POSTs: /entry then /entry/note carrying the entry id + version.
    assert rf.calls[0][1] == "/entry"
    assert rf.calls[1][1] == "/entry/note"
    note_body = rf.calls[1][2]
    assert note_body["id"] == "entry-1"
    assert note_body["version"] == 3
    assert note_body["note"] is True


# ─── error envelope (auth + config) ──────────────────────────────────


def test_tool_maps_auth_error_to_envelope(monkeypatch):
    class _AuthFetcher:
        async def post(self, *a, **k):
            raise XSOARAuthError("HTTP 401 (auth failed)")

    monkeypatch.setattr(connector, "_get_fetcher", lambda: _AuthFetcher())
    out = run(connector.xsoar_list_incidents())
    assert out["ok"] is False
    assert out["is_auth_error"] is True
    assert "auth failed" in out["error"]


def test_tool_maps_config_valueerror_to_envelope(monkeypatch):
    def _boom():
        raise ValueError("xsoar instance has no api_url configured")

    monkeypatch.setattr(connector, "_get_fetcher", _boom)
    out = run(connector.xsoar_get_incident("1"))
    assert out["ok"] is False
    assert "api_url" in out["error"]


def test_health_check_reports_generation(monkeypatch):
    rf = _RecordingFetcher(post_reply={"total": 42, "data": []}, is_v8=True)
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_health_check())
    assert out["ok"] is True
    assert out["reachable"] is True
    assert out["generation"] == "v8"
    assert out["total_incidents"] == 42
    # probe is a minimal incidents/search, NOT a /health GET
    assert rf.calls[0] == ("POST", "/incidents/search", {"filter": {"page": 0, "size": 1}})


# ═══════════════════════════════════════════════════════════════════
# 3. Action toolset (v0.2.0) — command engine, Lists, lifecycle
# ═══════════════════════════════════════════════════════════════════


# ─── playground_id resolver ──────────────────────────────────────────


def test_get_playground_id_returns_configured_value(monkeypatch):
    monkeypatch.setattr(
        connector, "_get_xsoar_config",
        lambda: {"api_url": "u", "api_key": "k", "api_id": None,
                 "verify_ssl": True, "playground_id": "PG-1"},
    )
    assert connector._get_playground_id() == "PG-1"


def test_get_playground_id_missing_raises_valueerror(monkeypatch):
    monkeypatch.setattr(
        connector, "_get_xsoar_config",
        lambda: {"api_url": "u", "api_key": "k", "api_id": None,
                 "verify_ssl": True, "playground_id": None},
    )
    with pytest.raises(ValueError) as ei:
        connector._get_playground_id()
    assert "playground_id" in str(ei.value)


# ─── _parse_war_room_entries ─────────────────────────────────────────


def test_parse_war_room_includes_type1_contents():
    """type==1 (standard note) entries are INCLUDED (ref skipped them — bug)."""
    resp = {"data": [{"type": 1, "contents": "hello"}]}
    assert connector._parse_war_room_entries(resp) == "hello"


def test_parse_war_room_marks_type4_error():
    resp = {"data": [{"type": 4, "contents": "boom"}, {"type": 1, "contents": "ok"}]}
    out = connector._parse_war_room_entries(resp)
    assert "Error: boom" in out and "ok" in out


def test_parse_war_room_serializes_dict_contents():
    resp = {"data": [{"type": 1, "contents": {"k": "v"}}]}
    assert '"k": "v"' in connector._parse_war_room_entries(resp)


def test_parse_war_room_empty_is_friendly():
    assert connector._parse_war_room_entries({"data": []}) == (
        "Command executed (no text output returned)."
    )


# ─── _execute_command ────────────────────────────────────────────────


def test_execute_command_no_context_keys():
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "printed"}]},
    })
    out = run(connector._execute_command(f, "PG-1", "!Print value=printed"))
    assert out == {"output": "printed"}
    # one POST: execute/sync with the playground id + command
    assert f.calls == [("POST", "/entry/execute/sync",
                        {"investigationId": "PG-1", "data": "!Print value=printed"})]


def test_execute_command_with_context_keys_clears_and_retrieves():
    f = _ScriptedFetcher(replies={
        "/entry": {"ok": 1},                                   # DeleteContext
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "ran"}]},
        "/context": {"score": 3},                              # context retrieval
    })
    out = run(connector._execute_command(f, "PG-1", "!ip ip=\"8.8.8.8\"", "IP,DBotScore"))
    assert out["output"] == "ran"
    assert out["context"] == {"IP": {"score": 3}, "DBotScore": {"score": 3}}
    paths = [p for (_m, p, _b) in f.calls]
    # 2 DeleteContext + 1 execute + 2 context = 5 posts
    assert paths.count("/entry") == 2
    assert "/entry/execute/sync" in paths
    assert paths.count("/investigation/PG-1/context") == 2
    # context query uses the literal ${Key} syntax
    ctx_calls = [b for (_m, p, b) in f.calls if p == "/investigation/PG-1/context"]
    assert ctx_calls[0] == {"query": "${IP}"}


def test_execute_command_playground_not_found_raises_valueerror():
    class _NoInv:
        is_v8 = False
        calls: list = []
        async def post(self, path, body=None, **kw):
            from src._xsoar_client import XSOARRequestError
            raise XSOARRequestError("HTTP 400: noInv — investigation not found")
    with pytest.raises(ValueError) as ei:
        run(connector._execute_command(_NoInv(), "BAD", "!Print value=x"))
    assert "BAD" in str(ei.value) and "not found" in str(ei.value)


# ─── run_command ─────────────────────────────────────────────────────


def test_run_command_executes_in_playground(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "printed"}]},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)

    out = run(connector.xsoar_run_command("!Print value=printed"))
    assert out["ok"] is True
    assert out["output"] == "printed"
    assert f.calls[0] == ("POST", "/entry/execute/sync",
                          {"investigationId": "PG-1", "data": "!Print value=printed"})


def test_run_command_requires_command(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    out = run(connector.xsoar_run_command(""))
    assert out["ok"] is False and "command" in out["error"]


def test_run_command_missing_playground_returns_envelope(monkeypatch):
    def _boom():
        raise ValueError("playground_id is not configured on this XSOAR instance.")
    monkeypatch.setattr(connector, "_get_playground_id", _boom)
    out = run(connector.xsoar_run_command("!Print value=x"))
    assert out["ok"] is False and "playground_id" in out["error"]


# ─── enrich_indicator ────────────────────────────────────────────────


def test_enrich_indicator_ip_builds_command_and_keys(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    f = _ScriptedFetcher(replies={
        "/entry": {},
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "done"}]},
        "/context": {"v": 1},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)

    out = run(connector.xsoar_enrich_indicator("IP", "8.8.8.8"))
    assert out["ok"] is True
    assert out["indicator_type"] == "ip" and out["value"] == "8.8.8.8"
    # command quotes the value; context keys come from the cmd_map
    exec_call = [b for (_m, p, b) in f.calls if p == "/entry/execute/sync"][0]
    assert exec_call["data"] == '!ip ip="8.8.8.8"'
    assert "IP" in out["context"] and "DBotScore" in out["context"]


def test_enrich_indicator_unknown_type_returns_envelope(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    out = run(connector.xsoar_enrich_indicator("banana", "x"))
    assert out["ok"] is False and "unsupported indicator_type" in out["error"]


# ─── complete_task ───────────────────────────────────────────────────


def test_complete_task_builds_taskcomplete_command(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "Task completed"}]},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)

    out = run(connector.xsoar_complete_task(incident_id="42", task_id="7", comment="done by guardian"))
    assert out["ok"] is True
    assert out["incident_id"] == "42" and out["task_id"] == "7"
    exec_call = [b for (_m, p, b) in f.calls if p == "/entry/execute/sync"][0]
    assert exec_call["data"] == '!taskComplete id=7 incidentId=42 comment="done by guardian"'


def test_complete_task_requires_ids(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    out = run(connector.xsoar_complete_task(incident_id="", task_id="7"))
    assert out["ok"] is False and "incident_id" in out["error"]


# ─── get_list / set_list / append_to_list ────────────────────────────


# Lists route through the command engine (!getList read / !createList write)
# on Cortex 8 — the v6 GET /lists/ REST endpoint 500s there. They need
# playground_id. Issue #45: writes use !createList (create-or-overwrite); the
# old !setList only updated EXISTING lists and masked failures as ok=True.

_GETLIST_OK = "Done: list bl was succesfully loaded:\n\n1.1.1.1"


def test_get_list_via_command(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {
            "data": [{"type": 1, "contents": "Done: list blocklist was succesfully loaded:\n\n2.2.2.2"}]
        },
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)
    out = run(connector.xsoar_get_list("blocklist"))
    assert out["ok"] is True and out["name"] == "blocklist" and out["data"] == "2.2.2.2"
    # ran !getList in the playground
    exec_call = [b for (_m, p, b) in f.calls if p == "/entry/execute/sync"][0]
    assert exec_call == {"investigationId": "PG-1", "data": '!getList listName="blocklist"'}


def test_get_list_not_found(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 4, "contents": "list nope does not exist"}]},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)
    out = run(connector.xsoar_get_list("nope"))
    assert out["ok"] is False and "not found" in out["error"]


def test_set_list_via_command(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "Done: list blocklist was updated"}]},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)
    out = run(connector.xsoar_set_list("blocklist", "1.1.1.1\n2.2.2.2"))
    assert out["ok"] is True and out["name"] == "blocklist"
    exec_call = [b for (_m, p, b) in f.calls if p == "/entry/execute/sync"][0]
    # issue #45: writes use !createList (create-or-overwrite), not !setList.
    assert exec_call["data"] == '!createList listName="blocklist" listData="1.1.1.1\n2.2.2.2"'


def test_set_list_reports_error_on_failure(monkeypatch):
    # issue #45 regression: a command that returns "Error: Item not found"
    # must surface as ok=False — not the previous silent ok=True.
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {
            "data": [{"type": 4, "contents": "Error: Item not found (8) on list [bl]"}]
        },
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)
    out = run(connector.xsoar_set_list("bl", "x"))
    assert out["ok"] is False and "could not create" in out["error"]


def test_append_to_list_via_command(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 1, "contents": _GETLIST_OK}]},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)
    out = run(connector.xsoar_append_to_list("bl", "2.2.2.2"))
    assert out["ok"] is True and out["data"] == "1.1.1.1\n2.2.2.2"
    # two execute calls: !getList then !setList with the merged data
    datas = [b["data"] for (_m, p, b) in f.calls if p == "/entry/execute/sync"]
    assert datas[0] == '!getList listName="bl"'
    assert datas[1] == '!createList listName="bl" listData="1.1.1.1\n2.2.2.2"'


def test_append_to_list_creates_when_absent(monkeypatch):
    monkeypatch.setattr(connector, "_get_playground_id", lambda: "PG-1")
    # The path-keyed fake serves both calls (!getList then !createList) the same
    # reply. A "Done: ... was updated" entry has no "loaded:" read-marker, so
    # _parse_getlist_output treats getList as no-current-data (current=None →
    # new_data="first"); and it's not an error, so the createList write succeeds.
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "Done: list new was updated"}]},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)
    out = run(connector.xsoar_append_to_list("new", "first"))
    assert out["ok"] is True and out["data"] == "first"
    # the WRITE went through !createList, not !setList
    datas = [b["data"] for (_m, p, b) in f.calls if p == "/entry/execute/sync"]
    assert datas[-1] == '!createList listName="new" listData="first"'


# ─── create_incident / run_playbook ──────────────────────────────────


def test_create_incident_assembles_body(monkeypatch):
    rf = _RecordingFetcher(post_reply={"id": "100", "version": 1})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_create_incident(
        name="guardian smoke", incident_type="Phishing", severity=3,
        details="seen in email", owner="alice",
        labels=["src:guardian"], custom_fields={"detectionsource": "Guardian"},
    ))
    assert out["ok"] is True and out["incident_id"] == "100"
    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/incident")
    assert body["name"] == "guardian smoke"
    assert body["type"] == "Phishing"
    assert body["severity"] == 3
    assert body["createInvestigation"] is True
    assert {"type": "Label", "value": "src:guardian"} in body["labels"]
    assert body["CustomFields"] == {"detectionsource": "Guardian"}


def test_create_incident_requires_name(monkeypatch):
    rf = _RecordingFetcher(post_reply={})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_create_incident(name=""))
    assert out["ok"] is False and "name" in out["error"]


def test_create_incident_omits_unset_fields(monkeypatch):
    rf = _RecordingFetcher(post_reply={"id": "101"})
    _install_fetcher(monkeypatch, rf)
    run(connector.xsoar_create_incident(name="bare"))
    body = rf.calls[0][2]
    assert "type" not in body and "severity" not in body and "owner" not in body
    assert body == {"name": "bare", "createInvestigation": True}


def test_run_playbook_setplaybook_in_incident_warroom(monkeypatch):
    # !setPlaybook runs in the INCIDENT's own war room (investigationId=incident_id),
    # NOT the playground — so no playground_id needed.
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "done"}]},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)
    out = run(connector.xsoar_run_playbook(incident_id="42", playbook_id="Phishing Investigation"))
    assert out["ok"] is True
    assert out["incident_id"] == "42" and out["playbook_id"] == "Phishing Investigation"
    exec_call = [b for (_m, p, b) in f.calls if p == "/entry/execute/sync"][0]
    assert exec_call == {"investigationId": "42", "data": '!setPlaybook name="Phishing Investigation"'}


def test_run_playbook_not_found_surfaces_error(monkeypatch):
    f = _ScriptedFetcher(replies={
        "/entry/execute/sync": {"data": [{"type": 4, "contents": "Playbook named bogus was not found (53)"}]},
    })
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)
    out = run(connector.xsoar_run_playbook(incident_id="42", playbook_id="bogus"))
    assert out["ok"] is False and "not found" in out["error"]


def test_run_playbook_requires_ids(monkeypatch):
    monkeypatch.setattr(connector, "_get_fetcher", lambda: _ScriptedFetcher(replies={}))
    out = run(connector.xsoar_run_playbook(incident_id="42", playbook_id=""))
    assert out["ok"] is False and "playbook_id" in out["error"]


# ─── public surface ──────────────────────────────────────────────────


def test_all_exported_tools_are_callable():
    expected = {
        "xsoar_list_incidents",
        "xsoar_get_incident",
        "xsoar_get_war_room",
        "xsoar_add_entry",
        "xsoar_add_note",
        "xsoar_update_incident",
        "xsoar_close_incident",
        "xsoar_list_incident_types",
        "xsoar_get_incident_fields",
        "xsoar_search_indicators",
        "xsoar_create_indicator",
        "xsoar_update_indicator",
        "xsoar_save_evidence",
        "xsoar_search_evidence",
        "xsoar_health_check",
        "xsoar_list_integrations",
        "xsoar_get_integration_status",
        "xsoar_test_integration_instance",
        "xsoar_get_integration_fetch_history",
        "xsoar_run_command",
        "xsoar_enrich_indicator",
        "xsoar_complete_task",
        "xsoar_get_list",
        "xsoar_set_list",
        "xsoar_append_to_list",
        "xsoar_create_incident",
        "xsoar_list_playbooks",
        "xsoar_get_playbook",
        "xsoar_run_playbook",
        "xsoar_get_playbook_state",
        "xsoar_import_playbook",
    }
    assert set(connector.__all__) == expected
    for name in expected:
        assert callable(getattr(connector, name)), f"{name} not callable"


# ─── list_integrations ───────────────────────────────────────────────

# Mirrors the real POST /settings/integration/search shape: `configurations`
# (definitions, holding integrationScript.commands) + `instances` (configured;
# `enabled` is the STRING "true"/"false").
_INTEGRATION_SEARCH_REPLY = {
    "configurations": [
        {"brand": "VirusTotal", "name": "VirusTotal", "integrationScript": {"commands": [
            {"name": "file", "description": "Check file reputation",
             "arguments": [{"name": "file", "required": True, "description": "hash"}]},
            {"name": "url", "description": "Check url reputation", "arguments": []},
        ]}},
        {"brand": "Splunk", "name": "Splunk", "integrationScript": {"commands": [
            {"name": "splunk-search", "description": "Run a search",
             "arguments": [{"name": "query", "required": True, "description": "spl"}]},
        ]}},
    ],
    "instances": [
        {"brand": "VirusTotal", "name": "VT_prod", "enabled": "true",
         "category": "Data Enrichment & Threat Intelligence"},
        {"brand": "Splunk", "name": "splunk_old", "enabled": "false", "category": "SIEM"},
    ],
}


def test_list_integrations_enabled_only_joins_commands(monkeypatch):
    rf = _RecordingFetcher(post_reply=_INTEGRATION_SEARCH_REPLY)
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_list_integrations())
    assert out["ok"] is True
    # Only the enabled instance (VT) — Splunk is disabled ("false").
    assert out["total"] == 1
    vt = out["integrations"][0]
    assert vt["brand"] == "VirusTotal"
    assert vt["instance_name"] == "VT_prod"
    assert vt["enabled"] is True
    assert vt["command_count"] == 2
    names = {c["name"] for c in vt["commands"]}
    assert names == {"file", "url"}
    # compact default: no arguments without command_detail
    assert "arguments" not in vt["commands"][0]

    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/settings/integration/search")
    assert isinstance(body.get("size"), int)


def test_list_integrations_brand_filter_includes_args(monkeypatch):
    rf = _RecordingFetcher(post_reply=_INTEGRATION_SEARCH_REPLY)
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_list_integrations(brand="virustotal"))
    assert out["total"] == 1
    cmds = {c["name"]: c for c in out["integrations"][0]["commands"]}
    # brand filter implies command_detail → arguments present
    assert cmds["file"]["arguments"][0] == {
        "name": "file", "required": True, "description": "hash",
    }


def test_list_integrations_enabled_only_false_lists_disabled(monkeypatch):
    rf = _RecordingFetcher(post_reply=_INTEGRATION_SEARCH_REPLY)
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_list_integrations(enabled_only=False))
    assert out["total"] == 2
    by_name = {i["instance_name"]: i for i in out["integrations"]}
    assert by_name["splunk_old"]["enabled"] is False
    assert by_name["splunk_old"]["command_count"] == 1  # joined from Splunk def


def test_list_integrations_include_commands_false_is_name_only(monkeypatch):
    rf = _RecordingFetcher(post_reply=_INTEGRATION_SEARCH_REPLY)
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_list_integrations(include_commands=False))
    assert out["total"] == 1
    assert "commands" not in out["integrations"][0]
    assert "command_count" not in out["integrations"][0]


# ─── get_integration_status / test_integration_instance (v0.2.42) ─────

# POST /settings/integration/search response carrying the `health` block —
# a map keyed per instance with {brand, instance:<name>, lastError, modified}.
# A non-empty lastError == that instance's fetch/test is failing.
_HEALTH_SEARCH_REPLY = {
    "instances": [
        {"brand": "Splunk", "name": "splunk_prod", "enabled": "true",
         "modified": "t-inst", "data": [{"name": "host", "value": "guardian-host"}]},
        {"brand": "VirusTotal", "name": "VT_prod", "enabled": "true"},
        {"brand": "Splunk", "name": "splunk_old", "enabled": "false"},
    ],
    "health": {
        "id-1": {"brand": "Splunk", "instance": "splunk_prod",
                 "lastError": "Could not fetch Splunk time", "modified": "t-health"},
        "id-2": {"brand": "VirusTotal", "instance": "VT_prod",
                 "lastError": "", "modified": "t2"},
    },
}


def test_get_integration_status_surfaces_last_error(monkeypatch):
    rf = _RecordingFetcher(post_reply=_HEALTH_SEARCH_REPLY)
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_get_integration_status())
    assert out["ok"] is True
    assert out["total"] == 3
    assert out["unhealthy_count"] == 1
    by_name = {i["instance_name"]: i for i in out["integrations"]}
    splunk = by_name["splunk_prod"]
    assert splunk["healthy"] is False
    assert splunk["last_error"] == "Could not fetch Splunk time"
    assert splunk["enabled"] is True
    assert splunk["modified"] == "t-health"  # health row wins over instance
    vt = by_name["VT_prod"]
    assert vt["healthy"] is True
    assert vt["last_error"] is None

    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/settings/integration/search")


def test_get_integration_status_unhealthy_only(monkeypatch):
    rf = _RecordingFetcher(post_reply=_HEALTH_SEARCH_REPLY)
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_get_integration_status(unhealthy_only=True))
    assert out["total"] == 1
    assert out["unhealthy_count"] == 1
    assert out["integrations"][0]["instance_name"] == "splunk_prod"


def test_get_integration_status_brand_filter(monkeypatch):
    rf = _RecordingFetcher(post_reply=_HEALTH_SEARCH_REPLY)
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_get_integration_status(brand="splunk"))
    names = {i["instance_name"] for i in out["integrations"]}
    assert names == {"splunk_prod", "splunk_old"}
    assert out["unhealthy_count"] == 1  # only splunk_prod has a lastError


def test_test_integration_instance_success(monkeypatch):
    sf = _ScriptedFetcher(replies={
        "/settings/integration/search": _HEALTH_SEARCH_REPLY,
        "/settings/integration/test": {"success": True, "message": "ok"},
    })
    _install_fetcher(monkeypatch, sf)

    out = run(connector.xsoar_test_integration_instance("splunk_prod"))
    assert out["ok"] is True
    assert out["success"] is True
    assert out["message"] == "ok"
    assert out["instance_name"] == "splunk_prod"
    assert out["brand"] == "Splunk"

    # The full resolved instance object is POSTed to /test verbatim.
    test_calls = [c for c in sf.calls if c[1] == "/settings/integration/test"]
    assert len(test_calls) == 1
    posted = test_calls[0][2]
    assert posted["name"] == "splunk_prod"
    assert posted["data"] == [{"name": "host", "value": "guardian-host"}]


def test_test_integration_instance_failure_surfaces_message(monkeypatch):
    sf = _ScriptedFetcher(replies={
        "/settings/integration/search": _HEALTH_SEARCH_REPLY,
        "/settings/integration/test": {
            "success": False, "message": "Could not fetch Splunk time"},
    })
    _install_fetcher(monkeypatch, sf)

    out = run(connector.xsoar_test_integration_instance("splunk_prod"))
    assert out["ok"] is True            # the call completed…
    assert out["success"] is False      # …but the test itself failed
    assert out["message"] == "Could not fetch Splunk time"


def test_test_integration_instance_unwraps_response_envelope(monkeypatch):
    sf = _ScriptedFetcher(replies={
        "/settings/integration/search": _HEALTH_SEARCH_REPLY,
        "/settings/integration/test": {"response": {"success": True, "message": "good"}},
    })
    _install_fetcher(monkeypatch, sf)

    out = run(connector.xsoar_test_integration_instance("splunk_prod"))
    assert out["success"] is True
    assert out["message"] == "good"


def test_test_integration_instance_not_found_is_error_envelope(monkeypatch):
    sf = _ScriptedFetcher(replies={
        "/settings/integration/search": _HEALTH_SEARCH_REPLY,
    })
    _install_fetcher(monkeypatch, sf)

    out = run(connector.xsoar_test_integration_instance("does_not_exist"))
    assert out["ok"] is False
    assert "No configured integration instance" in out["error"]
    # never reached the /test endpoint
    assert not any(c[1] == "/settings/integration/test" for c in sf.calls)


def test_test_integration_instance_v8_unavailable_returns_pointer(monkeypatch):
    """On v8, /settings/integration/test 404s — surface a clear pointer."""

    class _V8TestFetcher:
        is_v8 = True

        def __init__(self):
            self.calls: list = []

        async def post(self, path, body=None, **kw):
            self.calls.append(("POST", path, body))
            if path.endswith("/settings/integration/test"):
                raise XSOARRequestError(
                    "HTTP 404 from /settings/integration/test (not served)"
                )
            return _HEALTH_SEARCH_REPLY

    f = _V8TestFetcher()
    _install_fetcher(monkeypatch, f)

    out = run(connector.xsoar_test_integration_instance("splunk_prod"))
    assert out["ok"] is False
    assert out.get("v8_test_unavailable") is True
    assert "Cortex XSOAR 8" in out["error"]
    assert "fetch_history" in out["error"] or "fetch-history" in out["error"] \
        or "get_integration_fetch_history" in out["error"]


# ─── get_integration_fetch_history (v0.2.42) ─────────────────────────

# POST /settings/integration/fetch-history response — `data` rows each with a
# status + lastError (the v8 fetch-error source).
_FETCH_HISTORY_REPLY = {
    "data": [
        {"status": "failed", "lastError": "Could not fetch Splunk time",
         "lastPullTime": "2026-06-20T05:00:00Z", "numOfIncidents": 0},
        {"status": "success", "lastError": "",
         "lastPullTime": "2026-06-20T04:59:00Z", "numOfIncidents": 15},
    ],
}


def test_get_integration_fetch_history_projects_runs(monkeypatch):
    sf = _ScriptedFetcher(replies={
        "/settings/integration/search": _HEALTH_SEARCH_REPLY,
        "/settings/integration/fetch-history": _FETCH_HISTORY_REPLY,
    })
    _install_fetcher(monkeypatch, sf)

    out = run(connector.xsoar_get_integration_fetch_history("splunk_prod"))
    assert out["ok"] is True
    assert out["brand"] == "Splunk"
    assert out["total"] == 2
    assert out["runs"][0]["status"] == "failed"
    assert out["runs"][0]["last_error"] == "Could not fetch Splunk time"
    assert out["runs"][0]["incidents_pulled"] == 0
    assert out["runs"][1]["last_error"] is None
    assert out["runs"][1]["incidents_pulled"] == 15

    fh = [c for c in sf.calls if c[1] == "/settings/integration/fetch-history"]
    assert len(fh) == 1
    assert fh[0][2] == {"brand": "Splunk", "instance": "splunk_prod"}


def test_get_integration_fetch_history_clamps_limit(monkeypatch):
    sf = _ScriptedFetcher(replies={
        "/settings/integration/search": _HEALTH_SEARCH_REPLY,
        "/settings/integration/fetch-history": _FETCH_HISTORY_REPLY,
    })
    _install_fetcher(monkeypatch, sf)

    out = run(connector.xsoar_get_integration_fetch_history("splunk_prod", limit=1))
    assert out["total"] == 1
    assert out["runs"][0]["status"] == "failed"


def test_get_integration_fetch_history_not_found(monkeypatch):
    sf = _ScriptedFetcher(replies={
        "/settings/integration/search": _HEALTH_SEARCH_REPLY,
    })
    _install_fetcher(monkeypatch, sf)

    out = run(connector.xsoar_get_integration_fetch_history("nope"))
    assert out["ok"] is False
    assert "No configured integration instance" in out["error"]
    assert not any(
        c[1] == "/settings/integration/fetch-history" for c in sf.calls
    )


# ─── import_playbook (v0.2.26) ───────────────────────────────────────


def test_import_playbook_success(monkeypatch):
    rf = _RecordingFetcher(multipart_reply={"id": "pb-1", "name": "My PB"})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_import_playbook(playbook_yaml="id: x\nname: My PB\n"))
    assert out["ok"] is True
    assert out["playbook_id"] == "pb-1"
    assert out["playbook_name"] == "My PB"
    assert out["imported"] is True
    method, path, files = rf.calls[0]
    assert (method, path) == ("POST_MULTIPART", "/playbook/save/yaml")
    assert "file" in files


def test_import_playbook_normalizes_array_body(monkeypatch):
    rf = _RecordingFetcher(multipart_reply={"data": [{"id": "pb-2", "name": "Arr PB"}]})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_import_playbook(playbook_yaml="id: y\nname: Arr PB\n"))
    assert out["ok"] is True and out["playbook_id"] == "pb-2"


def test_import_playbook_extracts_from_playbook_wrapped_body(monkeypatch):
    # v6 POST /playbook/save/yaml returns {"playbook": {...}} (the live shape) —
    # extract id/name from the nested object, not the outer envelope.
    rf = _RecordingFetcher(
        multipart_reply={"playbook": {"id": "PbWrapped", "name": "Wrapped PB", "version": 8}}
    )
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_import_playbook(playbook_yaml="id: PbWrapped\nname: Wrapped PB\n"))
    assert out["ok"] is True
    assert out["playbook_id"] == "PbWrapped"
    assert out["playbook_name"] == "Wrapped PB"


def test_import_playbook_requires_yaml(monkeypatch):
    rf = _RecordingFetcher()
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_import_playbook(playbook_yaml="   "))
    assert out["ok"] is False and "playbook_yaml" in out["error"]


def test_import_playbook_unavailable_on_405_no_playground(monkeypatch):
    # Cortex 8 public gateway 405s AND no playground_id → guided-manual message.
    rf = _RecordingFetcher(
        multipart_exc=XSOARRequestError(
            "HTTP 405 from /playbook/import: Method Not Allowed"
        )
    )
    _install_fetcher(monkeypatch, rf)
    monkeypatch.setattr(connector, "_get_xsoar_config", lambda: {"playground_id": None})
    out = run(connector.xsoar_import_playbook(playbook_yaml="id: z\nname: Z\n"))
    assert out["ok"] is False
    assert out["import_unavailable"] is True
    assert out["reason"] == "import_endpoint_unavailable_and_no_core_api_path"


def test_import_playbook_via_core_api_on_405(monkeypatch):
    # issue #46: Cortex 8 405 + Core REST API integration + playground_id →
    # import via core-api-post /playbook/save (a JSON ARRAY of playbooks).
    rf = _RecordingFetcher(
        multipart_exc=XSOARRequestError(
            "HTTP 405 from /playbook/import: Method Not Allowed"
        )
    )
    _install_fetcher(monkeypatch, rf)
    monkeypatch.setattr(connector, "_get_xsoar_config", lambda: {"playground_id": "PG-8"})
    seen = {}

    async def _fake_exec(fetcher, inv, command, return_context_keys=None):
        seen["inv"] = inv
        seen["command"] = command
        return {"output": '{"response":[{"id":"z","name":"Z"}]}'}

    monkeypatch.setattr(connector, "_execute_command", _fake_exec)
    out = run(connector.xsoar_import_playbook(playbook_yaml="id: z\nname: Z\n"))
    assert out["ok"] is True and out["imported"] is True and out["via"] == "core-api"
    assert out["playbook_id"] == "z" and out["playbook_name"] == "Z"
    # Ran in the playground, as a JSON ARRAY body via core-api-post.
    assert seen["inv"] == "PG-8"
    assert seen["command"].startswith("!core-api-post uri=/playbook/save body=`[")
    assert '"id":"z"' in seen["command"] and seen["command"].endswith("]`")


def test_import_playbook_core_api_save_error(monkeypatch):
    # The core-api call ran but the server rejected it → clean ok=false.
    rf = _RecordingFetcher(
        multipart_exc=XSOARRequestError(
            "HTTP 405 from /playbook/import: Method Not Allowed"
        )
    )
    _install_fetcher(monkeypatch, rf)
    monkeypatch.setattr(connector, "_get_xsoar_config", lambda: {"playground_id": "PG-8"})

    async def _fake_exec(fetcher, inv, command, return_context_keys=None):
        return {"output": "Error: Error from Core REST API ... Status code: 400. Bad Request"}

    monkeypatch.setattr(connector, "_execute_command", _fake_exec)
    out = run(connector.xsoar_import_playbook(playbook_yaml="id: z\nname: Z\n"))
    assert out["ok"] is False and out["reason"] == "core_api_save_failed"


def test_import_playbook_other_4xx_is_normal_error(monkeypatch):
    # A genuine bad-request (not a generation mismatch) stays a normal error.
    rf = _RecordingFetcher(
        multipart_exc=XSOARRequestError("HTTP 400 from /playbook/import: bad yaml")
    )
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_import_playbook(playbook_yaml="id: z\nname: Z\n"))
    assert out["ok"] is False
    assert out.get("import_unavailable") is None
    assert "request rejected" in out["error"]


# ═══════════════════════════════════════════════════════════════════
# search_indicators — compact summary projection (v0.2.34, issue #48)
# ═══════════════════════════════════════════════════════════════════


def test_search_indicators_summarizes_compact_keys_and_reputation(monkeypatch):
    """Raw verbose IoC -> compact dict; score 3 -> 'Bad'; verbose keys
    dropped; source prefers sourceBrands; query passed through."""
    rf = _RecordingFetcher(post_reply={
        "total": 1,
        "iocObjects": [{
            "id": "7a1", "version": 4, "cacheVersn": 0, "sizeInBytes": 99,
            "sortValues": ["x"], "comments": [{"id": "c1"}],
            "indicator_type": "IP", "value": "8.8.8.8", "score": 3,
            "sourceBrands": ["VirusTotal"], "sourceInstances": ["VT_prod"],
            "investigationIDs": ["221"], "expirationStatus": "active",
            "created": "t0", "modified": "t1", "CustomFields": {"k": "v"},
        }],
    })
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_search_indicators(query="type:IP", size=10))
    assert out["ok"] is True
    assert out["total"] == 1
    assert out["result_count"] == 1
    ind = out["indicators"][0]
    assert ind == {
        "id": "7a1", "type": "IP", "value": "8.8.8.8", "score": 3,
        "reputation": "Bad", "source": "VirusTotal",
        "created": "t0", "modified": "t1",
        "investigation_ids": ["221"], "expiration_status": "active",
    }
    # Verbose store fields must NOT leak through.
    assert "version" not in ind and "CustomFields" not in ind
    assert "sortValues" not in ind and "comments" not in ind
    # Request shape: FLAT body — query/size/page at the TOP level, NOT
    # nested under "filter". /indicators/search ignores a "filter" envelope
    # entirely (unlike /incidents/search), so nesting silently disables the
    # query, size and page. Lock the flat shape against regression.
    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/indicators/search")
    assert body["query"] == "type:IP"
    assert "filter" not in body
    assert body["size"] == 10


def test_search_indicators_missing_score_maps_to_unknown(monkeypatch):
    """No score key -> no KeyError, score 0, reputation 'Unknown'."""
    rf = _RecordingFetcher(post_reply={
        "total": 1,
        "iocObjects": [{
            "id": "7a2", "indicator_type": "Domain",
            "value": "evil.example.com", "sourceBrands": ["Manual"],
        }],
    })
    _install_fetcher(monkeypatch, rf)
    ind = run(connector.xsoar_search_indicators())["indicators"][0]
    assert ind["score"] == 0
    assert ind["reputation"] == "Unknown"
    assert ind["type"] == "Domain"
    assert ind["source"] == "Manual"


def test_search_indicators_source_falls_back_to_source_instances(monkeypatch):
    """Empty sourceBrands -> source from sourceInstances; score 2 ->
    'Suspicious'; camelCase indicatorType also resolved."""
    rf = _RecordingFetcher(post_reply={
        "total": 1,
        "iocObjects": [{
            "id": "7a3", "indicatorType": "File", "value": "d41d8cd9",
            "score": 2, "sourceBrands": [], "sourceInstances": ["Cortex XSOAR"],
        }],
    })
    _install_fetcher(monkeypatch, rf)
    ind = run(connector.xsoar_search_indicators(query="type:File"))["indicators"][0]
    assert ind["score"] == 2
    assert ind["reputation"] == "Suspicious"
    assert ind["type"] == "File"
    assert ind["source"] == "Cortex XSOAR"


def test_search_indicators_empty_store_returns_empty_list(monkeypatch):
    """No indicators (bare `data` path) -> ok, empty list, zero totals."""
    rf = _RecordingFetcher(post_reply={"total": 0, "data": []})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_search_indicators(query="type:IP"))
    assert out["ok"] is True
    assert out["indicators"] == []
    assert out["total"] == 0
    assert out["result_count"] == 0


def test_summarize_indicator_first_source_scalar_and_missing():
    """_first_source: bare-string source, and both-missing -> None."""
    assert connector._first_source({"sourceBrands": "VT"}) == "VT"
    assert connector._first_source({"sourceInstances": []}) is None
    assert connector._first_source({}) is None


# ═══════════════════════════════════════════════════════════════════
# evidence flow — generation-aware save + compact search (v0.2.35, #49)
# ═══════════════════════════════════════════════════════════════════


def test_save_evidence_v6_uses_evidence_post(monkeypatch):
    """XSOAR 6: save_evidence POSTs the formal /evidence create (which
    round-trips into /evidence/search) — NOT /entry/tags."""
    rf = _RecordingFetcher(
        post_reply={"id": "1@223", "incidentId": "223", "entryId": "7@223"},
        is_v8=False,
    )
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_save_evidence(
        incident_id="223", entry_id="7@223", description="why"))
    assert out["ok"] is True
    assert out["saved"] is True
    assert out["via"] == "evidence-api"
    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/evidence")
    assert body == {"incidentId": "223", "entryId": "7@223", "description": "why"}


def test_save_evidence_v8_falls_back_to_entry_tag(monkeypatch):
    """XSOAR 8: /evidence POST isn't on the public API — tag the entry
    `evidence` via /entry/tags instead."""
    rf = _RecordingFetcher(post_reply={"id": "ok"}, is_v8=True)
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_save_evidence(incident_id="4051", entry_id="9@4051"))
    assert out["ok"] is True
    assert out["tagged"] is True
    assert out["via"] == "entry-tag"
    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/entry/tags")
    assert body["tags"] == ["evidence"]
    assert body["investigationId"] == "4051"


def test_search_evidence_summarizes_compact(monkeypatch):
    """Raw verbose evidence object -> compact summary; verbose keys dropped.
    Shape grounded in a live XSOAR 6 /evidence/search object."""
    rf = _RecordingFetcher(post_reply={"total": 1, "evidences": [{
        "id": "1@223", "version": 1, "cacheVersn": 0, "sizeInBytes": 0,
        "dbotCreatedBy": "admin", "fetched": "t", "taskId": "", "tagsRaw": [],
        "CustomFields": None, "incidentId": "223", "entryId": "7@223",
        "description": "phish proof", "occurred": "2026-01-01T00:00:00Z",
        "markedBy": "admin", "markedDate": "2026-06-15T14:17:04Z",
        "tags": ["evidence"],
    }]})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_search_evidence(incident_id="223"))
    assert out["ok"] is True
    assert out["count"] == 1
    ev = out["evidence"][0]
    assert ev == {
        "id": "1@223", "entry_id": "7@223", "incident_id": "223",
        "description": "phish proof", "occurred": "2026-01-01T00:00:00Z",
        "marked_by": "admin", "marked_date": "2026-06-15T14:17:04Z",
        "tags": ["evidence"],
    }
    assert "version" not in ev and "dbotCreatedBy" not in ev and "tagsRaw" not in ev
    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/evidence/search")
    assert body == {"incidentID": "223"}


def test_search_evidence_empty_returns_empty_list(monkeypatch):
    """No evidence (bare `data` path) -> ok, empty list, zero count."""
    rf = _RecordingFetcher(post_reply={"total": 0, "data": []})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_search_evidence(incident_id="999"))
    assert out["ok"] is True
    assert out["evidence"] == []
    assert out["count"] == 0
    assert out["via"] == "evidence-api"  # v6 path (default is_v8=False)


def test_search_evidence_v8_reads_war_room_tag(monkeypatch):
    """XSOAR 8: /evidence/search doesn't return tag-based evidence, so
    search_evidence reads the war room filtered to the `evidence` tag and
    projects each tagged entry into the evidence shape."""
    rf = _RecordingFetcher(post_reply={"entries": [
        {"id": "7@4068", "type": 1, "contents": "phish proof",
         "created": "2026-06-15T00:00:00Z", "user": "admin", "tags": ["evidence"]},
        {"id": "8@4068", "type": 1, "contents": "unrelated note",
         "created": "2026-06-15T00:01:00Z", "user": "admin", "tags": ["note"]},
    ]}, is_v8=True)
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_search_evidence(incident_id="4068"))
    assert out["ok"] is True
    assert out["via"] == "war-room-tag"
    assert out["count"] == 1  # the 'note'-tagged entry is filtered out
    assert out["evidence"][0] == {
        "id": "7@4068", "entry_id": "7@4068", "incident_id": "4068",
        "description": "phish proof", "occurred": "2026-06-15T00:00:00Z",
        "marked_by": "admin", "marked_date": "2026-06-15T00:00:00Z",
        "tags": ["evidence"],
    }
    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/investigation/4068")
    assert body["tags"] == ["evidence"]


def test_summarize_evidence_entry_maps_war_room_fields():
    """_summarize_evidence_entry maps a war-room entry to the evidence shape."""
    ev = connector._summarize_evidence_entry(
        {"id": "9@1", "contents": "c", "created": "t", "user": "u", "tags": ["evidence"]},
        "1",
    )
    assert ev == {
        "id": "9@1", "entry_id": "9@1", "incident_id": "1", "description": "c",
        "occurred": "t", "marked_by": "u", "marked_date": "t", "tags": ["evidence"],
    }


# ─── get_playbook_state (v0.2.42) ────────────────────────────────────

_WORKPLAN_OK = {
    "invPlaybook": {
        "playbookId": "Splunk Notable Triage",
        "name": "Splunk Notable Triage",
        # XSOAR returns the playbook-level state LOWERCASE ("completed") even
        # though per-task states are capitalized — ran_to_success must match
        # case-insensitively.
        "state": "completed",
        "tasks": {
            "0": {"id": "0", "state": "Completed", "task": {"name": "Start"}},
            "1": {"id": "1", "state": "Completed",
                  "task": {"name": "splunk-job-create", "scriptId": "SplunkPy"}},
        },
    }
}

_WORKPLAN_FAILED = {
    "invPlaybook": {
        "playbookId": "PB", "name": "PB", "state": "Completed",
        "tasks": {
            "0": {"id": "0", "state": "Completed", "task": {"name": "Start"}},
            "3": {"id": "3", "state": "Error",
                  "task": {"name": "splunk-search", "scriptId": "SplunkPy"}},
        },
    }
}

_WARROOM_ERR = {"entries": [
    {"id": "e1", "type": 4, "taskId": "3", "contents": "splunk-search failed: boom"},
    {"id": "e2", "type": 1, "taskId": "0", "contents": "ok"},
]}

_WORKPLAN_SUBPB = {
    "invPlaybook": {
        "playbookId": "Parent", "name": "Parent", "state": "Completed",
        "tasks": {
            "0": {"id": "0", "state": "Completed", "task": {"name": "Start"}},
            "5": {"id": "5", "state": "Completed", "task": {"name": "sub"},
                  "subPlaybook": {"tasks": {
                      "s1": {"id": "s1", "state": "LoopError",
                             "task": {"name": "nested-fail"}},
                  }}},
        },
    }
}


def test_get_playbook_state_success(monkeypatch):
    rf = _RecordingFetcher(get_reply=_WORKPLAN_OK)
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_get_playbook_state("42"))
    assert out["ok"] is True
    assert out["has_playbook"] is True
    assert out["ran_to_success"] is True
    assert out["overall_state"] == "completed"
    assert out["counts"]["completed"] == 2
    assert out["task_total"] == 2
    assert out["failed_tasks"] == []
    # the per-task list is now surfaced (id/name/state/type) for monitoring +
    # complete_task discovery
    assert out["tasks_truncated"] is False
    assert {t["id"] for t in out["tasks"]} == {"0", "1"}
    assert all(t["state"] == "Completed" for t in out["tasks"])
    # work plan read via GET; war room NOT fetched when there are no failures.
    assert rf.calls[0][0] == "GET"
    assert all(c[0] != "POST" for c in rf.calls)


def test_get_playbook_state_surfaces_waiting_task_for_complete(monkeypatch):
    # A Waiting manual task's id must appear in `tasks` so the operator/agent
    # can feed it to xsoar_complete_task (the work plan is the only place the
    # id lives).
    wp = {"invPlaybook": {"playbookId": "PB", "name": "PB", "state": "waiting", "tasks": {
        "0": {"id": "0", "state": "Completed", "task": {"name": "Start", "type": "start"}},
        "1": {"id": "1", "state": "Waiting", "task": {"name": "Analyst review", "type": "regular"}},
    }}}
    rf = _RecordingFetcher(get_reply=wp)
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_get_playbook_state("42"))
    assert out["ran_to_success"] is False
    waiting = [t for t in out["tasks"] if t["state"] == "Waiting"]
    assert len(waiting) == 1
    assert waiting[0]["id"] == "1" and waiting[0]["type"] == "regular"


def test_get_playbook_state_failed_task_attaches_error(monkeypatch):
    rf = _RecordingFetcher(get_reply=_WORKPLAN_FAILED, post_reply=_WARROOM_ERR)
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_get_playbook_state("42"))
    assert out["ran_to_success"] is False
    assert out["counts"]["error"] == 1
    assert len(out["failed_tasks"]) == 1
    ft = out["failed_tasks"][0]
    assert ft["state"] == "Error"
    assert ft["name"] == "splunk-search"
    assert "boom" in (ft.get("errorMessage") or "")
    # the war room WAS fetched (to resolve the error text).
    assert any(c[0] == "POST" for c in rf.calls)


def test_get_playbook_state_recurses_subplaybook(monkeypatch):
    rf = _RecordingFetcher(get_reply=_WORKPLAN_SUBPB, post_reply={"entries": []})
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_get_playbook_state("42"))
    assert out["ran_to_success"] is False
    names = {f["name"] for f in out["failed_tasks"]}
    assert "nested-fail" in names  # failure inside the sub-playbook surfaces


def test_get_playbook_state_no_playbook(monkeypatch):
    rf = _RecordingFetcher(get_reply={"noPlaybookHere": 1})
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_get_playbook_state("42"))
    assert out["ok"] is True
    assert out["has_playbook"] is False


# ─── run_playbook investigation bootstrap + list_incidents source (v0.2.42) ──

def test_run_playbook_opens_investigation_then_setplaybook(monkeypatch):
    # _ensure_investigation: reads the version via /incidents/search, then opens
    # the war room via POST /incident/investigate {id, version} (verified live;
    # the old POST /incident {createInvestigation:true} is a no-op on an existing
    # incident). run_playbook then resolves the playbook id -> display name via
    # /playbook/search and !setPlaybook switches the incident to it.
    f = _ScriptedFetcher(replies={
        "/incidents/search": {"data": [{"id": "42", "version": 7}], "total": 1},
        "/incident/investigate": {"id": "42", "investigation": {"id": "42"}},
        "/playbook/search": {"playbooks": [{"id": "MyPbId", "name": "My PB"}]},
        "/entry/execute/sync": {"data": [{"type": 1,
                                          "contents": "Changed playbook from 'Default' to 'My PB'."}]},
    })
    _install_fetcher(monkeypatch, f)

    out = run(connector.xsoar_run_playbook("42", "MyPbId"))
    assert out["ok"] is True
    assert out["opened_investigation"] is True
    assert out["playbook_name"] == "My PB"  # resolved from the id
    paths = [p for (_m, p, _b) in f.calls]
    assert "/incident/investigate" in paths  # the working open endpoint
    # the war room is opened BEFORE setPlaybook runs
    assert paths.index("/incident/investigate") < paths.index("/entry/execute/sync")
    # the open call carried the incident id + optimistic-lock version
    open_body = [b for (_m, p, b) in f.calls if p == "/incident/investigate"][0]
    assert open_body.get("id") == "42"
    assert open_body.get("version") == 7
    # setPlaybook uses the RESOLVED display name, not the id
    exec_call = [b for (_m, p, b) in f.calls if p == "/entry/execute/sync"][0]
    assert exec_call["data"] == '!setPlaybook name="My PB"'


def test_run_playbook_falls_back_to_createinvestigation(monkeypatch):
    # When /incident/investigate isn't served (raises), _ensure_investigation
    # falls back to POST /incident {createInvestigation:true}.
    class _InvestigateUnservedFetcher(_ScriptedFetcher):
        async def post(self, path, body=None, **kw):
            if path == "/incident/investigate":
                self.calls.append(("POST", path, body))
                raise XSOARRequestError("HTTP 404 from /incident/investigate")
            return await super().post(path, body, **kw)

    f = _InvestigateUnservedFetcher(replies={
        "/incidents/search": {"data": [{"id": "42", "version": 7}], "total": 1},
        "/incident": {"id": "42", "investigationId": "42"},
        "/playbook/search": {},
        "/entry/execute/sync": {"data": [{"type": 1, "contents": "done"}]},
    })
    _install_fetcher(monkeypatch, f)
    out = run(connector.xsoar_run_playbook("42", "Some PB"))
    assert out["ok"] is True and out["opened_investigation"] is True
    paths = [p for (_m, p, _b) in f.calls]
    assert "/incident/investigate" in paths and "/incident" in paths  # tried both
    fb_body = [b for (_m, p, b) in f.calls if p == "/incident"][0]
    assert fb_body.get("createInvestigation") is True


def test_list_incidents_source_brand_builds_query(monkeypatch):
    rf = _RecordingFetcher(post_reply={"total": 0, "data": []})
    _install_fetcher(monkeypatch, rf)
    run(connector.xsoar_list_incidents(source_brand="SplunkPy v2"))
    q = rf.calls[0][2]["filter"]["query"]
    assert q == 'sourceBrand:"SplunkPy v2"'


def test_list_incidents_source_instance_and_query_combined(monkeypatch):
    rf = _RecordingFetcher(post_reply={"total": 0, "data": []})
    _install_fetcher(monkeypatch, rf)
    run(connector.xsoar_list_incidents(query="status:active", source_instance="splunk-mimic"))
    q = rf.calls[0][2]["filter"]["query"]
    assert "(status:active)" in q
    assert 'sourceInstance:"splunk-mimic"' in q
    assert " and " in q


# ─── list_playbooks / get_playbook (R1: tenant playbook catalog + detail) ──


def test_list_playbooks_request_shape_and_summary(monkeypatch):
    rf = _RecordingFetcher(post_reply={
        "total": 2,
        "playbooks": [
            {"id": "pb-1", "name": "Phishing Investigation",
             "description": "Triage phishing", "tags": ["phishing"],
             "system": True, "inputs": [{"key": "URL"}],
             "tasks": {"0": {}, "1": {}, "2": {}}},
            {"id": "pb-2", "name": "Malware Containment", "system": False},
        ],
    })
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_list_playbooks(query="tag:phishing", page=1, size=25))
    assert out["ok"] is True
    assert out["total"] == 2
    assert out["result_count"] == 2
    first = out["playbooks"][0]
    assert first["id"] == "pb-1"
    assert first["name"] == "Phishing Investigation"
    assert first["input_count"] == 1
    assert first["task_count"] == 3
    assert first["system"] is True

    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/playbook/search")
    assert body == {"page": 1, "size": 25, "query": "tag:phishing"}


def test_list_playbooks_size_capped_and_total_fallback(monkeypatch):
    rf = _RecordingFetcher(post_reply={"playbooks": [{"id": "pb-1", "name": "A"}]})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_list_playbooks(size=9999))
    # size capped at 200; no "query" key when omitted
    assert rf.calls[0][2] == {"page": 0, "size": 200}
    # total falls back to result_count when XSOAR omits "total"
    assert out["total"] == 1
    assert out["result_count"] == 1


def test_get_playbook_detail_inputs_and_tasks(monkeypatch):
    rf = _RecordingFetcher(post_reply={
        "playbooks": [{
            "id": "pb-1", "name": "Phishing Investigation",
            "description": "Triage phishing", "tags": ["phishing"],
            "system": True, "startTaskId": "0",
            "inputs": [
                {"key": "URL", "required": True, "description": "url to detonate",
                 "value": {"simple": "https://x"}},
                {"key": "Sender", "required": False,
                 "value": {"complex": {"root": "incident"}}},
            ],
            "tasks": {
                "0": {"id": "0", "type": "start", "task": {"name": "Start"}},
                "1": {"id": "1", "type": "regular", "task": {"name": "Detonate URL"}},
            },
        }],
    })
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_get_playbook("pb-1"))
    assert out["ok"] is True
    assert out["id"] == "pb-1"
    assert out["start_task_id"] == "0"
    assert out["input_count"] == 2
    assert out["inputs"][0] == {
        "key": "URL", "required": True,
        "description": "url to detonate", "default": "https://x",
    }
    # a complex/context value reference is summarized, not dumped
    assert out["inputs"][1]["default"] == "<complex/context reference>"
    assert out["task_count"] == 2
    assert out["tasks"][1] == {"id": "1", "name": "Detonate URL", "type": "regular"}
    # resolved by an id: query first
    assert rf.calls[0] == ("POST", "/playbook/search", {"query": "id:pb-1"})


def test_get_playbook_name_fallback(monkeypatch):
    # id: query returns empty → name: query returns the hit
    class _TwoStep:
        is_v8 = False

        def __init__(self):
            self.calls: list = []
            self._n = 0

        async def post(self, path, body=None, **kw):
            self.calls.append(("POST", path, body))
            self._n += 1
            if self._n == 1:
                return {"playbooks": []}
            return {"playbooks": [{"id": "pb-9", "name": "My PB"}]}

    f = _TwoStep()
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)
    out = run(connector.xsoar_get_playbook("My PB"))
    assert out["ok"] is True
    assert out["name"] == "My PB"
    assert f.calls[0][2] == {"query": "id:My PB"}
    assert f.calls[1][2] == {"query": 'name:"My PB"'}


def test_get_playbook_not_found(monkeypatch):
    rf = _RecordingFetcher(post_reply={"playbooks": []})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_get_playbook("nope"))
    assert out["ok"] is False
    assert "not found" in out["error"]
    assert out["playbook_id"] == "nope"


# ─── create_indicator / update_indicator (R2: TIM write) ─────────────


def test_create_indicator_request_and_summary(monkeypatch):
    # /indicator/create returns the FLAT created indicator object (verified live)
    rf = _RecordingFetcher(post_reply={
        "id": "1192500", "version": 1, "indicator_type": "IP",
        "value": "203.0.113.77", "score": 3, "source": "Guardian",
        "created": "t0", "modified": "t1",
    })
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_create_indicator(
        value="203.0.113.77", indicator_type="IP", score=3,
        tags=["guardian-r2"], source="Guardian"))
    assert out["ok"] is True
    assert out["id"] == "1192500"
    assert out["created"]["value"] == "203.0.113.77"
    assert out["created"]["score"] == 3
    assert out["created"]["reputation"] == "Bad"

    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/indicator/create")
    ind = body["indicator"]
    assert ind["value"] == "203.0.113.77"
    assert ind["indicator_type"] == "IP"
    assert ind["score"] == 3 and ind["manualScore"] is True
    assert ind["CustomFields"] == {"tags": ["guardian-r2"]}
    assert ind["source"] == "Guardian"


def test_create_indicator_requires_value_and_type(monkeypatch):
    _install_fetcher(monkeypatch, _RecordingFetcher())
    assert run(connector.xsoar_create_indicator(value="", indicator_type="IP"))["ok"] is False
    assert run(connector.xsoar_create_indicator(value="x", indicator_type=""))["ok"] is False


def test_update_indicator_sets_reputation(monkeypatch):
    rf = _RecordingFetcher(post_reply={
        "id": "1192500", "version": 4, "indicator_type": "IP",
        "value": "203.0.113.77", "score": 3,
    })
    _install_fetcher(monkeypatch, rf)

    out = run(connector.xsoar_update_indicator(
        indicator_id="1192500", score=3, comment="manual verdict"))
    assert out["ok"] is True
    assert out["updated"]["score"] == 3
    assert out["updated"]["reputation"] == "Bad"

    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/indicator/edit")
    assert body["id"] == "1192500"
    assert body["score"] == 3 and body["manualScore"] is True
    assert body["comment"] == "manual verdict"
    # no value/indicator_type on an edit-only body
    assert "value" not in body and "indicator_type" not in body


def test_update_indicator_tags_only(monkeypatch):
    rf = _RecordingFetcher(post_reply={"id": "5", "indicator_type": "Domain", "value": "x.com"})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_update_indicator(indicator_id="5", tags=["phish"]))
    assert out["ok"] is True
    assert rf.calls[0][2]["CustomFields"] == {"tags": ["phish"]}
    # score not sent when not provided
    assert "score" not in rf.calls[0][2]


def test_update_indicator_requires_a_field(monkeypatch):
    _install_fetcher(monkeypatch, _RecordingFetcher())
    out = run(connector.xsoar_update_indicator(indicator_id="5"))
    assert out["ok"] is False
    assert "nothing to update" in out["error"]


# ─── R3: connector self-sufficiency — /xsoar internal path ───────────


def test_full_url_internal_vs_public():
    from src._xsoar_client import XSOARFetcher
    v6 = XSOARFetcher(api_url="https://xsoar6", api_key="k", api_id=None, verify_ssl=False)
    v8 = XSOARFetcher(api_url="https://api-t.xdr.us", api_key="k", api_id="42", verify_ssl=False)
    # v6: no prefix, internal and public identical
    assert v6._full_url("/playbook/save") == "https://xsoar6/playbook/save"
    assert v6._full_url("/playbook/save", internal=True) == "https://xsoar6/playbook/save"
    # v8: public gateway vs full internal API
    assert v8._full_url("/playbook/save") == "https://api-t.xdr.us/xsoar/public/v1/playbook/save"
    assert v8._full_url("/playbook/save", internal=True) == "https://api-t.xdr.us/xsoar/playbook/save"
    assert (v8._full_url("/investigation/9/workplan", internal=True)
            == "https://api-t.xdr.us/xsoar/investigation/9/workplan")
    # de-dup a path that already carries the public prefix
    assert v8._full_url("/xsoar/public/v1/x") == "https://api-t.xdr.us/xsoar/public/v1/x"


def test_fetch_workplan_v8_prefers_internal_direct(monkeypatch):
    # On v8, the work plan is read via the DIRECT internal API path
    # (no Core REST API integration / playground), not !core-api-get.
    class _WPFetcher:
        is_v8 = True

        def __init__(self):
            self.calls: list = []

        async def get(self, path, **kw):
            self.calls.append((path, kw.get("internal")))
            return {"id": "INV"}  # a (minimal) workplan dict

    f = _WPFetcher()
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)
    out = run(connector.xsoar_get_playbook_state("INV"))
    assert out["ok"] is True
    assert f.calls and f.calls[0] == ("/investigation/INV/workplan", True)


def test_fetch_workplan_v6_unchanged(monkeypatch):
    # v6 still reads the work plan directly (no internal flag needed).
    class _WP6:
        is_v8 = False

        def __init__(self):
            self.calls: list = []

        async def get(self, path, **kw):
            self.calls.append((path, kw.get("internal")))
            return {"id": "INV"}

    f = _WP6()
    monkeypatch.setattr(connector, "_get_fetcher", lambda: f)
    out = run(connector.xsoar_get_playbook_state("INV"))
    assert out["ok"] is True
    assert f.calls[0][0] == "/investigation/INV/workplan"
