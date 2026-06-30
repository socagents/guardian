"""R5 — sync_investigation_to_xsoar built-in (closed-loop write-back + containment).

The closed-loop superset of push_verdict_to_xsoar: writes the verdict war-room
entry + evidence, escalates the incident severity to match the verdict, pushes
the investigation's IOCs to XSOAR Threat-Intel, and (when asked) runs an
approval-gated containment playbook. Tests mock the tool dispatcher.
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
    """Records (name, kwargs); returns connector-shaped {ok:True,...} dicts."""

    def __init__(self):
        self.calls = []

    async def __call__(self, name, kwargs):
        self.calls.append((name, kwargs))
        if name == "xsoar_add_entry":
            return {"ok": True, "entry_id": "ENTRY-1", "incident_id": kwargs["incident_id"]}
        if name == "xsoar_save_evidence":
            return {"ok": True, "saved": True}
        if name == "xsoar_update_incident":
            return {"ok": True, "incident_id": kwargs["incident_id"], "updated": True}
        if name == "xsoar_create_indicator":
            return {"ok": True, "id": "ind-1", "created": {"value": kwargs.get("value")}}
        if name == "xsoar_run_playbook":
            return {"ok": True, "incident_id": kwargs["incident_id"], "playbook_id": kwargs.get("playbook_id")}
        raise KeyError(name)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = InvestigationStore(data_root=tmp_path)
    monkeypatch.setattr(it, "investigation_store", lambda: s)
    return s


def _resolved_issue(store, verdict="TRUE_POSITIVE"):
    iss = store.create_issue(title="Phish", kind="phishing", severity="high", source_ref="INC-42")
    it.issue_update(iss.id, conclusions="creds harvested", recommendations="reset jdoe")
    it.issue_set_verdict(iss.id, verdict, confidence=0.9,
                         blast_radius={"hosts": ["WS-1"], "accounts": ["jdoe"]})
    it.issue_add_technique(iss.id, "T1566.001", tactic="initial-access")
    return iss


def test_verdict_to_severity_score_handles_underscores():
    assert it._verdict_to_severity_score("TRUE_POSITIVE") == (4, 3)
    assert it._verdict_to_severity_score("Malicious") == (4, 3)
    assert it._verdict_to_severity_score("Suspicious") == (3, 2)
    assert it._verdict_to_severity_score("FALSE_POSITIVE") == (1, 1)
    assert it._verdict_to_severity_score("inconclusive") == (None, None)


def test_sync_happy_path_writes_verdict_and_escalates(store, monkeypatch):
    fake = FakeDispatcher()
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: fake)
    iss = _resolved_issue(store)

    out = asyncio.run(it.sync_investigation_to_xsoar(iss.id))

    assert out["ok"] is True
    assert out["incident_id"] == "INC-42" and out["entry_id"] == "ENTRY-1"
    names = [c[0] for c in fake.calls]
    assert "xsoar_add_entry" in names and "xsoar_save_evidence" in names
    # verdict (TRUE_POSITIVE) → severity 4 escalation
    up = next(c for c in fake.calls if c[0] == "xsoar_update_incident")
    assert up[1]["incident_id"] == "INC-42" and up[1]["severity"] == 4
    # no containment requested → run_playbook NOT called
    assert "xsoar_run_playbook" not in names
    # timeline event recorded
    assert any(e.type == "sync_to_xsoar" for e in store.list_events(iss.id))


def test_sync_containment_dispatches_run_playbook(store, monkeypatch):
    fake = FakeDispatcher()
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: fake)
    iss = _resolved_issue(store)

    out = asyncio.run(it.sync_investigation_to_xsoar(
        iss.id, containment_playbook="Isolate Endpoint - Generic"))

    assert out["ok"] is True and out["steps"]["containment"] is True
    rp = next(c for c in fake.calls if c[0] == "xsoar_run_playbook")
    assert rp[1]["incident_id"] == "INC-42"
    assert rp[1]["playbook_id"] == "Isolate Endpoint - Generic"


def test_sync_passes_instance_through_all_calls(store, monkeypatch):
    fake = FakeDispatcher()
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: fake)
    iss = _resolved_issue(store)
    asyncio.run(it.sync_investigation_to_xsoar(iss.id, instance="primary-xsoar",
                                               containment_playbook="PB"))
    for name, kwargs in fake.calls:
        assert kwargs.get("instance") == "primary-xsoar", f"{name} missing instance"


def test_sync_no_escalation_when_disabled(store, monkeypatch):
    fake = FakeDispatcher()
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: fake)
    iss = _resolved_issue(store)
    asyncio.run(it.sync_investigation_to_xsoar(iss.id, escalate_severity=False))
    assert "xsoar_update_incident" not in [c[0] for c in fake.calls]


def test_sync_requires_source_ref(store, monkeypatch):
    fake = FakeDispatcher()
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: fake)
    iss = store.create_issue(title="standalone", kind="other")
    it.issue_set_verdict(iss.id, "TRUE_POSITIVE")
    out = asyncio.run(it.sync_investigation_to_xsoar(iss.id))
    assert "error" in out and fake.calls == []


def test_sync_requires_verdict(store, monkeypatch):
    fake = FakeDispatcher()
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: fake)
    iss = store.create_issue(title="open", kind="phishing", source_ref="INC-9")
    out = asyncio.run(it.sync_investigation_to_xsoar(iss.id))
    assert "error" in out and fake.calls == []


def test_sync_dispatcher_unavailable(store, monkeypatch):
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: None)
    iss = _resolved_issue(store)
    out = asyncio.run(it.sync_investigation_to_xsoar(iss.id))
    assert "error" in out


def test_sync_partial_when_containment_fails(store, monkeypatch):
    class ContainFails(FakeDispatcher):
        async def __call__(self, name, kwargs):
            if name == "xsoar_run_playbook":
                self.calls.append((name, kwargs))
                return {"ok": False, "error": "playbook not found"}
            return await super().__call__(name, kwargs)
    fake = ContainFails()
    monkeypatch.setattr(it, "get_tool_dispatcher", lambda: fake)
    iss = _resolved_issue(store)
    out = asyncio.run(it.sync_investigation_to_xsoar(iss.id, containment_playbook="nope"))
    assert out["ok"] is False and out["partial"] is True
    assert out["steps"]["add_entry"] is True and out["steps"]["containment"] is False
