"""v0.2.54 — a tool that RETURNS an error-shaped dict ({ok:false}/{error})
without raising must be recorded status=failure (not success).

Root cause: the audit wrappers + job scheduler set "failure" only on a
raised exception, but connector tools (xsoar/xsiam) and several built-ins
report logical failure via a return value. Findings: OBS-F5, XSOAR-F1/F7,
XSIAM-F4, JOBS-F8.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from usecase import audit_log as audit_mod
from usecase import connector_loader as cl
from usecase.connector_loader import is_error_result, _wrap_builtin, _wrap_with_instance
from usecase.instance_store import Instance
from usecase.job_scheduler import CroniterJobScheduler


# ── is_error_result classification ──────────────────────────────────

def test_is_error_result_classification():
    assert is_error_result({"ok": False}) is True
    assert is_error_result({"ok": False, "error": "x"}) is True
    assert is_error_result({"error": "boom"}) is True
    assert is_error_result({"isError": True}) is True
    assert is_error_result({"ok": True}) is False
    assert is_error_result({"ok": True, "error": None}) is False
    assert is_error_result({"results": [1, 2]}) is False
    assert is_error_result({"error": None}) is False
    assert is_error_result("a string") is False
    assert is_error_result(["list"]) is False
    assert is_error_result(None) is False


# ── built-in shim ───────────────────────────────────────────────────

def test_builtin_error_result_recorded_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(audit_mod, "record_event", lambda action, **kw: calls.append((action, kw)))
    wrapped = _wrap_builtin("push_verdict_to_xsoar", lambda: {"ok": False, "error": "save failed"})
    out = wrapped()
    assert out == {"ok": False, "error": "save failed"}  # return value untouched
    kw = calls[0][1]
    assert kw["status"] == "failure"
    assert "save failed" in kw["metadata"]["error"]


def test_builtin_ok_result_recorded_success(monkeypatch):
    calls = []
    monkeypatch.setattr(audit_mod, "record_event", lambda action, **kw: calls.append((action, kw)))
    wrapped = _wrap_builtin("issues_list", lambda: {"ok": True, "issues": []})
    wrapped()
    assert calls[0][1]["status"] == "success"


# ── connector wrapper (async) ───────────────────────────────────────

def _inst(name: str) -> Instance:
    return Instance(
        id=f"id-{name}", connector_id="xsoar", name=name,
        config={"container_url": "http://x"}, secret_refs={},
        created_at="2026-01-01T00:00:00Z", enabled=True,
        container_url="http://x", disabled_tools=[],
    )


def test_connector_async_error_result_recorded_failure(monkeypatch):
    calls = []
    monkeypatch.setattr(audit_mod, "record_event", lambda action, **kw: calls.append((action, kw)))

    async def fn(**kwargs):
        return {"ok": False, "error": "XSOAR 404"}

    wrapped = _wrap_with_instance(
        fn, [_inst("xsoar-v8")], secret_store=None,
        tool_name="close_incident", legacy_name=None, human_required=set(),
    )
    asyncio.run(wrapped())
    tc = [kw for a, kw in calls if a == audit_mod.ACTION_TOOL_CALL][0]
    assert tc["status"] == "failure"
    assert "XSOAR 404" in (tc["metadata"].get("error") or "")


# ── job scheduler ───────────────────────────────────────────────────

@pytest.fixture
def scheduler(tmp_path: Path) -> CroniterJobScheduler:
    async def _disp(name, args):
        return {"ok": False, "error": "tool said no"}
    return CroniterJobScheduler(definitions=[], dispatcher=_disp, data_root=tmp_path)


def test_job_tool_call_error_result_marks_run_failed(scheduler):
    scheduler.add_job(name="j", cron="0 * * * *",
                      action={"type": "tool_call", "name": "xsoar_close_incident", "args": {"id": "1"}})
    run = asyncio.run(scheduler.trigger_now("j"))
    assert run is not None
    assert run.status == "failure"
    assert "tool said no" in (run.error or "")


def test_job_tool_call_ok_result_marks_run_success(tmp_path):
    async def _disp(name, args):
        return {"ok": True, "data": 1}
    s = CroniterJobScheduler(definitions=[], dispatcher=_disp, data_root=tmp_path)
    s.add_job(name="ok", cron="0 * * * *",
              action={"type": "tool_call", "name": "xsoar_get_incident", "args": {}})
    run = asyncio.run(s.trigger_now("ok"))
    assert run.status == "success"
