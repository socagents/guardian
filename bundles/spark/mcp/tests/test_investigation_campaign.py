"""Stage C — campaign / cross-incident analytics store layer.

Covers the cases rollup columns, the playbook_matches + case_relationships
tables, their CRUD/upsert/inverse-lookup methods, and backward-safe migration.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.investigation_store import InvestigationStore  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    return InvestigationStore(data_root=tmp_path)


def test_case_rollup_columns_persist(store):
    case = store.create_case(title="Campaign X")
    updated = store.update_case(
        case.id,
        campaign_summary="multi-host phishing campaign",
        threat_actor="TA505",
        infrastructure=json.dumps({"ips": ["1.2.3.4"]}),
        techniques=json.dumps(["T1566.001", "T1071.004"]),
        severity_rollup="high",
    )
    assert updated.threat_actor == "TA505"
    got = store.get_case(case.id)
    assert got.campaign_summary == "multi-host phishing campaign"
    assert json.loads(got.techniques) == ["T1566.001", "T1071.004"]
    assert got.severity_rollup == "high"


def test_playbook_match_crud_and_inverse(store):
    a = store.create_issue(title="phish a", kind="phishing")
    b = store.create_issue(title="phish b", kind="phishing")
    store.add_playbook_match(a.id, "soar-playbooks/phishing-triage", score=0.9,
                             matched_criteria="email + malicious url")
    store.add_playbook_match(b.id, "soar-playbooks/phishing-triage", score=0.7)
    ms = store.list_playbook_matches(a.id)
    assert len(ms) == 1 and ms[0].playbook_doc_id == "soar-playbooks/phishing-triage"
    assert ms[0].score == 0.9
    issues = store.list_issues_by_playbook("soar-playbooks/phishing-triage")
    assert {i.id for i in issues} == {a.id, b.id}


def test_playbook_match_upsert_dedup(store):
    a = store.create_issue(title="x")
    store.add_playbook_match(a.id, "pb1", score=0.5)
    store.add_playbook_match(a.id, "pb1", score=0.95, matched_criteria="tighter")
    ms = store.list_playbook_matches(a.id)
    assert len(ms) == 1
    assert ms[0].score == 0.95
    assert ms[0].matched_criteria == "tighter"


def test_case_relationship_crud_bidirectional(store):
    c1 = store.create_case(title="campaign 1")
    c2 = store.create_case(title="campaign 2")
    store.add_case_relationship(c1.id, c2.id, "same-campaign", note="shared C2")
    # visible from both endpoints
    from_c1 = store.list_case_relationships(c1.id)
    from_c2 = store.list_case_relationships(c2.id)
    assert len(from_c1) == 1 and len(from_c2) == 1
    assert from_c1[0].relationship_type == "same-campaign"
    assert from_c1[0].target_case_id == c2.id


def test_case_relationship_upsert_dedup(store):
    c1 = store.create_case(title="a")
    c2 = store.create_case(title="b")
    store.add_case_relationship(c1.id, c2.id, "sibling")
    store.add_case_relationship(c1.id, c2.id, "sibling", note="now with note")
    rels = store.list_case_relationships(c1.id)
    assert len(rels) == 1
    assert rels[0].note == "now with note"


def test_pre_migration_db_gets_case_columns(tmp_path):
    # Simulate a pre-Stage-C cases table (no rollup columns).
    db = tmp_path / "investigations.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE cases (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT, "
        "status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
    )
    con.execute("INSERT INTO cases VALUES ('c1','old case',NULL,'open','t','t')")
    con.commit()
    con.close()

    store = InvestigationStore(data_root=tmp_path)  # runs migration
    got = store.get_case("c1")
    assert got is not None
    assert got.campaign_summary is None  # column exists, value null
    assert got.severity_rollup is None
    # and the new tables exist
    store.add_playbook_match(store.create_issue(title="z").id, "pb", score=1.0)
    store.add_case_relationship("c1", store.create_case(title="c2").id, "sibling")
