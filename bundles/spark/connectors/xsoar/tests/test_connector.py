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
                 get_reply: Optional[dict] = None, is_v8: bool = False):
        self.post_reply = post_reply if post_reply is not None else {}
        self.get_reply = get_reply if get_reply is not None else {}
        self.is_v8 = is_v8
        self.calls: list[tuple[str, str, Any]] = []

    async def post(self, path, body=None, **kw):
        self.calls.append(("POST", path, body))
        return self.post_reply

    async def get(self, path, **kw):
        self.calls.append(("GET", path, kw.get("params")))
        return self.get_reply


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


def test_get_list_filters_by_name(monkeypatch):
    rf = _RecordingFetcher(get_reply={"data": [
        {"id": "a", "name": "allowlist", "data": "1.1.1.1", "type": "plain_text"},
        {"id": "b", "name": "blocklist", "data": "2.2.2.2", "type": "plain_text"},
    ]})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_get_list("blocklist"))
    assert out["ok"] is True
    assert out["name"] == "blocklist" and out["data"] == "2.2.2.2"
    assert rf.calls[0][0:2] == ("GET", "/lists/")


def test_get_list_not_found(monkeypatch):
    rf = _RecordingFetcher(get_reply={"data": []})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_get_list("nope"))
    assert out["ok"] is False and "not found" in out["error"]


def test_set_list_saves(monkeypatch):
    rf = _RecordingFetcher(post_reply={"id": "x"})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_set_list("blocklist", "1.1.1.1\n2.2.2.2"))
    assert out["ok"] is True and out["name"] == "blocklist" and out["type"] == "plain_text"
    method, path, body = rf.calls[0]
    assert (method, path) == ("POST", "/lists/save")
    assert body == {"name": "blocklist", "data": "1.1.1.1\n2.2.2.2", "type": "plain_text"}


def test_set_list_json_type(monkeypatch):
    rf = _RecordingFetcher(post_reply={})
    _install_fetcher(monkeypatch, rf)
    run(connector.xsoar_set_list("cfg", '{"a":1}', list_type="json"))
    assert rf.calls[0][2]["type"] == "json"


def test_append_to_list_plain_text(monkeypatch):
    rf = _RecordingFetcher(
        get_reply={"data": [{"name": "bl", "data": "1.1.1.1", "type": "plain_text"}]},
        post_reply={},
    )
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_append_to_list("bl", "2.2.2.2"))
    assert out["ok"] is True and out["data"] == "1.1.1.1\n2.2.2.2"
    # last call is the save with the merged data
    method, path, body = rf.calls[-1]
    assert (method, path) == ("POST", "/lists/save")
    assert body["data"] == "1.1.1.1\n2.2.2.2"


def test_append_to_list_creates_when_absent(monkeypatch):
    rf = _RecordingFetcher(get_reply={"data": []}, post_reply={})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_append_to_list("new", "first"))
    assert out["ok"] is True and out["data"] == "first" and out["type"] == "plain_text"


def test_append_to_list_json(monkeypatch):
    rf = _RecordingFetcher(
        get_reply={"data": [{"name": "j", "data": "[\"a\"]", "type": "json"}]},
        post_reply={},
    )
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_append_to_list("j", "b"))
    assert out["ok"] is True
    import json as _j
    assert _j.loads(out["data"]) == ["a", "b"]


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


def test_run_playbook_posts_inv_playbook(monkeypatch):
    rf = _RecordingFetcher(post_reply={"investigationId": "42"})
    _install_fetcher(monkeypatch, rf)
    out = run(connector.xsoar_run_playbook(incident_id="42", playbook_id="Phishing Investigation"))
    assert out["ok"] is True
    assert out["incident_id"] == "42" and out["playbook_id"] == "Phishing Investigation"
    method, path, body = rf.calls[0]
    assert method == "POST"
    assert path == "/inv-playbook/Phishing Investigation/42"


def test_run_playbook_requires_ids(monkeypatch):
    rf = _RecordingFetcher(post_reply={})
    _install_fetcher(monkeypatch, rf)
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
        "xsoar_save_evidence",
        "xsoar_search_evidence",
        "xsoar_health_check",
    }
    assert set(connector.__all__) == expected
    for name in expected:
        assert callable(getattr(connector, name)), f"{name} not callable"
