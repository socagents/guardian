"""xsiam connector — unit tests.

No network. Covers:
  1. _papi_client.Fetcher — the Cortex public-API auth headers
     (x-xdr-auth-id + Authorization) + base-URL /public_api/v1 normalization.
  2. connector helpers — the _xsiam_wrap error envelope + _xsiam_ok/_xsiam_err.
  3. A representative read tool (incidents_list) and a representative EDR-response
     tool (endpoints_isolate) — request shaping via a recording fetcher.
  4. __all__ integrity — the 54 ported tools are exported + callable, and the
     dropped Phantom-simulation tools are gone.

Run with:
  cd bundles/spark/connectors/xsiam && python3 -m pytest tests/ -x
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Optional

import pytest

# Make the connector package importable (mirrors the runtime's path injection).
SRC_PARENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SRC_PARENT))

from src import connector  # noqa: E402
from src._papi_client import Fetcher  # noqa: E402


def run(coro):
    return asyncio.run(coro)


# ─── 1. Fetcher: auth headers + URL normalization ────────────────────


def test_fetcher_builds_cortex_auth_headers():
    f = Fetcher("https://api-x.xdr.us.paloaltonetworks.com/public_api/v1", "KEY", "ID7")
    h = f._build_headers()
    assert h["x-xdr-auth-id"] == "ID7"
    assert h["Authorization"] == "KEY"
    assert h["Content-Type"] == "application/json"


@pytest.mark.parametrize(
    "api_url,expected",
    [
        ("https://api-x.xdr.us.paloaltonetworks.com",
         "https://api-x.xdr.us.paloaltonetworks.com/public_api/v1"),
        ("https://api-x.xdr.us.paloaltonetworks.com/",
         "https://api-x.xdr.us.paloaltonetworks.com/public_api/v1"),
        ("https://api-x.xdr.us.paloaltonetworks.com/public_api/v1",
         "https://api-x.xdr.us.paloaltonetworks.com/public_api/v1"),
    ],
)
def test_get_fetcher_normalizes_base_url(monkeypatch, api_url, expected):
    monkeypatch.setattr(
        connector, "_get_xsiam_config",
        lambda: {"api_url": api_url, "api_id": "ID", "api_key": "KEY"},
    )
    f = connector._get_fetcher()
    assert f.url == expected
    assert f.api_key == "KEY" and f.api_key_id == "ID"


def test_get_fetcher_requires_api_url(monkeypatch):
    monkeypatch.setattr(
        connector, "_get_xsiam_config",
        lambda: {"api_url": None, "api_id": "ID", "api_key": "KEY"},
    )
    with pytest.raises(ValueError, match="api_url"):
        connector._get_fetcher()


def test_get_fetcher_requires_api_id(monkeypatch):
    monkeypatch.setattr(
        connector, "_get_xsiam_config",
        lambda: {"api_url": "https://x", "api_id": None, "api_key": "KEY"},
    )
    with pytest.raises(ValueError, match="api_id"):
        connector._get_fetcher()


# ─── 2. Error envelope ───────────────────────────────────────────────


def test_xsiam_ok_and_err_shape():
    ok = connector._xsiam_ok({"a": 1})
    assert ok == {"ok": True, "success": True, "a": 1}
    err = connector._xsiam_err("boom", code=1)
    assert err == {"ok": False, "success": False, "error": "boom", "code": 1}


def test_xsiam_wrap_catches_exceptions():
    @connector._xsiam_wrap
    async def boom():
        raise RuntimeError("nope")

    out = run(boom())
    assert out["ok"] is False and out["success"] is False
    assert "RuntimeError" in out["error"]


# ─── 3. Tool request shaping (recording fetcher) ─────────────────────


class _RecordingFetcher:
    def __init__(self, reply: Optional[dict] = None):
        self.reply = reply if reply is not None else {}
        self.calls: list[tuple[str, str, Any]] = []

    async def send_request(self, path, method="POST", data=None):
        self.calls.append((method, path, data))
        return self.reply


def _install(monkeypatch, rf):
    monkeypatch.setattr(connector, "_get_fetcher", lambda: rf)


def test_incidents_list_shapes_request(monkeypatch):
    rf = _RecordingFetcher({"reply": {"incidents": [{"incident_id": "1"}]}})
    _install(monkeypatch, rf)
    out = run(connector.xsiam_incidents_list(status="new", search_to=50))
    assert out["ok"] is True
    assert out["incidents"] == [{"incident_id": "1"}]
    method, path, data = rf.calls[0]
    assert path == "/incidents/get_incidents/"
    rd = data["request_data"]
    assert rd["search_to"] == 50
    assert {"field": "status", "operator": "eq", "value": "new"} in rd["filters"]


def test_endpoints_isolate_shapes_request(monkeypatch):
    rf = _RecordingFetcher({"reply": {"action_id": "A1", "endpoints_count": 2}})
    _install(monkeypatch, rf)
    out = run(connector.xsiam_endpoints_isolate(endpoint_id_list=["e1"]))
    assert out["ok"] is True
    assert out["action_id"] == "A1"
    assert out["endpoints_affected"] == 2
    method, path, data = rf.calls[0]
    assert path == "/endpoints/isolate/"
    assert "filters" in data["request_data"]


def test_endpoints_isolate_requires_a_filter(monkeypatch):
    rf = _RecordingFetcher({})
    _install(monkeypatch, rf)
    out = run(connector.xsiam_endpoints_isolate())
    assert out["ok"] is False and "filter" in out["error"]
    assert rf.calls == []  # never hit the API


# ─── 4. __all__ integrity ────────────────────────────────────────────

_DROPPED = {
    "xsiam_get_cases", "xsiam_send_webhook_log", "xsiam_find_xql_examples_rag",
    "xsiam_get_dataset_fields", "xsiam_get_xql_examples",
}


def test_all_exports_are_callable_and_dropped_tools_gone():
    assert len(connector.__all__) == 54
    for name in connector.__all__:
        assert callable(getattr(connector, name)), f"{name} not callable"
        assert name not in _DROPPED
    for name in _DROPPED:
        assert not hasattr(connector, name), f"dropped tool still present: {name}"
