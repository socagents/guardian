"""#CDW-F11 — the web connector now has a real health probe.

Pre-fix the instance Test endpoint returned probe_implemented:false for
the web connector WITHOUT contacting anything, so an operator couldn't
tell a down browser sidecar from a healthy one. real_probe('web') now
hits the Chromium CDP /json/version endpoint.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import usecase.connector_probes as probes  # noqa: E402


def test_web_is_probe_implemented():
    assert "web" in probes.PROBE_IMPLEMENTED


class _FakeResp:
    def __init__(self, status: int):
        self.status_code = status


class _FakeClient:
    status = 200
    last_url = ""

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url):
        _FakeClient.last_url = url
        return _FakeResp(_FakeClient.status)


def test_web_probe_ok(monkeypatch):
    _FakeClient.status = 200
    monkeypatch.setattr(probes.httpx, "AsyncClient", _FakeClient)
    ok, err, is_auth = asyncio.run(
        probes.real_probe("web", config={"cdp_url": "http://guardian-browser:9222"})
    )
    assert ok is True and err is None and is_auth is False
    assert _FakeClient.last_url == "http://guardian-browser:9222/json/version"


def test_web_probe_down(monkeypatch):
    _FakeClient.status = 502
    monkeypatch.setattr(probes.httpx, "AsyncClient", _FakeClient)
    ok, err, is_auth = asyncio.run(
        probes.real_probe("web", config={"cdp_url": "http://guardian-browser:9222"})
    )
    assert ok is False
    assert "502" in err


def test_web_probe_ws_url_normalized(monkeypatch):
    # CDP config may be a ws:// URL; the version endpoint is HTTP.
    _FakeClient.status = 200
    monkeypatch.setattr(probes.httpx, "AsyncClient", _FakeClient)
    asyncio.run(
        probes.real_probe("web", config={"cdp_url": "ws://guardian-browser:9222"})
    )
    assert _FakeClient.last_url.startswith("http://")
