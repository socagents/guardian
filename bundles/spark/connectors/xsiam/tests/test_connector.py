"""xsiam connector — unit tests.

No network. Covers:
  1. _papi_client.Fetcher — the Cortex public-API auth headers
     (x-xdr-auth-id + Authorization) + base-URL /public_api/v1 normalization.
  2. connector helpers — the _xsiam_wrap error envelope + _xsiam_ok/_xsiam_err.
  3. A representative read tool (incidents_list) and a representative EDR-response
     tool (endpoints_isolate) — request shaping via a recording fetcher.
  4. __all__ integrity — the 55 tools are exported + callable, and the
     dropped simulation-only tools are gone.
  5. compute-unit cost surfacing (run_xql_query) + get_xql_quota (v0.2.91).

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


def test_fetcher_standard_auth_headers_default():
    # auth_type defaults to "standard" (backwards-compatible): api_key sent
    # verbatim, no nonce/timestamp. Tested with the field omitted AND explicit.
    for f in (
        Fetcher("https://api-x.xdr.us.paloaltonetworks.com/public_api/v1", "KEY", "ID7"),
        Fetcher("https://api-x.xdr.us.paloaltonetworks.com/public_api/v1",
                "KEY", "ID7", auth_type="standard"),
    ):
        h = f._build_headers()
        assert h["x-xdr-auth-id"] == "ID7"
        assert h["Authorization"] == "KEY"
        assert h["Content-Type"] == "application/json"
        assert "x-xdr-nonce" not in h and "x-xdr-timestamp" not in h


def test_fetcher_advanced_auth_headers():
    import hashlib

    # auth_type="advanced": Authorization is sha256(api_key + nonce + timestamp),
    # with the nonce + timestamp sent so the server can recompute + replay-check.
    f = Fetcher(
        "https://api-x.xdr.us.paloaltonetworks.com/public_api/v1",
        "KEY", "ID7", auth_type="advanced",
    )
    h = f._build_headers()
    assert h["x-xdr-auth-id"] == "ID7"
    assert h["Content-Type"] == "application/json"
    nonce, ts = h["x-xdr-nonce"], h["x-xdr-timestamp"]
    assert len(nonce) == 64 and ts.isdigit()
    assert h["Authorization"] == hashlib.sha256(
        f"KEY{nonce}{ts}".encode("utf-8")
    ).hexdigest()
    # Fresh per call — a second build yields a different nonce (+ signature).
    h2 = f._build_headers()
    assert h2["x-xdr-nonce"] != nonce
    assert h2["Authorization"] != h["Authorization"]


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


# ─── 3b. run_xql_query — lookback window + bounded poll (Stage B / v0.2.46) ───


class _XqlFetcher:
    """query_id for start_xql_query, then a scripted sequence of
    get_query_results replies (to exercise the PENDING poll loop)."""

    def __init__(self, results_sequence):
        self._results = list(results_sequence)
        self.calls: list[tuple[str, Any]] = []

    async def send_request(self, path, method="POST", data=None):
        self.calls.append((path, data))
        if path == "xql/start_xql_query":
            return {"reply": "QID-1"}
        if path == "xql/get_query_results":
            if self._results:
                return self._results.pop(0)
            return {"reply": {"status": "SUCCESS", "results": {"data": []}}}
        return {}


def _start_timeframe(rf):
    start = next(d for p, d in rf.calls if p == "xql/start_xql_query")
    return start["request_data"]["timeframe"]


def test_run_xql_default_window_is_30min(monkeypatch):
    monkeypatch.setattr(connector, "_XQL_POLL_INTERVAL_S", 0)
    rf = _XqlFetcher([{"reply": {"status": "SUCCESS", "results": {"data": [{"a": 1}]}}}])
    _install(monkeypatch, rf)
    out = run(connector.xsiam_run_xql_query(query="dataset = x | limit 1"))
    assert out["success"] is True
    tf = _start_timeframe(rf)
    span_min = (tf["to"] - tf["from"]) / 60000
    assert 29.5 <= span_min <= 30.5  # backward-compatible default


def test_run_xql_lookback_hours_widens_window(monkeypatch):
    monkeypatch.setattr(connector, "_XQL_POLL_INTERVAL_S", 0)
    rf = _XqlFetcher([{"reply": {"status": "SUCCESS", "results": {"data": []}}}])
    _install(monkeypatch, rf)
    run(connector.xsiam_run_xql_query(query="dataset = x", lookback_hours=24))
    tf = _start_timeframe(rf)
    span_h = (tf["to"] - tf["from"]) / 3_600_000
    assert 23.5 <= span_h <= 24.5


def test_run_xql_lookback_clamped_to_max(monkeypatch):
    monkeypatch.setattr(connector, "_XQL_POLL_INTERVAL_S", 0)
    rf = _XqlFetcher([{"reply": {"status": "SUCCESS", "results": {"data": []}}}])
    _install(monkeypatch, rf)
    run(connector.xsiam_run_xql_query(query="dataset = x", lookback_hours=100000))
    tf = _start_timeframe(rf)
    span_h = (tf["to"] - tf["from"]) / 3_600_000
    assert span_h <= 168.5  # clamped to 7 days


def test_run_xql_polls_until_not_pending(monkeypatch):
    monkeypatch.setattr(connector, "_XQL_POLL_INTERVAL_S", 0)
    rf = _XqlFetcher([
        {"reply": {"status": "PENDING"}},
        {"reply": {"status": "PENDING"}},
        {"reply": {"status": "SUCCESS", "results": {"data": [{"host": "h1"}]}}},
    ])
    _install(monkeypatch, rf)
    out = run(connector.xsiam_run_xql_query(query="dataset = x", lookback_hours=1))
    assert out["success"] is True
    polls = [c for c in rf.calls if c[0] == "xql/get_query_results"]
    assert len(polls) == 3  # polled through the two PENDINGs


def test_run_xql_requires_query(monkeypatch):
    rf = _XqlFetcher([])
    _install(monkeypatch, rf)
    out = run(connector.xsiam_run_xql_query(query="   "))
    assert out["success"] is False
    assert rf.calls == []  # never hit the API


# ─── 3a-cu. compute-unit cost surfacing + quota (v0.2.91) ────────────


def test_run_xql_surfaces_compute_units(monkeypatch):
    # query_cost {tenant: CU} + remaining_quota + number_of_results lift to top level.
    monkeypatch.setattr(connector, "_XQL_POLL_INTERVAL_S", 0)
    rf = _XqlFetcher([{"reply": {
        "status": "SUCCESS",
        "number_of_results": 5,
        "query_cost": {"tenant_abc": 0.0012},
        "remaining_quota": 4.9988,
        "results": {"data": [{"a": 1}]},
    }}])
    _install(monkeypatch, rf)
    out = run(connector.xsiam_run_xql_query(query="dataset = x | limit 5", lookback_hours=1))
    assert out["success"] is True
    assert out["compute_units_used"] == 0.0012
    assert out["remaining_quota_cu"] == 4.9988
    assert out["number_of_results"] == 5


def test_run_xql_quota_exceeded_returns_hint(monkeypatch):
    monkeypatch.setattr(connector, "_XQL_POLL_INTERVAL_S", 0)

    class _RaisingFetcher:
        def __init__(self, exc):
            self.exc = exc
            self.calls = []

        async def send_request(self, path, method="POST", data=None):
            self.calls.append((path, data))
            if path == "xql/start_xql_query":
                return {"reply": "QID-1"}
            raise self.exc

    rf = _RaisingFetcher(RuntimeError("HTTP 500 query usage exceeded max daily quota"))
    _install(monkeypatch, rf)
    out = run(connector.xsiam_run_xql_query(query="dataset = x", lookback_hours=1))
    assert out["success"] is False
    assert "quota" in out["error"].lower()
    assert "00:00 UTC" in out.get("hint", "")


def test_get_xql_quota_shapes_request_and_computes_remaining(monkeypatch):
    rf = _RecordingFetcher({"reply": {
        "license_quota": 655.0,
        "additional_purchased_quota": 0.0,
        "eval_quota": 0.0,
        "used_quota": 6.27,
        "daily_used_quota": 1.0,
        "total_daily_running_queries": 1514,
    }})
    _install(monkeypatch, rf)
    out = run(connector.xsiam_get_xql_quota())
    assert out["ok"] is True
    q = out["quota"]
    assert q["license_quota"] == 655.0
    assert q["daily_used_quota"] == 1.0
    assert q["remaining_annual_cu"] == 648.73  # (655 + 0 + 0) - 6.27
    method, path, data = rf.calls[0]
    assert path == "xql/get_quota"
    assert data == {"request_data": {}}


# ─── 3b. lookup datasets — create (add_dataset) + populate (add_data) ─


def test_create_dataset_shapes_add_dataset_request(monkeypatch):
    # create_dataset → POST xql/add_dataset with dataset_name/type/schema.
    rf = _RecordingFetcher({"reply": {"dataset_name": "high_value_assets"}})
    _install(monkeypatch, rf)
    out = run(connector.xsiam_create_dataset(
        dataset_name="high_value_assets",
        dataset_schema={"asset_id": "text", "risk_score": "number"},
    ))
    assert out["success"] is True
    method, path, data = rf.calls[0]
    assert path == "xql/add_dataset"
    rd = data["request_data"]
    assert rd["dataset_name"] == "high_value_assets"
    assert rd["dataset_type"] == "lookup"
    assert rd["dataset_schema"] == {"asset_id": "text", "risk_score": "number"}


def test_create_dataset_requires_name_and_schema(monkeypatch):
    rf = _RecordingFetcher({})
    _install(monkeypatch, rf)
    assert run(connector.xsiam_create_dataset(dataset_name="", dataset_schema={"a": "text"}))["success"] is False
    assert run(connector.xsiam_create_dataset(dataset_name="ds", dataset_schema={}))["success"] is False
    assert rf.calls == []


def test_add_lookup_data_sends_data_as_array_one_request(monkeypatch):
    # The XSIAM xql/lookups/add_data endpoint takes `data` as a LIST of rows,
    # sent in ONE request. A bare object makes the API skip every row.
    rf = _RecordingFetcher({"reply": {"rows added": 2}})
    _install(monkeypatch, rf)
    rows = [{"ip": "1.1.1.1"}, {"ip": "2.2.2.2"}]
    out = run(connector.xsiam_add_lookup_data(dataset_name="ioc_lookup", data=rows, key_fields=["ip"]))
    assert out["success"] is True
    assert len(rf.calls) == 1  # ONE request, not one-per-row
    _, path, data = rf.calls[0]
    assert path == "xql/lookups/add_data"
    rd = data["request_data"]
    assert rd["dataset_name"] == "ioc_lookup"
    assert rd["data"] == rows  # the whole array
    assert isinstance(rd["data"], list)
    assert rd["key_fields"] == ["ip"]


def test_add_lookup_data_wraps_single_dict_to_list(monkeypatch):
    rf = _RecordingFetcher({"reply": {"rows added": 1}})
    _install(monkeypatch, rf)
    out = run(connector.xsiam_add_lookup_data(dataset_name="ds", data={"a": 1}))
    assert out["success"] is True
    assert len(rf.calls) == 1
    assert rf.calls[0][2]["request_data"]["data"] == [{"a": 1}]  # wrapped to a list


def test_add_lookup_data_requires_dataset_and_rows(monkeypatch):
    rf = _RecordingFetcher({})
    _install(monkeypatch, rf)
    assert run(connector.xsiam_add_lookup_data(dataset_name="", data={"a": 1}))["success"] is False
    assert run(connector.xsiam_add_lookup_data(dataset_name="ds", data=[]))["success"] is False
    assert rf.calls == []  # neither hit the API


# ─── 4. __all__ integrity ────────────────────────────────────────────

_DROPPED = {
    "xsiam_get_cases", "xsiam_send_webhook_log", "xsiam_find_xql_examples_rag",
    "xsiam_get_dataset_fields", "xsiam_get_xql_examples",
}


def test_all_exports_are_callable_and_dropped_tools_gone():
    assert len(connector.__all__) == 55
    for name in connector.__all__:
        assert callable(getattr(connector, name)), f"{name} not callable"
        assert name not in _DROPPED
    for name in _DROPPED:
        assert not hasattr(connector, name), f"dropped tool still present: {name}"
