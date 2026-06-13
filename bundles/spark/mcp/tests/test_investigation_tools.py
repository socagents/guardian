"""Investigation MCP tools — agent-facing issue/case tools over the store."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.builtin_components import investigation_tools as it  # noqa: E402
from usecase.investigation_store import (  # noqa: E402
    InvestigationStore,
    set_investigation_store,
)


@pytest.fixture()
def wired(tmp_path):
    store = InvestigationStore(data_root=tmp_path)
    set_investigation_store(store)
    yield store
    set_investigation_store(None)


def test_issue_create_get_update_event_flow(wired):
    created = it.issue_create(title="Phish", kind="phishing", severity="high", source_ref="42")
    assert "issue" in created
    iid = created["issue"]["id"]
    assert created["issue"]["origin"] == "agent"
    assert created["issue"]["source_ref"] == "42"

    it.issue_add_event(iid, "action", "ran enrich_indicator on evil.com")
    it.issue_update(iid, status="resolved", conclusions="confirmed phishing")

    got = it.issue_get(iid)
    assert got["issue"]["status"] == "resolved"
    assert got["issue"]["conclusions"] == "confirmed phishing"
    assert len(got["events"]) == 1
    assert got["events"][0]["type"] == "action"
    assert got["case"] is None


def test_issues_list_filters(wired):
    a = it.issue_create(title="a", kind="malware")["issue"]["id"]
    it.issue_create(title="b", kind="phishing")
    it.issue_update(a, status="closed")
    assert it.issues_list()["count"] == 2
    assert it.issues_list(status="closed")["count"] == 1


def test_case_create_group_and_get(wired):
    case = it.case_create(title="Campaign X", description="related")["case"]
    i1 = it.issue_create(title="i1", kind="phishing")["issue"]["id"]
    i2 = it.issue_create(title="i2", kind="phishing")["issue"]["id"]
    it.case_add_issue(case["id"], i1)
    it.case_add_issue(case["id"], i2)

    cg = it.case_get(case["id"])
    assert len(cg["issues"]) == 2
    cl = it.cases_list()
    assert cl["cases"][0]["issue_count"] == 2
    # the issue now reports its case
    assert it.issue_get(i1)["case"]["id"] == case["id"]


def test_tool_error_envelopes(wired):
    assert "error" in it.issue_get("nope")
    assert "error" in it.issue_update("nope", status="closed")
    assert "error" in it.issue_add_event("nope", "note", "x")
    assert "error" in it.case_get("nope")
    assert "error" in it.case_add_issue("nope-case", "nope-issue")
    assert "error" in it.issue_create(title="")


def test_tools_handle_unwired_store():
    set_investigation_store(None)
    assert "error" in it.issues_list()
    assert "not initialized" in it.issues_list()["error"]


def test_issue_set_attack_chain_round_trip(wired):
    iid = it.issue_create(title="LM", kind="lateral_movement")["issue"]["id"]
    svg = '<svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    res = it.issue_set_attack_chain(iid, svg)
    assert res.get("ok") is True and res["bytes"] > 0
    assert wired.get_attack_chain(iid) == svg


def test_issue_set_attack_chain_rejects_non_svg(wired):
    iid = it.issue_create(title="x")["issue"]["id"]
    assert "error" in it.issue_set_attack_chain(iid, "not an svg")
    assert wired.get_attack_chain(iid) is None


def test_issue_set_attack_chain_strips_active_content(wired):
    iid = it.issue_create(title="x")["issue"]["id"]
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><rect onload="x()"/></svg>'
    assert it.issue_set_attack_chain(iid, svg).get("ok") is True
    stored = wired.get_attack_chain(iid).lower()
    assert "<script" not in stored and "onload" not in stored


def test_issue_set_attack_chain_missing_issue(wired):
    assert "error" in it.issue_set_attack_chain("nope", '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')
