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
