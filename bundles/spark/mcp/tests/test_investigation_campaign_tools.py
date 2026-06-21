"""Stage C — campaign analytics MCP tools."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.investigation_store import InvestigationStore  # noqa: E402
from usecase.builtin_components import investigation_tools as it  # noqa: E402


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = InvestigationStore(data_root=tmp_path)
    monkeypatch.setattr(it, "investigation_store", lambda: s)
    return s


# ── case_rollup ──────────────────────────────────────────────────

def test_case_rollup_synthesizes(store):
    case = store.create_case(title="Phish campaign")
    i1 = store.create_issue(title="host1", kind="phishing", severity="high")
    i2 = store.create_issue(title="host2", kind="phishing", severity="medium")
    store.add_issue_to_case(i1.id, case.id)
    store.add_issue_to_case(i2.id, case.id)
    store.add_technique_mapping(i1.id, "T1566.001")
    store.add_technique_mapping(i2.id, "T1071.004")
    # shared IOC "evil.com" on both; unique ones on each
    store.upsert_indicator("evil.com", "domain", issue_id=i1.id)
    store.upsert_indicator("evil.com", "domain", issue_id=i2.id)
    store.upsert_indicator("1.1.1.1", "ip", issue_id=i1.id)
    it.issue_set_verdict(i1.id, "TRUE_POSITIVE")
    it.issue_set_verdict(i2.id, "TRUE_POSITIVE")

    out = it.case_rollup(case.id)
    assert "error" not in out
    assert set(out["rollup"]["techniques"]) == {"T1566.001", "T1071.004"}
    assert out["rollup"]["severity_rollup"] == "high"
    assert "evil.com" in out["rollup"]["infrastructure"]["shared_indicators"]
    assert "1.1.1.1" not in out["rollup"]["infrastructure"]["shared_indicators"]  # only on one
    # persisted on the case
    c = store.get_case(case.id)
    assert json.loads(c.techniques) == sorted(["T1566.001", "T1071.004"])
    assert c.severity_rollup == "high"


def test_case_rollup_accepts_overrides(store):
    case = store.create_case(title="c")
    store.add_issue_to_case(store.create_issue(title="i").id, case.id)
    out = it.case_rollup(case.id, threat_actor="TA505", campaign_summary="hand-written")
    assert out["rollup"]["threat_actor"] == "TA505"
    assert store.get_case(case.id).threat_actor == "TA505"
    assert store.get_case(case.id).campaign_summary == "hand-written"


def test_case_rollup_missing_case(store):
    out = it.case_rollup("nope")
    assert "error" in out


# ── issue_match_playbook ─────────────────────────────────────────

def test_issue_match_playbook(store):
    iss = store.create_issue(title="phish")
    out = it.issue_match_playbook(iss.id, "soar-playbooks/phishing", score=0.9,
                                  matched_criteria="email+url")
    assert out["match"]["playbook_doc_id"] == "soar-playbooks/phishing"
    assert store.list_playbook_matches(iss.id)[0].score == 0.9


# ── case_relate / case_related ───────────────────────────────────

def test_case_relate_and_related(store):
    c1 = store.create_case(title="camp 1")
    c2 = store.create_case(title="camp 2")
    out = it.case_relate(c1.id, c2.id, "same-campaign", note="shared C2")
    assert "error" not in out
    rel = it.case_related(c1.id)
    assert rel["count"] == 1
    assert rel["related"][0]["relationship_type"] == "same-campaign"
    assert rel["related"][0]["other_case"]["title"] == "camp 2"


def test_case_relate_rejects_bad_type(store):
    c1 = store.create_case(title="a")
    c2 = store.create_case(title="b")
    out = it.case_relate(c1.id, c2.id, "frobnicate")
    assert "error" in out


def test_case_relate_missing_case(store):
    c1 = store.create_case(title="a")
    out = it.case_relate(c1.id, "ghost", "sibling")
    assert "error" in out


# ── infer_relationships ──────────────────────────────────────────

def test_infer_relationships_transitive(store):
    d = store.upsert_indicator("evil.com", "domain")
    i = store.upsert_indicator("1.2.3.4", "ip")
    store.add_relationship(d.id, "indicator", "1.2.3.4", "ip", "resolves-to")
    store.add_relationship(i.id, "indicator", "c2.bad.com", "domain", "communicates-with")

    out = it.infer_relationships(indicator_id=d.id)
    assert "error" not in out
    targets = [s["target_value"] for s in out["suggestions"] if s["kind"] == "transitive-edge"]
    assert "c2.bad.com" in targets


def test_infer_relationships_technique_siblings(store):
    a = store.create_issue(title="a")
    b = store.create_issue(title="b")
    store.add_technique_mapping(a.id, "T1071.004")
    store.add_technique_mapping(b.id, "T1071.004")
    out = it.infer_relationships(issue_id=a.id)
    sib = [s for s in out["suggestions"] if s["kind"] == "technique-sibling"]
    assert any(s["issue_id"] == b.id for s in sib)


def test_infer_relationships_requires_an_arg(store):
    out = it.infer_relationships()
    assert "error" in out
