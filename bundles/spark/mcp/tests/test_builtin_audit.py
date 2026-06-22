"""#73 — built-in tools emit a `tool_call` audit row via `_wrap_builtin`.

Built-in legacy tools (memory_*, sessions_*, knowledge_*, jobs_*, the
investigation issue_/case_/indicator_ tools, skills_*) are not part of any
connector, so they never pass through `_wrap_with_instance` — the sole emitter
of ACTION_TOOL_CALL. Before this shim a session/job that called only built-ins
left no tool_call row → invisible in /observability/events + /traces.
"""

import asyncio
import inspect

import pytest

from usecase import audit_log as audit_mod
from usecase.connector_loader import _wrap_builtin


def test_sync_builtin_emits_tool_call_success(monkeypatch):
    calls = []
    monkeypatch.setattr(audit_mod, "record_event", lambda action, **kw: calls.append((action, kw)))

    def fn(a, b=2):
        return a + b

    wrapped = _wrap_builtin("memory_store", fn)
    assert wrapped(1, b=3) == 4

    assert len(calls) == 1
    action, kw = calls[0]
    assert action == audit_mod.ACTION_TOOL_CALL
    assert kw["status"] == "success"
    assert kw["target"] == "tool:memory_store"
    assert kw["actor"] == "agent"
    assert kw["metadata"]["tool"] == "memory_store"
    assert kw["metadata"]["connector_id"] is None
    # only KEY names recorded — never values (the value 3 must not leak)
    assert kw["metadata"]["arg_keys"] == ["b", "<1 positional>"]
    assert isinstance(kw["duration_ms"], int)


def test_sync_builtin_emits_failure_and_reraises(monkeypatch):
    calls = []
    monkeypatch.setattr(audit_mod, "record_event", lambda action, **kw: calls.append((action, kw)))

    def boom():
        raise ValueError("nope")

    wrapped = _wrap_builtin("jobs_list", boom)
    with pytest.raises(ValueError):
        wrapped()

    assert len(calls) == 1
    assert calls[0][1]["status"] == "failure"
    assert "ValueError" in calls[0][1]["metadata"]["error"]


def test_async_builtin_emits_tool_call(monkeypatch):
    calls = []
    monkeypatch.setattr(audit_mod, "record_event", lambda action, **kw: calls.append((action, kw)))

    async def afn(x):
        return x * 2

    wrapped = _wrap_builtin("knowledge_search", afn)
    assert inspect.iscoroutinefunction(wrapped)
    assert asyncio.run(wrapped(5)) == 10
    assert calls[0][1]["status"] == "success"
    assert calls[0][1]["target"] == "tool:knowledge_search"


def test_wrap_preserves_signature():
    def fn(query: str, limit: int = 10):
        return []

    wrapped = _wrap_builtin("memory_search", fn)
    params = inspect.signature(wrapped).parameters
    assert "query" in params and "limit" in params


def test_audit_write_failure_never_breaks_the_call(monkeypatch):
    def explode(*a, **k):
        raise RuntimeError("audit sink down")

    monkeypatch.setattr(audit_mod, "record_event", explode)

    def fn():
        return "ok"

    wrapped = _wrap_builtin("sessions_list", fn)
    # record_event raising must not mask the real return value.
    assert wrapped() == "ok"
