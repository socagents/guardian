"""Stage A — structured investigation MCP tools."""
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


def test_issue_set_verdict(store):
    iss = store.create_issue(title="t")
    out = it.issue_set_verdict(iss.id, "TRUE_POSITIVE", confidence=0.9, blast_radius={"hosts": ["h1"]})
    assert out["issue"]["verdict"] == "TRUE_POSITIVE"
    assert out["issue"]["verdict_confidence"] == 0.9
    assert json.loads(out["issue"]["blast_radius"])["hosts"] == ["h1"]


def test_issue_set_verdict_rejects_bad_enum(store):
    iss = store.create_issue(title="t")
    out = it.issue_set_verdict(iss.id, "MAYBE")
    assert "error" in out


def test_issue_add_technique_and_inverse(store):
    a = store.create_issue(title="a")
    out = it.issue_add_technique(a.id, "T1566.001", tactic="initial-access", confidence=0.8)
    assert out["technique"]["technique_id"] == "T1566.001"
    inv = it.incidents_by_technique("T1566.001")
    assert inv["count"] == 1 and inv["issues"][0]["id"] == a.id


def test_generate_investigation_report(store):
    iss = store.create_issue(title="Phish case", kind="phishing")
    it.issue_set_verdict(iss.id, "TRUE_POSITIVE", confidence=0.85,
                         blast_radius={"hosts": ["h1"], "accounts": ["u1"]})
    it.issue_add_technique(iss.id, "T1566.001", tactic="initial-access", manifestation="phish link")
    it.issue_add_event(iss.id, type="finding", content="user clicked link")
    out = it.generate_investigation_report(iss.id)
    assert "markdown" in out and "json" in out
    md = out["markdown"]
    assert "TRUE_POSITIVE" in md and "T1566.001" in md and "Phish case" in md
    # report persisted on the issue
    assert store.get_issue(iss.id).report and "TRUE_POSITIVE" in store.get_issue(iss.id).report
    assert out["json"]["verdict"] == "TRUE_POSITIVE"
