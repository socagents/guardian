"""#82 — delete_skill emits a `skill_deleted` audit event.

update_skill already audits (`skill_updated`); delete_skill did not, so an
operator UI/REST delete (gate-bypassing) left no trace. This pins the
symmetric audit on the core skills_crud.delete_skill so EVERY delete path
records to /observability/events.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.builtin_components import skills_crud as sc  # noqa: E402
from usecase import audit_log as audit_mod  # noqa: E402


@pytest.fixture()
def skills_dir(tmp_path, monkeypatch):
    (tmp_path / "workflows").mkdir()
    (tmp_path / "workflows" / "demo.md").write_text(
        "---\nname: demo\n---\n# Demo\nbody\n", encoding="utf-8"
    )
    monkeypatch.setattr(sc, "SKILLS_DIR", tmp_path)
    return tmp_path


class _FakeAudit:
    def __init__(self):
        self.calls = []

    def record(self, **kw):
        self.calls.append(kw)
        return "id"


def test_delete_skill_emits_audit(skills_dir, monkeypatch):
    fake = _FakeAudit()
    monkeypatch.setattr(audit_mod, "audit_log", lambda: fake)

    res = sc.delete_skill("workflows/demo.md")
    assert res["success"] is True

    deleted = [c for c in fake.calls if c.get("action") == "skill_deleted"]
    assert len(deleted) == 1
    assert deleted[0]["target"] == "skill:workflows/demo.md"
    assert deleted[0]["status"] == "success"
    assert deleted[0]["metadata"]["file_path"] == "workflows/demo.md"


def test_delete_missing_skill_no_audit(skills_dir, monkeypatch):
    fake = _FakeAudit()
    monkeypatch.setattr(audit_mod, "audit_log", lambda: fake)

    res = sc.delete_skill("workflows/nope.md")
    assert res["success"] is False
    assert not any(c.get("action") == "skill_deleted" for c in fake.calls)


def test_delete_audit_failure_never_breaks(skills_dir, monkeypatch):
    def boom():
        raise RuntimeError("audit down")

    monkeypatch.setattr(audit_mod, "audit_log", boom)
    res = sc.delete_skill("workflows/demo.md")
    assert res["success"] is True  # delete still succeeds
