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


def test_indicator_tools_flow(wired):
    import json as _json
    from usecase.builtin_components import indicator_tools as ind
    iid = it.issue_create(title="x", kind="malware")["issue"]["id"]
    r = ind.indicator_upsert(value="1.2.3.4", type="ip", issue_id=iid, dbot_score=3,
                             enrichment={"country": "AT"}, source="guardian")
    assert "indicator" in r and r["indicator"]["value"] == "1.2.3.4"
    assert _json.loads(r["indicator"]["enrichment"]) == {"country": "AT"}
    assert ind.indicators_list()["count"] == 1
    assert ind.indicators_list(type="domain")["count"] == 0
    det = ind.indicator_get(r["indicator"]["id"])
    assert det["indicator"]["issues"][0]["id"] == iid


def test_indicator_upsert_rejects_empty(wired):
    from usecase.builtin_components import indicator_tools as ind
    assert "error" in ind.indicator_upsert(value="", type="ip")


def test_indicator_get_missing(wired):
    from usecase.builtin_components import indicator_tools as ind
    assert "error" in ind.indicator_get("nope")


def test_indicator_relate_flow_and_appears_on_detail(wired):
    from usecase.builtin_components import indicator_tools as ind
    iid = it.issue_create(title="x", kind="phishing")["issue"]["id"]
    src = ind.indicator_upsert(value="evil.com", type="domain", issue_id=iid)["indicator"]["id"]
    r = ind.indicator_relate(
        indicator_id=src, relationship_type="attributed-to",
        target="APT-X", target_type="threat-actor", description="campaign overlap",
    )
    assert "relationship" in r
    assert r["relationship"]["relationship_type"] == "attributed-to"
    assert r["relationship"]["target_value"] == "APT-X"
    # the edge rides on the indicator detail
    det = ind.indicator_get(src)
    assert det["indicator"]["relationships"][0]["target_value"] == "APT-X"


def test_indicator_relate_missing_indicator(wired):
    from usecase.builtin_components import indicator_tools as ind
    assert "error" in ind.indicator_relate(
        indicator_id="nope", relationship_type="uses",
        target="T1071", target_type="attack-pattern",
    )


def test_issue_set_relation_graph_round_trip(wired):
    iid = it.issue_create(title="x", kind="phishing")["issue"]["id"]
    svg = '<svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    res = it.issue_set_relation_graph(iid, svg)
    assert res.get("ok") is True and res["bytes"] > 0
    assert wired.get_relations_canvas(iid) == svg


def test_issue_set_relation_graph_strips_active_content_and_validates(wired):
    iid = it.issue_create(title="x")["issue"]["id"]
    assert "error" in it.issue_set_relation_graph(iid, "not an svg")
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><rect onload="x()"/></svg>'
    assert it.issue_set_relation_graph(iid, svg).get("ok") is True
    stored = wired.get_relations_canvas(iid).lower()
    assert "<script" not in stored and "onload" not in stored


def test_issue_set_relation_graph_missing_issue(wired):
    assert "error" in it.issue_set_relation_graph("nope", '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')


def test_case_set_attack_chain_round_trip(wired):
    cid = it.case_create(title="campaign")["case"]["id"]
    svg = '<svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>'
    res = it.case_set_attack_chain(cid, svg)
    assert res.get("ok") is True and res["case_id"] == cid and res["bytes"] > 0
    assert wired.get_case_attack_chain(cid) == svg


def test_case_set_relation_graph_round_trip_and_strips(wired):
    cid = it.case_create(title="campaign")["case"]["id"]
    assert "error" in it.case_set_relation_graph(cid, "not an svg")
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><script>x()</script><rect onload="y()"/></svg>'
    assert it.case_set_relation_graph(cid, svg).get("ok") is True
    stored = wired.get_case_relations_canvas(cid).lower()
    assert "<script" not in stored and "onload" not in stored


def test_case_set_diagram_missing_case(wired):
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    assert "error" in it.case_set_attack_chain("nope", svg)
    assert "error" in it.case_set_relation_graph("nope", svg)
