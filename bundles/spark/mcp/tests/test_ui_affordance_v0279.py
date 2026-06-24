"""v0.2.79 ui-dead-affordance batch — Python backend coverage.

Covers the pure-Python sites added/changed in this batch:

  * MEM-F5  — memory_store.search() returns (Memory, score, fts_promoted)
              3-tuples and to_dict(fts_promoted=True) emits the field, so the
              UI's "FTS hit" badge can finally populate.
  * MEM-F13 — list_all(scope_prefix=...) matches scope LIKE '<prefix>%', so
              the UI "session" tab (scope=session → prefix session:) lists the
              dynamic session:<uuid> rows the literal "session" scope never had.
  * SKILL-F15 — list_deleted_skills() enumerates .deleted/ and restore_skill()
                moves a soft-deleted skill back into the live tree (with
                traversal guards), giving the UI a real restore path.
  * OBS-F17 — SqliteTelemetryStore.record() emits a telemetry_recorded audit
              row (the enable/disable toggle was already audited; the record
              path was not).

The TypeScript sites (chat/route plan-approve + tool-status persist + thinking
persist, connector restart/reconcile proxies, telemetry/personality/investigation
proxy routes, approvals CONFIRM gate, knowledge cross-search, pipeline dynamic
lanes, skills dead-surface removal) are validated by the tsc gate + build.

Repo has NO pytest-asyncio — pure-sync paths only here.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase import audit_log as audit_mod  # noqa: E402
from usecase.builtin_components import skills_crud  # noqa: E402
from usecase.memory_store import SqliteMemoryStore  # noqa: E402
from usecase.telemetry import SqliteTelemetryStore  # noqa: E402


class _FakeAudit:
    """Stand-in audit sink: record(action, **kw) appends to .calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def record(self, action: str, **kw: Any) -> str:
        self.calls.append((action, kw))
        return "row-id"

    def rows(self, action: str) -> list[dict[str, Any]]:
        return [kw for a, kw in self.calls if a == action]


# ─────────────────────────────────────────────────────────────────
# MEM-F5 — fts_promoted threads through search() → to_dict()
# ─────────────────────────────────────────────────────────────────


def test_search_returns_three_tuples_with_fts_flag(tmp_path):
    store = SqliteMemoryStore(data_root=tmp_path)
    store.store(key="k1", value="phishing campaign on host alpha", scope="agent")
    store.store(key="k2", value="lateral movement via smb", scope="agent")

    hits = store.search("phishing campaign", limit=5, scope="agent")
    assert hits, "expected at least one hit"
    for tup in hits:
        # #MEM-F5 — the third element is the fts_promoted bool.
        assert len(tup) == 3
        mem, score, fts = tup
        assert isinstance(score, float)
        assert isinstance(fts, bool)


def test_to_dict_emits_fts_promoted_only_when_true():
    from usecase.memory_store import Memory

    m = Memory(
        id="i", key="k", value="v", scope="agent",
        created_at="t", updated_at="t", ttl_seconds=None, meta={},
    )
    # Default / False → field omitted (keeps list payloads lean).
    assert "fts_promoted" not in m.to_dict()
    assert "fts_promoted" not in m.to_dict(fts_promoted=False)
    # True → field present.
    d = m.to_dict(score=0.5, fts_promoted=True)
    assert d["fts_promoted"] is True
    assert d["score"] == 0.5


# ─────────────────────────────────────────────────────────────────
# MEM-F13 — list_all(scope_prefix=...) matches the session:<uuid> family
# ─────────────────────────────────────────────────────────────────


def test_list_all_scope_prefix_matches_session_family(tmp_path):
    store = SqliteMemoryStore(data_root=tmp_path)
    store.store(key="a", value="alpha", scope="session:sess-1")
    store.store(key="b", value="beta", scope="session:sess-2")
    store.store(key="c", value="gamma", scope="agent")

    # The literal "session" scope has no rows (the bug MEM-F13 describes).
    assert store.list_all(scope="session") == []
    # The prefix query surfaces the dynamic session:<uuid> rows.
    pref = store.list_all(scope_prefix="session:")
    assert {m.key for m in pref} == {"a", "b"}
    # Exact scope still works and is unaffected.
    assert {m.key for m in store.list_all(scope="agent")} == {"c"}


def test_list_all_scope_prefix_escapes_like_wildcards(tmp_path):
    store = SqliteMemoryStore(data_root=tmp_path)
    store.store(key="a", value="alpha", scope="session:sess-1")
    # A prefix containing a LIKE wildcard must be escaped, not interpreted —
    # "sess%" should match nothing (no scope literally starts with "sess%").
    assert store.list_all(scope_prefix="sess%") == []


# ─────────────────────────────────────────────────────────────────
# SKILL-F15 — list_deleted_skills() + restore_skill()
# ─────────────────────────────────────────────────────────────────


def _seed_skill(skills_dir: Path, category: str, name: str, body: str = "# s\n") -> None:
    d = skills_dir / category
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(body, encoding="utf-8")


def test_delete_then_list_deleted_then_restore(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    monkeypatch.setattr(skills_crud, "SKILLS_DIR", skills_dir)

    _seed_skill(skills_dir, "workflows", "triage", "# Triage\n")

    # Delete → moves to .deleted/.
    res = skills_crud.delete_skill("workflows/triage.md")
    assert res["success"] is True
    assert (skills_dir / ".deleted" / "triage.md").exists()

    # list_deleted enumerates it.
    listed = skills_crud.list_deleted_skills()
    names = {d["name"] for d in listed["deleted"]}
    assert "triage.md" in names
    assert listed["count"] >= 1

    # Restore brings it back into the live tree.
    restored = skills_crud.restore_skill("triage.md", category="restored")
    assert restored["success"] is True
    assert restored["path"] == "restored/triage.md"
    assert (skills_dir / "restored" / "triage.md").exists()
    assert not (skills_dir / ".deleted" / "triage.md").exists()


def test_restore_rejects_traversal_and_missing(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    (skills_dir / ".deleted").mkdir(parents=True)
    monkeypatch.setattr(skills_crud, "SKILLS_DIR", skills_dir)

    # Path components / traversal in backup_name are rejected.
    assert skills_crud.restore_skill("../../etc/passwd")["success"] is False
    assert skills_crud.restore_skill("sub/dir.md")["success"] is False
    # Non-.md rejected.
    assert skills_crud.restore_skill("foo.txt")["success"] is False
    # Missing backup rejected.
    assert skills_crud.restore_skill("nope.md")["success"] is False
    # Bad category rejected.
    (skills_dir / ".deleted" / "ok.md").write_text("# ok\n", encoding="utf-8")
    assert skills_crud.restore_skill("ok.md", category="../escape")["success"] is False


def test_restore_writes_skill_restored_audit(tmp_path, monkeypatch):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    monkeypatch.setattr(skills_crud, "SKILLS_DIR", skills_dir)
    fake = _FakeAudit()
    monkeypatch.setattr(audit_mod, "_audit", fake)
    monkeypatch.setattr(audit_mod, "audit_log", lambda: fake)

    _seed_skill(skills_dir, "workflows", "triage")
    skills_crud.delete_skill("workflows/triage.md")
    skills_crud.restore_skill("triage.md")

    assert fake.rows("skill_restored"), "expected a skill_restored audit row"


# ─────────────────────────────────────────────────────────────────
# OBS-F17 — telemetry record() emits a telemetry_recorded audit row
# ─────────────────────────────────────────────────────────────────


def test_telemetry_record_emits_audit(tmp_path):
    fake = _FakeAudit()
    store = SqliteTelemetryStore(
        declared_events=["install"],
        default_enabled=True,
        data_root=tmp_path,
        audit_log=fake,
    )
    ok = store.record("install", count=2)
    assert ok is True
    rows = fake.rows("telemetry_recorded")
    assert len(rows) == 1
    assert rows[0]["metadata"]["event"] == "install"
    assert rows[0]["metadata"]["count"] == 2


def test_telemetry_record_no_audit_when_disabled_or_undeclared(tmp_path):
    fake = _FakeAudit()
    store = SqliteTelemetryStore(
        declared_events=["install"],
        default_enabled=False,  # off → record() is a no-op
        data_root=tmp_path,
        audit_log=fake,
    )
    assert store.record("install") is False
    # Enable, then try an UNDECLARED event → still no record + no audit.
    store.set_enabled(True)
    assert store.record("not_declared") is False
    assert fake.rows("telemetry_recorded") == []
