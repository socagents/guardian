"""Stage B — push_verdict_to_xsoar built-in tool.

Writes a resolved Issue's structured verdict back to the upstream XSOAR
incident war room via the tool dispatcher (xsoar_add_entry + xsoar_save_evidence).
Tests mock the dispatcher so no connector is needed; they assert the write path,
the guards (source_ref + verdict), and graceful degradation.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.investigation_store import InvestigationStore  # noqa: E402
from usecase.builtin_components import investigation_tools as it  # noqa: E402


class FakeDispatcher:
    """Records (name, kwargs) calls; returns connector-shaped dicts."""

    def __init__(self):
        self.calls = []

    async def __call__(self, name, kwargs):
        self.calls.append((name, kwargs))
        if name == "xsoar_add_entry":
            return {"ok": True, "entry_id": "ENTRY-1", "incident_id": kwargs["incident_id"]}
        if name == "xsoar_save_evidence":
            return {"ok": True, "saved": True, "entry_id": kwargs["entry_id"], "via": "evidence-api"}
        raise KeyError(name)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = InvestigationStore(data_root=tmp_path)
    monkeypatch.setattr(it, "investigation_store", lambda: s)
    return s


def _resolved_issue(store):
    iss = store.create_issue(title="Phish", kind="phishing", severity="high",
                             source_ref="INC-42")
    it.issue_update(iss.id, conclusions="creds harvested", recommendations="reset jdoe")
    it.issue_set_verdict(iss.id, "TRUE_POSITIVE", confidence=0.9,
                         blast_radius={"hosts": ["WS-1"], "accounts": ["jdoe"]})
    it.issue_add_technique(iss.id, "T1566.001", tactic="initial-access")
    return iss


def test_push_happy_path(store, monkeypatch):
    fake = FakeDispatcher()
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: fake)
    iss = _resolved_issue(store)

    out = asyncio.run(it.push_verdict_to_xsoar(iss.id))

    assert out.get("ok") is True
    assert out["incident_id"] == "INC-42"
    assert out["entry_id"] == "ENTRY-1"
    # add_entry called with the incident + verdict-bearing content
    add = next(c for c in fake.calls if c[0] == "xsoar_add_entry")
    assert add[1]["incident_id"] == "INC-42"
    assert "TRUE_POSITIVE" in add[1]["content"]
    assert "T1566.001" in add[1]["content"]
    # save_evidence called with the returned entry id
    ev = next(c for c in fake.calls if c[0] == "xsoar_save_evidence")
    assert ev[1]["entry_id"] == "ENTRY-1"
    # a pushback event was recorded on the issue timeline
    evs = store.list_events(iss.id)
    assert any(e.type == "pushback" for e in evs)


def test_push_passes_instance_through(store, monkeypatch):
    fake = FakeDispatcher()
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: fake)
    iss = _resolved_issue(store)

    asyncio.run(it.push_verdict_to_xsoar(iss.id, instance="primary-xsoar"))

    add = next(c for c in fake.calls if c[0] == "xsoar_add_entry")
    assert add[1]["instance"] == "primary-xsoar"


def test_push_requires_source_ref(store, monkeypatch):
    fake = FakeDispatcher()
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: fake)
    iss = store.create_issue(title="standalone", kind="other")  # no source_ref
    it.issue_set_verdict(iss.id, "TRUE_POSITIVE")

    out = asyncio.run(it.push_verdict_to_xsoar(iss.id))
    assert "error" in out
    assert fake.calls == []  # never touched the connector


def test_push_requires_verdict(store, monkeypatch):
    fake = FakeDispatcher()
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: fake)
    iss = store.create_issue(title="open", kind="phishing", source_ref="INC-9")

    out = asyncio.run(it.push_verdict_to_xsoar(iss.id))
    assert "error" in out
    assert fake.calls == []


def test_push_dispatcher_unavailable(store, monkeypatch):
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: None)
    iss = _resolved_issue(store)
    out = asyncio.run(it.push_verdict_to_xsoar(iss.id))
    assert "error" in out


def test_push_connector_error_surfaces(store, monkeypatch):
    class Boom:
        async def __call__(self, name, kwargs):
            raise KeyError("xsoar_add_entry")  # connector / instance not configured
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: Boom())
    iss = _resolved_issue(store)
    out = asyncio.run(it.push_verdict_to_xsoar(iss.id))
    assert "error" in out
    assert "INC-42" in out["error"]
