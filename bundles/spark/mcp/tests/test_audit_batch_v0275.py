"""v0.2.75 audit batch — CHAT subsystem audit-trace gaps.

Covers the pure-Python sites in this batch:

  * audit_log constants — the operator-state mutation action strings (promoted
    from bare literals to named constants in #CHAT-F14) exist and resolve to
    the expected values, so a typo can't silently emit an unknown action.
  * manifest — every NEW v0.2.75 action string is declared under
    audit.events (the TS-emitted chat_* actions + the now-declared
    operator_state_set/delete).
  * #CHAT-F14 — the operator-state PUT/DELETE handlers attribute their audit
    row to the X-Guardian-Actor the proxy forwards (apikey:<id> | user:operator)
    instead of the hardcoded "user:operator". The chat subagents-enabled toggle
    flows through PUT, so this is the toggle's attribution.

The TypeScript sites (CHAT-F4/F5/F6/F8/F9/F10/F19/F21/F25 in the chat route,
use-chat, page.tsx, operator-state proxy) are validated by the tsc gate + live
smoke; this file covers the Python sites.

Repo has NO pytest-asyncio — async route handlers are driven via asyncio.run().
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from starlette.requests import Request  # noqa: E402

from usecase import audit_log as audit_mod  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# audit_log — new operator-state mutation constants (#CHAT-F14)
# ─────────────────────────────────────────────────────────────────


def test_operator_state_mutation_constants_declared():
    assert audit_mod.ACTION_OPERATOR_STATE_SET == "operator_state_set"
    assert audit_mod.ACTION_OPERATOR_STATE_DELETE == "operator_state_delete"


# ─────────────────────────────────────────────────────────────────
# manifest — every NEW v0.2.75 action declared under audit.events
# ─────────────────────────────────────────────────────────────────


def test_new_actions_declared_in_manifest():
    import yaml

    manifest_path = Path(__file__).resolve().parents[2] / "manifest.yaml"
    events = set(yaml.safe_load(manifest_path.read_text())["audit"]["events"])
    for value in (
        # TS-emitted chat-route actions.
        "chat_turn_retried",
        "chat_response_blocked",
        "chat_tool_call_suppressed",
        "chat_tool_cache_hit",
        "chat_model_changed",
        "chat_slash_command",
        "chat_context_blocked",
        # #CHAT-F14 — operator-state mutations (already emitted, now declared).
        "operator_state_set",
        "operator_state_delete",
    ):
        assert value in events, f"{value!r} missing from manifest audit.events"


# ─────────────────────────────────────────────────────────────────
# #CHAT-F14 — operator-state PUT/DELETE attribute to forwarded actor
# ─────────────────────────────────────────────────────────────────


class _CapturingMcp:
    """Captures the handlers register_operator_state_routes wires up so the test
    can invoke them directly (keyed by '<METHOD> <path>')."""

    def __init__(self) -> None:
        self.routes: dict[str, Any] = {}

    def custom_route(self, path: str, methods: list[str], **_kw: Any):
        def deco(fn):
            for m in methods:
                self.routes[f"{m} {path}"] = fn
            return fn

        return deco


def _make_request(method: str, key: str, *, actor: str | None, body: bytes = b"") -> Request:
    """Build a Starlette Request with the bearer + optional X-Guardian-Actor."""
    headers = [(b"authorization", b"Bearer test-mcp-token")]
    if actor is not None:
        headers.append((b"x-guardian-actor", actor.encode()))
    if body:
        headers.append((b"content-type", b"application/json"))
    scope = {
        "type": "http",
        "method": method,
        "path": f"/api/v1/operator-state/{key}",
        "headers": headers,
        "path_params": {"key": key},
        "query_string": b"",
    }

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(scope, receive)


def _wire_real_audit(tmp_path, monkeypatch) -> audit_mod.SqliteAuditLog:
    """Use a REAL SqliteAuditLog so the contextvar-resolved actor lands in the
    row's actor column (the fake sink only captures kwargs, which is None here
    because the route relies on the actor contextvar, not an explicit kwarg)."""
    log = audit_mod.SqliteAuditLog(data_root=tmp_path)
    monkeypatch.setattr(audit_mod, "_audit", log)
    return log


def _build_routes(tmp_path, monkeypatch):
    from api.operator_state import register_operator_state_routes
    from config.config import config as cfg
    from usecase.operator_state_store import OperatorStateStore

    # Pass the bearer check: require_bearer compares against config.mcp_token.
    # The Settings singleton is loaded at import, so set the attribute directly
    # (monkeypatch.setenv would not retroactively reload it).
    monkeypatch.setattr(cfg, "mcp_token", "test-mcp-token", raising=False)
    store = OperatorStateStore(data_root=tmp_path)
    mcp = _CapturingMcp()
    register_operator_state_routes(mcp, store)
    return mcp, store


def test_put_attributes_forwarded_actor(tmp_path, monkeypatch):
    log = _wire_real_audit(tmp_path, monkeypatch)
    mcp, _store = _build_routes(tmp_path, monkeypatch)
    put = mcp.routes["PUT /api/v1/operator-state/{key}"]

    req = _make_request(
        "PUT",
        "chat_subagents_enabled",
        actor="apikey:abc123",
        body=b'{"value": false}',
    )
    resp = asyncio.run(put(req))
    assert resp.status_code == 200

    rows = log.query(action="operator_state_set")
    assert len(rows) == 1
    assert rows[0]["actor"] == "apikey:abc123"
    assert rows[0]["target"] == "operator-state:chat_subagents_enabled"


def test_put_defaults_to_user_operator_without_header(tmp_path, monkeypatch):
    log = _wire_real_audit(tmp_path, monkeypatch)
    mcp, _store = _build_routes(tmp_path, monkeypatch)
    put = mcp.routes["PUT /api/v1/operator-state/{key}"]

    req = _make_request(
        "PUT", "tested_journeys", actor=None, body=b'{"value": ["a"]}'
    )
    resp = asyncio.run(put(req))
    assert resp.status_code == 200

    rows = log.query(action="operator_state_set")
    assert len(rows) == 1
    # Absent header preserves the legacy default rather than the MCP's "system".
    assert rows[0]["actor"] == "user:operator"


def test_delete_attributes_forwarded_actor(tmp_path, monkeypatch):
    log = _wire_real_audit(tmp_path, monkeypatch)
    mcp, store = _build_routes(tmp_path, monkeypatch)
    store.put("scratch_key", "v")

    delete = mcp.routes["DELETE /api/v1/operator-state/{key}"]
    req = _make_request("DELETE", "scratch_key", actor="user:operator")
    resp = asyncio.run(delete(req))
    assert resp.status_code == 204

    rows = log.query(action="operator_state_delete")
    assert len(rows) == 1
    assert rows[0]["actor"] == "user:operator"
    assert rows[0]["target"] == "operator-state:scratch_key"
