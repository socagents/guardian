"""The XSIAM instance probe must honor auth_type.

Regression: v0.2.86 added Advanced (signed) auth to the connector's Fetcher,
but the separate probe in connector_probes.py kept doing Standard auth only —
so "Test Connection" 401'd a perfectly valid Advanced key. The probe now signs
when auth_type == advanced, matching the Fetcher (and the real Cortex API).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import usecase.connector_probes as probes  # noqa: E402


def test_xsiam_is_probe_implemented():
    assert "xsiam" in probes.PROBE_IMPLEMENTED


# ─── unit: the header builder ────────────────────────────────────────


def test_xsiam_headers_standard_sends_key_verbatim():
    h = probes._xsiam_papi_headers("VERBATIM_KEY", "101", "standard")
    assert h["Authorization"] == "VERBATIM_KEY"
    assert h["x-xdr-auth-id"] == "101"
    assert "x-xdr-nonce" not in h and "x-xdr-timestamp" not in h


def test_xsiam_headers_advanced_signs_request():
    h = probes._xsiam_papi_headers("THEKEY", "107", "advanced")
    assert h["Authorization"] != "THEKEY"          # signed, not verbatim
    assert len(h["Authorization"]) == 64           # sha256 hexdigest
    assert len(h["x-xdr-nonce"]) == 64
    assert h["x-xdr-timestamp"].isdigit()
    assert h["x-xdr-auth-id"] == "107"


# ─── integration: real_probe wires auth_type through ─────────────────


class _CapturingClient:
    status = 200
    last_headers: dict = {}

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        _CapturingClient.last_headers = headers or {}

        class _R:
            status_code = _CapturingClient.status

        return _R()


def _run_xsiam(monkeypatch, auth_type):
    monkeypatch.setattr(probes.httpx, "AsyncClient", _CapturingClient)
    return asyncio.run(
        probes.real_probe(
            "xsiam",
            config={"api_url": "https://api-x.xdr.eu.paloaltonetworks.com",
                    "api_id": "107", "auth_type": auth_type},
            secrets={"api_key": "SECRET_KEY"},
        )
    )


def test_xsiam_probe_advanced_signs(monkeypatch):
    _CapturingClient.status = 200
    ok, err, _ = _run_xsiam(monkeypatch, "advanced")
    assert ok is True and err is None
    h = _CapturingClient.last_headers
    assert h["Authorization"] != "SECRET_KEY"      # signed
    assert "x-xdr-nonce" in h and "x-xdr-timestamp" in h


def test_xsiam_probe_standard_verbatim(monkeypatch):
    _CapturingClient.status = 200
    _run_xsiam(monkeypatch, "standard")
    h = _CapturingClient.last_headers
    assert h["Authorization"] == "SECRET_KEY"
    assert "x-xdr-nonce" not in h


def test_xsiam_probe_401_is_auth_error(monkeypatch):
    _CapturingClient.status = 401
    ok, err, is_auth = _run_xsiam(monkeypatch, "advanced")
    assert ok is False and is_auth is True
    assert "401" in err
