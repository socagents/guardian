"""v0.2.82 coverage-fixes batch — audit actor attribution, contextvar
propagation on the ^tool path, and KB audit hygiene.

Covers the pure-Python sites changed in this batch (the #57-72 residual run):

  * F-actor-hardcode — usecase.audit_log.resolve_tool_actor() resolves the
    REAL forwarded principal (operator / ^tool / API-key) and only falls back
    to "agent" for the ambient "system"/"agent" defaults — so the connector
    wrappers + _wrap_builtin stop hardcoding actor="agent" on every tool_call.
  * F-ctxvar — TriggerContextMiddleware is now a PURE ASGI middleware, so the
    trigger/actor/chain_id contextvars survive into a child task spawned the
    way FastMCP spawns its streamable-HTTP tool-execution task (the ^tool path
    that previously dropped trigger/chain_id to NULL). BaseHTTPMiddleware ran
    dispatch in a separate task, so they didn't propagate.
  * F-kb-double-docread — kb_store.get_doc() no longer emits kb_doc_read (the
    REST handler is the single, richer emitter).
  * F-kb-double-search — kb_store.search(_emit_audit=False) suppresses the
    inner kb_searched row so the active knowledge_search tool emits exactly
    one (its own, richer mode=active) row.
  * F-kb-active-preview — the active knowledge_search + the store search rows
    carry a bounded query_preview (<=200 chars), like the passive path.

CI-only deps (skipped locally): starlette (the ASGI middleware test),
pydantic (the connector_loader _wrap_builtin tests). The repo has NO
pytest-asyncio — async paths are driven via asyncio.run().
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from usecase import audit_log as audit_mod  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Shared fakes
# ─────────────────────────────────────────────────────────────────


class _FakeAudit:
    """Stand-in audit sink: record(action, **kw) appends to .calls.

    Mirrors the real SqliteAuditLog.record contract — when actor is None it
    resolves from the contextvar, so the fake captures the EFFECTIVE actor the
    way the real recorder would.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def record(self, action: str, **kw: Any) -> str:
        if kw.get("actor") is None:
            kw["actor"] = audit_mod.get_current_actor()
        self.calls.append((action, kw))
        return "row-id"

    def rows(self, action: str) -> list[dict[str, Any]]:
        return [kw for a, kw in self.calls if a == action]


def _wire_audit(monkeypatch) -> _FakeAudit:
    fake = _FakeAudit()
    monkeypatch.setattr(audit_mod, "_audit", fake)
    return fake


# ─────────────────────────────────────────────────────────────────
# F-actor-hardcode — resolve_tool_actor()
# ─────────────────────────────────────────────────────────────────


def test_resolve_tool_actor_falls_back_to_agent_when_unset():
    # No actor header set → contextvar default → ambient "system" → "agent".
    # (model-internal / ambient tool call stays attributed to the agent.)
    assert audit_mod.resolve_tool_actor() == "agent"


def test_resolve_tool_actor_treats_system_as_ambient():
    tok = audit_mod.set_current_actor("system")
    try:
        assert audit_mod.resolve_tool_actor() == "agent"
    finally:
        audit_mod.reset_current_actor(tok)


def test_resolve_tool_actor_treats_agent_as_ambient():
    tok = audit_mod.set_current_actor("agent")
    try:
        assert audit_mod.resolve_tool_actor() == "agent"
    finally:
        audit_mod.reset_current_actor(tok)


def test_resolve_tool_actor_preserves_forwarded_operator():
    tok = audit_mod.set_current_actor("user:operator")
    try:
        assert audit_mod.resolve_tool_actor() == "user:operator"
    finally:
        audit_mod.reset_current_actor(tok)


def test_resolve_tool_actor_preserves_forwarded_apikey():
    # The normalized apikey:<id> form (F-actor-format) flows through untouched.
    tok = audit_mod.set_current_actor("apikey:abc123")
    try:
        assert audit_mod.resolve_tool_actor() == "apikey:abc123"
    finally:
        audit_mod.reset_current_actor(tok)


# ─────────────────────────────────────────────────────────────────
# F-actor-hardcode — _wrap_builtin records the resolved actor
# (CI-only: connector_loader needs pydantic)
# ─────────────────────────────────────────────────────────────────


def _wrap_builtin():
    pytest.importorskip("pydantic")
    from usecase.connector_loader import _wrap_builtin as wb
    return wb


def test_wrap_builtin_ambient_attributes_to_agent(monkeypatch):
    wb = _wrap_builtin()
    fake = _wire_audit(monkeypatch)

    def fn():
        return "ok"

    # No forwarded principal in scope → "agent".
    assert wb("memory_store", fn)() == "ok"
    rows = fake.rows(audit_mod.ACTION_TOOL_CALL)
    assert len(rows) == 1
    assert rows[0]["actor"] == "agent"


def test_wrap_builtin_forwarded_principal_attributes_to_it(monkeypatch):
    wb = _wrap_builtin()
    fake = _wire_audit(monkeypatch)

    def fn():
        return "ok"

    # A real forwarded principal (e.g. a ^tool / API-key driven call) must be
    # recorded, NOT clobbered to "agent".
    tok = audit_mod.set_current_actor("apikey:zzz")
    try:
        assert wb("jobs_list", fn)() == "ok"
    finally:
        audit_mod.reset_current_actor(tok)

    rows = fake.rows(audit_mod.ACTION_TOOL_CALL)
    assert len(rows) == 1
    assert rows[0]["actor"] == "apikey:zzz"


def test_wrap_builtin_does_not_clobber_contextvar_for_nested_records(monkeypatch):
    """The wrapper must set the contextvar to the RESOLVED actor (not a blanket
    "agent"), so a record_event the inner fn emits also attributes correctly."""
    wb = _wrap_builtin()
    fake = _wire_audit(monkeypatch)

    def fn():
        # Inner emission with actor=None → resolves from contextvar.
        audit_mod.record_event("memory_stored", target="m:1")
        return "ok"

    tok = audit_mod.set_current_actor("user:operator")
    try:
        assert wb("memory_store", fn)() == "ok"
    finally:
        audit_mod.reset_current_actor(tok)

    inner = fake.rows("memory_stored")
    assert len(inner) == 1
    assert inner[0]["actor"] == "user:operator"
    # and the tool_call row too
    assert fake.rows(audit_mod.ACTION_TOOL_CALL)[0]["actor"] == "user:operator"


# ─────────────────────────────────────────────────────────────────
# F-kb-double-search / F-kb-active-preview — active knowledge_search
# emits exactly one row + bounded query_preview (no inner duplicate)
# ─────────────────────────────────────────────────────────────────


class _StubDoc:
    def to_dict(self, include_content=True, score=None):
        return {"id": "d1", "score": score}


class _StubKb:
    """Stub whose search() records whether the suppression flag arrived."""

    def __init__(self, docs):
        self._docs = docs
        self.last_emit_audit = None

    def search(self, query, kb_name=None, category=None, tags=None, limit=5,
               _emit_audit=True):
        self.last_emit_audit = _emit_audit
        return [(d, 0.9) for d in self._docs]


def test_knowledge_search_single_row_with_bounded_preview(monkeypatch):
    from usecase.builtin_components import cognitive_tools

    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event",
        lambda action, **kw: calls.append((action, kw)),
    )
    stub = _StubKb([_StubDoc()])
    monkeypatch.setattr("usecase.kb_store.knowledge_base", lambda: stub)

    out = cognitive_tools.knowledge_search("phishing iocs", limit=3)
    assert out["count"] == 1

    # the active tool suppressed the inner store emission
    assert stub.last_emit_audit is False

    rows = [kw for a, kw in calls if a == audit_mod.ACTION_KB_SEARCHED]
    # exactly ONE row (no duplicate mode=None inner row)
    assert len(rows) == 1
    assert rows[0]["metadata"]["mode"] == "active"
    # bounded preview present + <=200 chars
    assert rows[0]["metadata"]["query_preview"] == "phishing iocs"
    assert len(rows[0]["metadata"]["query_preview"]) <= 200


def test_knowledge_search_preview_is_bounded_to_200(monkeypatch):
    from usecase.builtin_components import cognitive_tools

    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event",
        lambda action, **kw: calls.append((action, kw)),
    )
    monkeypatch.setattr(
        "usecase.kb_store.knowledge_base", lambda: _StubKb([_StubDoc()])
    )

    long_q = "x" * 500
    cognitive_tools.knowledge_search(long_q)
    rows = [kw for a, kw in calls if a == audit_mod.ACTION_KB_SEARCHED]
    assert len(rows) == 1
    assert len(rows[0]["metadata"]["query_preview"]) == 200


# ─────────────────────────────────────────────────────────────────
# F-kb-double-search — kb_store.search(_emit_audit=False) suppresses the
# inner kb_searched emission (success + failure paths)
# ─────────────────────────────────────────────────────────────────


class _BoomEmbedder:
    dims = 8
    model_id = "boom-embedder"

    def embed(self, text: str) -> list[float]:
        raise RuntimeError("vertex unreachable: simulated outage")


def test_kb_search_emit_audit_false_suppresses_failure_row(tmp_path, monkeypatch):
    from usecase.kb_store import SqliteKnowledgeBase

    fake = _wire_audit(monkeypatch)
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=_BoomEmbedder())

    with pytest.raises(RuntimeError):
        kb.search("anything", kb_name="soc", _emit_audit=False)

    # the outer layer owns the emission; the inner store stays silent
    assert fake.rows("kb_searched") == []


def test_kb_search_default_still_emits_failure_row(tmp_path, monkeypatch):
    """Regression guard — the REST/passive paths (default _emit_audit=True) keep
    their failure trace (KB-F11)."""
    from usecase.kb_store import SqliteKnowledgeBase

    fake = _wire_audit(monkeypatch)
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=_BoomEmbedder())

    with pytest.raises(RuntimeError):
        kb.search("anything", kb_name="soc")

    rows = fake.rows("kb_searched")
    assert len(rows) == 1
    assert rows[0]["status"] == "failure"
    # F-kb-active-preview — the store row now carries a bounded preview too
    assert rows[0]["metadata"]["query_preview"] == "anything"


# ─────────────────────────────────────────────────────────────────
# F-kb-double-docread — kb_store.get_doc() no longer emits kb_doc_read
# ─────────────────────────────────────────────────────────────────


def test_get_doc_emits_no_kb_doc_read(tmp_path, monkeypatch):
    from usecase.kb_store import SqliteKnowledgeBase

    fake = _wire_audit(monkeypatch)
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=_BoomEmbedder())
    # Insert one doc with a pre-computed vector so the boom embedder never runs
    # (model_id + dims match → trusted, no live embed call).
    kb.upsert(
        kb_name="soc",
        doc_id="d1",
        content="c",
        title="t",
        category="cat",
        source_hash="h1",
        precomputed_embedding=[0.0] * _BoomEmbedder.dims,
        precomputed_model=_BoomEmbedder.model_id,
    )
    fake.calls.clear()  # drop the index rows; we only care about get_doc

    doc = kb.get_doc("soc", "d1")
    assert doc is not None
    # the store layer is silent — the REST handler is the single emitter
    assert fake.rows("kb_doc_read") == []


# ─────────────────────────────────────────────────────────────────
# F-ctxvar — TriggerContextMiddleware (pure ASGI) propagates contextvars
# into a child task spawned the way FastMCP spawns its tool-exec task.
# (CI-only: needs starlette)
# ─────────────────────────────────────────────────────────────────


def test_trigger_context_propagates_into_child_task():
    """The crux of F-ctxvar: a BaseHTTPMiddleware set the contextvar in a task
    SEPARATE from the endpoint, so a child task (FastMCP's tool-exec task)
    spawned from the endpoint never saw it. The pure-ASGI middleware sets it in
    the SAME task that awaits the app, so a child task spawned from inside the
    app inherits it via contextvars.copy_context()."""
    pytest.importorskip("starlette")
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from api.trigger_context import TriggerContextMiddleware
    from usecase.audit_log import (
        get_current_chain_id,
        get_current_trigger,
        get_current_actor,
    )

    async def _endpoint(request):
        # Spawn a child task the way FastMCP spawns its tool-execution task.
        # It captures the current context at creation; with a pure ASGI
        # middleware the contextvars are already set in THIS task.
        async def _child():
            return {
                "trigger": get_current_trigger(),
                "chain_id": get_current_chain_id(),
                "actor": get_current_actor(),
            }

        captured = await asyncio.ensure_future(_child())
        return JSONResponse(captured)

    app = Starlette(routes=[Route("/run", _endpoint)])
    app.add_middleware(TriggerContextMiddleware)
    client = TestClient(app)

    r = client.get(
        "/run",
        headers={
            "X-Guardian-Trigger": "job:nightly",
            "X-Guardian-Chain-Id": "ch_abc",
            "X-Guardian-Actor": "apikey:k1",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["trigger"] == "job:nightly"
    assert body["chain_id"] == "ch_abc"
    assert body["actor"] == "apikey:k1"


def test_trigger_context_resets_after_request():
    pytest.importorskip("starlette")
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from api.trigger_context import TriggerContextMiddleware
    from usecase.audit_log import get_current_trigger, get_current_chain_id

    async def _ok(request):
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/ok", _ok)])
    app.add_middleware(TriggerContextMiddleware)
    client = TestClient(app)
    client.get(
        "/ok",
        headers={"X-Guardian-Trigger": "job:x", "X-Guardian-Chain-Id": "ch_x"},
    )
    # no cross-request leak
    assert get_current_trigger() is None
    assert get_current_chain_id() is None
