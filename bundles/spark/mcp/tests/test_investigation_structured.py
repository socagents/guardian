"""Stage A — structured investigation record: verdict/confidence/blast_radius/
report columns + technique_mappings table + backward-safe migration."""
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


def test_structured_verdict_fields_roundtrip(store):
    iss = store.create_issue(title="t", kind="phishing")
    store.update_issue(
        iss.id,
        verdict="TRUE_POSITIVE",
        verdict_confidence=0.9,
        blast_radius=json.dumps({"hosts": ["h1"], "accounts": []}),
        report="# Report\nbody",
    )
    got = store.get_issue(iss.id)
    assert got.verdict == "TRUE_POSITIVE"
    assert got.verdict_confidence == 0.9
    assert json.loads(got.blast_radius)["hosts"] == ["h1"]
    assert got.report.startswith("# Report")


def test_technique_mapping_crud_and_inverse(store):
    a = store.create_issue(title="a")
    b = store.create_issue(title="b")
    store.add_technique_mapping(
        a.id, "T1566.001", tactic="initial-access",
        manifestation="phish link", evidence_ref="ind1", confidence=0.8,
    )
    store.add_technique_mapping(b.id, "T1566.001", tactic="initial-access")
    store.add_technique_mapping(a.id, "T1059.001", tactic="execution")
    a_techs = store.list_technique_mappings(a.id)
    assert {t.technique_id for t in a_techs} == {"T1566.001", "T1059.001"}
    by = store.list_issues_by_technique("T1566.001")
    assert {i.id for i in by} == {a.id, b.id}


def test_technique_mapping_upsert_dedup(store):
    a = store.create_issue(title="a")
    store.add_technique_mapping(a.id, "T1566.001", confidence=0.5)
    store.add_technique_mapping(a.id, "T1566.001", confidence=0.9)  # same (issue,tech) -> update
    techs = store.list_technique_mappings(a.id)
    assert len(techs) == 1 and techs[0].confidence == 0.9


def test_pre_migration_db_gets_columns(tmp_path):
    """An old investigations.db lacking the new columns + table upgrades cleanly."""
    db = tmp_path / "investigations.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE cases (id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT,
            status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        CREATE TABLE issues (id TEXT PRIMARY KEY, title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open', severity TEXT NOT NULL DEFAULT 'medium',
            kind TEXT NOT NULL DEFAULT 'other', origin TEXT NOT NULL DEFAULT 'agent',
            source_ref TEXT, case_id TEXT, summary TEXT, scope TEXT, recommendations TEXT,
            conclusions TEXT, next_steps TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
        INSERT INTO issues (id,title,status,severity,kind,origin,created_at,updated_at)
            VALUES ('old1','Old','open','high','malware','agent','t0','t0');
        """
    )
    con.commit()
    con.close()
    store = InvestigationStore(data_root=tmp_path)  # init -> migrate
    got = store.get_issue("old1")
    assert got is not None and got.title == "Old"
    assert got.verdict is None and got.report is None  # new cols present, default None
    store.add_technique_mapping("old1", "T1486")  # new table usable
    assert store.list_technique_mappings("old1")[0].technique_id == "T1486"
