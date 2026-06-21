"""Stage D — report templates."""
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


def _rich_issue(store):
    iss = store.create_issue(title="Phish", kind="phishing", severity="high", source_ref="INC-1")
    it.issue_update(iss.id, summary="user phished", conclusions="creds harvested",
                    recommendations="reset jdoe")
    it.issue_set_verdict(iss.id, "TRUE_POSITIVE", confidence=0.9,
                         blast_radius={"hosts": ["WS-1"], "accounts": ["jdoe"]})
    it.issue_add_technique(iss.id, "T1566.001", tactic="initial-access")
    store.upsert_indicator("evil.com", "domain", issue_id=iss.id, dbot_score=3)
    it.issue_add_event(iss.id, type="finding", content="clicked link")
    return iss


def test_report_default_is_technical(store):
    iss = _rich_issue(store)
    out = it.generate_investigation_report(iss.id)
    assert "error" not in out
    md = out["markdown"]
    assert "TRUE_POSITIVE" in md and "T1566.001" in md
    assert "## Timeline" in md  # technical = full report w/ timeline
    assert store.get_issue(iss.id).report == md  # persisted


def test_report_executive_omits_timeline(store):
    iss = _rich_issue(store)
    md = it.generate_investigation_report(iss.id, template="executive")["markdown"]
    assert "TRUE_POSITIVE" in md
    assert "reset jdoe" in md  # recommendations present
    assert "## Timeline" not in md
    assert "Executive" in md


def test_report_ioc_list(store):
    iss = _rich_issue(store)
    md = it.generate_investigation_report(iss.id, template="ioc-list")["markdown"]
    assert "evil.com" in md
    assert "T1566.001" in md
    assert "## Conclusions" not in md  # terse


def test_report_bad_template(store):
    iss = _rich_issue(store)
    out = it.generate_investigation_report(iss.id, template="bogus")
    assert "error" in out


def test_generate_campaign_report(store):
    case = store.create_case(title="Campaign X")
    i1 = _rich_issue(store)
    i2 = store.create_issue(title="host2", kind="phishing", severity="medium")
    it.issue_add_technique(i2.id, "T1071.004")
    store.add_issue_to_case(i1.id, case.id)
    store.add_issue_to_case(i2.id, case.id)
    it.case_rollup(case.id, threat_actor="TA505")

    out = it.generate_campaign_report(case.id)
    assert "error" not in out
    md = out["markdown"]
    assert "Campaign X" in md
    assert "TA505" in md
    assert "T1566.001" in md and "T1071.004" in md  # technique union
    assert "host2" in md  # member issue


def test_campaign_report_missing(store):
    assert "error" in it.generate_campaign_report("nope")
