"""InvestigationStore — sqlite-backed Issues + Cases + events.

Mirrors the InstanceStore test style. Each test gets a fresh store in a
tmp data_root so they don't share the on-disk db.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.investigation_store import (  # noqa: E402
    Case,
    Issue,
    IssueEvent,
    InvestigationStore,
)


@pytest.fixture()
def store(tmp_path):
    return InvestigationStore(data_root=tmp_path)


# ─── Issues ──────────────────────────────────────────────────────────


def test_create_and_get_issue_round_trips(store):
    issue = store.create_issue(
        title="Suspicious login from 8.8.8.8",
        kind="access_violation",
        severity="high",
        origin="agent",
        source_ref="1234",
        scope="Investigate the login + downstream activity.",
        summary="initial",
    )
    assert isinstance(issue, Issue)
    assert issue.id
    fetched = store.get_issue(issue.id)
    assert fetched == issue
    assert fetched.title == "Suspicious login from 8.8.8.8"
    assert fetched.kind == "access_violation"
    assert fetched.severity == "high"
    assert fetched.origin == "agent"
    assert fetched.source_ref == "1234"
    assert fetched.status == "open"
    assert fetched.case_id is None
    assert fetched.created_at and fetched.updated_at


def test_get_missing_issue_returns_none(store):
    assert store.get_issue("nope") is None


def test_create_issue_defaults(store):
    issue = store.create_issue(title="bare", kind="other")
    assert issue.severity == "medium"
    assert issue.origin == "agent"
    assert issue.status == "open"
    assert issue.source_ref is None


def test_list_issues_all_and_by_status(store):
    a = store.create_issue(title="a", kind="phishing")
    b = store.create_issue(title="b", kind="malware")
    store.update_issue(b.id, status="resolved")
    all_ids = {i.id for i in store.list_issues()}
    assert all_ids == {a.id, b.id}
    open_ids = {i.id for i in store.list_issues(status="open")}
    assert open_ids == {a.id}
    resolved_ids = {i.id for i in store.list_issues(status="resolved")}
    assert resolved_ids == {b.id}


def test_update_issue_partial(store):
    issue = store.create_issue(title="t", kind="phishing")
    updated = store.update_issue(
        issue.id,
        status="investigating",
        severity="critical",
        summary="found C2 beacon",
        recommendations="block the domain",
        conclusions="confirmed malicious",
        next_steps="notify SOC lead",
    )
    assert updated is not None
    assert updated.status == "investigating"
    assert updated.severity == "critical"
    assert updated.summary == "found C2 beacon"
    assert updated.recommendations == "block the domain"
    assert updated.conclusions == "confirmed malicious"
    assert updated.next_steps == "notify SOC lead"
    # untouched fields preserved
    assert updated.title == "t"
    assert updated.kind == "phishing"
    # updated_at advanced (or at least present)
    assert updated.updated_at >= issue.created_at


def test_update_missing_issue_returns_none(store):
    assert store.update_issue("nope", status="closed") is None


def test_delete_issue(store):
    issue = store.create_issue(title="t", kind="other")
    assert store.delete_issue(issue.id) is True
    assert store.get_issue(issue.id) is None
    assert store.delete_issue(issue.id) is False


# ─── Cases ───────────────────────────────────────────────────────────


def test_create_and_get_case(store):
    case = store.create_case(title="Credential-stuffing campaign", description="related logins")
    assert isinstance(case, Case)
    fetched = store.get_case(case.id)
    assert fetched == case
    assert fetched.title == "Credential-stuffing campaign"
    assert fetched.status == "open"


def test_list_cases_with_issue_counts(store):
    case = store.create_case(title="c1")
    i1 = store.create_issue(title="i1", kind="phishing")
    i2 = store.create_issue(title="i2", kind="phishing")
    store.add_issue_to_case(i1.id, case.id)
    store.add_issue_to_case(i2.id, case.id)
    cases = store.list_cases()
    assert len(cases) == 1
    # list_cases returns dicts with issue_count
    assert cases[0]["id"] == case.id
    assert cases[0]["issue_count"] == 2


# ─── Membership ──────────────────────────────────────────────────────


def test_add_issue_to_case_sets_case_id_and_filters(store):
    case = store.create_case(title="c")
    issue = store.create_issue(title="i", kind="malware")
    other = store.create_issue(title="o", kind="phishing")
    result = store.add_issue_to_case(issue.id, case.id)
    assert result is not None and result.case_id == case.id
    in_case = store.list_issues(case_id=case.id)
    assert [i.id for i in in_case] == [issue.id]
    assert other.id not in {i.id for i in in_case}


def test_add_issue_to_missing_case_or_issue(store):
    case = store.create_case(title="c")
    assert store.add_issue_to_case("nope", case.id) is None
    issue = store.create_issue(title="i", kind="other")
    assert store.add_issue_to_case(issue.id, "nope") is None


def test_remove_issue_from_case(store):
    case = store.create_case(title="c")
    issue = store.create_issue(title="i", kind="other")
    store.add_issue_to_case(issue.id, case.id)
    assert store.remove_issue_from_case(issue.id) is True
    assert store.get_issue(issue.id).case_id is None


# ─── Events (activity timeline) ──────────────────────────────────────


def test_add_and_list_events_in_order(store):
    issue = store.create_issue(title="i", kind="malware")
    e1 = store.add_event(issue.id, "action", "ran enrich_indicator on 8.8.8.8")
    e2 = store.add_event(issue.id, "finding", "DBotScore = bad")
    assert isinstance(e1, IssueEvent)
    events = store.list_events(issue.id)
    assert [e.id for e in events] == [e1.id, e2.id]  # insertion order
    assert events[0].type == "action"
    assert events[1].content == "DBotScore = bad"


def test_delete_issue_cascades_events(store):
    issue = store.create_issue(title="i", kind="other")
    store.add_event(issue.id, "note", "x")
    store.delete_issue(issue.id)
    assert store.list_events(issue.id) == []


def test_add_event_to_missing_issue_returns_none(store):
    assert store.add_event("nope", "note", "x") is None


def test_attack_chain_set_and_get(store):
    issue = store.create_issue(title="x", kind="lateral_movement")
    assert store.get_attack_chain(issue.id) is None
    assert store.set_attack_chain(issue.id, "<svg/>") is True
    assert store.get_attack_chain(issue.id) == "<svg/>"
    # The SVG rides only on the detail path, never the lean Issue DTO/list.
    assert not hasattr(store.list_issues()[0], "attack_chain_svg")


def test_attack_chain_missing_issue(store):
    assert store.set_attack_chain("nope", "<svg/>") is False
    assert store.get_attack_chain("nope") is None


def test_indicator_upsert_dedup_link_and_queries(store):
    i1 = store.create_issue(title="a", kind="phishing")
    i2 = store.create_issue(title="b", kind="phishing")
    ind = store.upsert_indicator("evil.com", "domain", issue_id=i1.id, dbot_score=3, source="guardian")
    assert ind.value == "evil.com" and ind.type == "domain" and ind.dbot_score == 3
    # re-seeing in another issue → SAME row, linked to both, source updated
    ind2 = store.upsert_indicator("evil.com", "domain", issue_id=i2.id, source="xsoar")
    assert ind2.id == ind.id
    listed = store.list_indicators()
    assert len(listed) == 1 and listed[0]["issue_count"] == 2 and listed[0]["source"] == "xsoar"
    # filters
    assert store.list_indicators(type="domain")[0]["id"] == ind.id
    assert store.list_indicators(type="ip") == []
    assert len(store.list_indicators(issue_id=i1.id)) == 1
    # detail carries related issues; per-issue list
    detail = store.get_indicator(ind.id)
    assert {x["id"] for x in detail["issues"]} == {i1.id, i2.id}
    assert [x.id for x in store.list_indicators_for_issue(i1.id)] == [ind.id]


def test_upsert_indicator_requires_value_and_type(store):
    with pytest.raises(ValueError):
        store.upsert_indicator("", "ip")


def test_get_missing_indicator_returns_none(store):
    assert store.get_indicator("nope") is None


# ─── Relationships (STIX edges) + relations canvas ───────────────────


def test_add_relationship_dedups_and_bumps_last_seen(store):
    i = store.create_issue(title="a", kind="phishing")
    ind = store.upsert_indicator("evil.com", "domain", issue_id=i.id)
    e1 = store.add_relationship(
        source_id=ind.id, source_type="indicator",
        target_value="185.234.219.12", target_type="indicator",
        relationship_type="resolves-to",
    )
    assert e1["source_id"] == ind.id
    assert e1["relationship_type"] == "resolves-to"
    assert e1["target_value"] == "185.234.219.12"
    assert e1["source"] == "guardian"
    first_seen = e1["first_seen"]
    # re-asserting the SAME edge dedups (same id) + keeps existing description
    e2 = store.add_relationship(
        source_id=ind.id, source_type="indicator",
        target_value="185.234.219.12", target_type="indicator",
        relationship_type="resolves-to", description="A-record",
    )
    assert e2["id"] == e1["id"]
    assert e2["first_seen"] == first_seen  # unchanged
    assert e2["description"] == "A-record"
    rels = store.list_relationships(ind.id)
    assert len(rels) == 1


def test_add_relationship_requires_core_fields(store):
    i = store.create_issue(title="a", kind="phishing")
    ind = store.upsert_indicator("evil.com", "domain", issue_id=i.id)
    with pytest.raises(ValueError):
        store.add_relationship(
            source_id=ind.id, source_type="indicator",
            target_value="", target_type="indicator", relationship_type="resolves-to",
        )


def test_list_relationships_scopes_by_source(store):
    i = store.create_issue(title="a", kind="phishing")
    a = store.upsert_indicator("evil.com", "domain", issue_id=i.id)
    b = store.upsert_indicator("8.8.8.8", "ip", issue_id=i.id)
    store.add_relationship(source_id=a.id, source_type="indicator",
                           target_value="T1566.002", target_type="attack-pattern",
                           relationship_type="uses")
    store.add_relationship(source_id=b.id, source_type="indicator",
                           target_value="APT-X", target_type="threat-actor",
                           relationship_type="attributed-to")
    assert len(store.list_relationships()) == 2  # all
    assert {r["source_id"] for r in store.list_relationships(a.id)} == {a.id}


def test_relations_canvas_set_and_get(store):
    issue = store.create_issue(title="x", kind="phishing")
    assert store.get_relations_canvas(issue.id) is None
    assert store.set_relations_canvas(issue.id, "<svg/>") is True
    assert store.get_relations_canvas(issue.id) == "<svg/>"
    # rides only on the detail path, never the lean Issue DTO/list
    assert not hasattr(store.list_issues()[0], "relations_canvas_svg")


def test_relations_canvas_missing_issue(store):
    assert store.set_relations_canvas("nope", "<svg/>") is False
    assert store.get_relations_canvas("nope") is None


# ─── Case-level diagram SVGs (v0.2.2) ────────────────────────────────


def test_case_attack_chain_set_and_get(store):
    case = store.create_case(title="campaign")
    assert store.get_case_attack_chain(case.id) is None
    assert store.set_case_attack_chain(case.id, "<svg>chain</svg>") is True
    assert store.get_case_attack_chain(case.id) == "<svg>chain</svg>"
    # rides only on the detail path, never the lean Case DTO/list
    assert not hasattr(store.get_case(case.id), "attack_chain_svg")
    assert "attack_chain_svg" not in store.list_cases()[0]


def test_case_relations_canvas_set_and_get(store):
    case = store.create_case(title="campaign")
    assert store.get_case_relations_canvas(case.id) is None
    assert store.set_case_relations_canvas(case.id, "<svg>rel</svg>") is True
    assert store.get_case_relations_canvas(case.id) == "<svg>rel</svg>"
    # the two case SVGs are independent
    assert store.get_case_attack_chain(case.id) is None


def test_case_diagrams_missing_case(store):
    assert store.set_case_attack_chain("nope", "<svg/>") is False
    assert store.get_case_attack_chain("nope") is None
    assert store.set_case_relations_canvas("nope", "<svg/>") is False
    assert store.get_case_relations_canvas("nope") is None
