"""#PLAT-F11 — plugin pip install/uninstall is MCP-token-only + approval-gated.

Covers the two pure helpers added to api/plugin_entry_points_routes.py:
  * _require_mcp_token  — refuses non-MCP_TOKEN principals (API keys) with 403
  * _gate_pip_op        — drives the approvals bus; denies/timeouts return an
                          error response, approval returns None, no-bus fails
                          open to the MCP-token-only protection.
"""

import asyncio
import types

from api import plugin_entry_points_routes as mod


def _req(principal):
    return types.SimpleNamespace(state=types.SimpleNamespace(auth_principal=principal))


def test_require_mcp_token_refuses_api_key():
    resp = mod._require_mcp_token(_req("api_key:abc123"))
    assert resp is not None and resp.status_code == 403


def test_require_mcp_token_allows_mcp_token():
    assert mod._require_mcp_token(_req("mcp_token")) is None


def test_require_mcp_token_refuses_missing_principal():
    resp = mod._require_mcp_token(types.SimpleNamespace(state=types.SimpleNamespace()))
    assert resp is not None and resp.status_code == 403


class _FakeBus:
    def __init__(self, status):
        self._status = status
        self.requested = None

    def request(self, *, tool, namespaced, actor, args, risk_tier):
        self.requested = {"tool": tool, "risk_tier": risk_tier, "args": args}
        return "appr-1"

    async def wait_async(self, approval_id, timeout=None):
        return self._status, "because"


def _gate(monkeypatch, bus):
    import usecase.approvals_bus as bus_mod

    monkeypatch.setattr(bus_mod, "approvals_bus", lambda: bus)
    return asyncio.run(mod._gate_pip_op(tool="plugin_entry_install", args={"spec": "evil==1.0"}))


def test_gate_approved_returns_none(monkeypatch):
    bus = _FakeBus("approved")
    assert _gate(monkeypatch, bus) is None
    # the request was opened destructive-tier with the spec attached
    assert bus.requested["risk_tier"] == "destructive"
    assert bus.requested["args"]["spec"] == "evil==1.0"


def test_gate_denied_returns_403(monkeypatch):
    resp = _gate(monkeypatch, _FakeBus("denied"))
    assert resp is not None and resp.status_code == 403


def test_gate_timeout_returns_408(monkeypatch):
    resp = _gate(monkeypatch, _FakeBus("timeout"))
    assert resp is not None and resp.status_code == 408


def test_gate_no_bus_fails_open(monkeypatch):
    import usecase.approvals_bus as bus_mod

    monkeypatch.setattr(bus_mod, "approvals_bus", lambda: None)
    # No bus wired → fall through to the MCP-token-only protection (None).
    assert asyncio.run(mod._gate_pip_op(tool="plugin_entry_install", args={})) is None
