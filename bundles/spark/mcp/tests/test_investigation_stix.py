"""Stage D — STIX 2.1 bundle export."""
from __future__ import annotations

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


def _resolved_issue(store):
    iss = store.create_issue(title="Phish", kind="phishing", severity="high",
                             source_ref="INC-77")
    it.issue_set_verdict(iss.id, "TRUE_POSITIVE", confidence=0.9)
    it.issue_add_technique(iss.id, "T1566.001", tactic="initial-access")
    it.issue_add_technique(iss.id, "T1071.004", tactic="command-and-control")
    d = store.upsert_indicator("evil.com", "domain", issue_id=iss.id, dbot_score=3)
    store.upsert_indicator("185.234.219.12", "ip", issue_id=iss.id, dbot_score=3)
    store.add_relationship(d.id, "indicator", "185.234.219.12", "ip", "resolves-to")
    return iss


def _types(bundle):
    return [o["type"] for o in bundle["objects"]]


def test_issue_stix_bundle_shape(store):
    iss = _resolved_issue(store)
    out = it.export_issue_stix(iss.id)
    assert "error" not in out
    b = out["bundle"]
    assert b["type"] == "bundle"
    assert b["id"].startswith("bundle--")
    types = _types(b)
    for required in ("identity", "incident", "attack-pattern", "indicator", "relationship"):
        assert required in types, f"missing {required}: {types}"
    # every SDO has a STIX-shaped id + spec_version
    for o in b["objects"]:
        assert o["id"].startswith(o["type"] + "--")
        assert o.get("spec_version") == "2.1" or o["type"] == "bundle"


def test_issue_stix_attack_pattern_has_mitre_ref(store):
    iss = _resolved_issue(store)
    b = it.export_issue_stix(iss.id)["bundle"]
    aps = [o for o in b["objects"] if o["type"] == "attack-pattern"]
    assert len(aps) == 2
    ext = aps[0]["external_references"][0]
    assert ext["source_name"] == "mitre-attack"
    assert ext["external_id"].startswith("T")


def test_issue_stix_indicator_pattern(store):
    iss = _resolved_issue(store)
    b = it.export_issue_stix(iss.id)["bundle"]
    inds = [o for o in b["objects"] if o["type"] == "indicator"]
    patterns = " ".join(i["pattern"] for i in inds)
    assert "domain-name:value = 'evil.com'" in patterns
    assert "ipv4-addr:value = '185.234.219.12'" in patterns


def test_issue_stix_is_deterministic(store):
    iss = _resolved_issue(store)
    a = it.export_issue_stix(iss.id)["bundle"]
    b = it.export_issue_stix(iss.id)["bundle"]
    assert a == b  # stable ids → byte-identical re-export


def test_issue_stix_missing(store):
    assert "error" in it.export_issue_stix("nope")


def test_case_stix_bundle(store):
    case = store.create_case(title="Campaign")
    i1 = _resolved_issue(store)
    i2 = store.create_issue(title="host2", kind="phishing", severity="medium")
    it.issue_add_technique(i2.id, "T1486")
    store.add_issue_to_case(i1.id, case.id)
    store.add_issue_to_case(i2.id, case.id)
    store.update_case(case.id, threat_actor="TA505")
    out = it.export_case_stix(case.id)
    assert "error" not in out
    b = out["bundle"]
    types = _types(b)
    assert "grouping" in types or "campaign" in types
    assert "threat-actor" in types  # rollup threat_actor → SDO
    assert "attack-pattern" in types
