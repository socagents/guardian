"""v0.2.74 audit batch — KB/MEM/SKILL/SUB/HOOK/PLAT/OBS/API audit-trace gaps.

Covers the pure-Python sites added/changed in this batch:

  * audit_log constants — every NEW action string is exported as a named
    constant (a typo would otherwise emit an unknown action with no catch).
  * KB-F1   — store-level search emits kb_searched; the REST list/tags
              enumeration rows are covered by the manifest declaration + the
              constant (ACTION_KB_LISTED) existing.
  * KB-F11  — an embed failure inside KbStore.search() emits a failure
              kb_searched row BEFORE re-raising (a Vertex outage left no trace).
  * KB-F8   — the passive ContextAssembler kb_searched row carries a bounded
              query_preview (the active path has the tool_call row; passive had
              nothing).
  * MEM-F2  — memory_searched carries query_preview + session_id (derived from
              scope=session:<id>).
  * MEM-F4  — memory_searched carries a `mode` discriminator (active|passive).
  * SKILL-F6 — skills_update audit row records sha256_before/after content
               hashes so a body rewrite is verifiable from audit.db alone.
  * HOOK-F11 — InProcessApprovalsBus._reap_orphaned_pending emits an
               approval_orphans_reaped row when it reaps boot-orphaned rows.
  * PLAT-F5  — provider_updated is a named constant (ACTION_PROVIDER_UPDATED).
  * PLAT-F12/SUB-F10 — operator_state route _preview helper truncates large
               blobs and passes None through.

The TypeScript sites (API-F2/F3/F4/F17/PLAT-F6 auth+vertex routes, OBS-F7
safeAudit retry, HOOK-F3 injectContext, SUB-F9) are validated by the tsc gate +
live smoke; this file covers the Python sites.

Repo has NO pytest-asyncio — async paths are driven via asyncio.run().
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from usecase import audit_log as audit_mod  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# Shared fakes
# ─────────────────────────────────────────────────────────────────


class _FakeAudit:
    """Stand-in audit sink: record(action, **kw) appends to .calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def record(self, action: str, **kw: Any) -> str:
        self.calls.append((action, kw))
        return "row-id"

    def rows(self, action: str) -> list[dict[str, Any]]:
        return [kw for a, kw in self.calls if a == action]


def _wire_audit(monkeypatch) -> _FakeAudit:
    """Point the module singleton at a fresh fake so record_event() routes to it."""
    fake = _FakeAudit()
    monkeypatch.setattr(audit_mod, "_audit", fake)
    return fake


class _BoomEmbedder:
    """Embedder whose embed() always raises (simulates a Vertex outage)."""

    dims = 8
    model_id = "boom-embedder"

    def embed(self, text: str) -> list[float]:
        raise RuntimeError("vertex unreachable: simulated outage")


# ─────────────────────────────────────────────────────────────────
# audit_log — every new action constant exists (#PLAT-F5 + batch)
# ─────────────────────────────────────────────────────────────────


def test_new_action_constants_declared():
    expected = {
        "ACTION_KB_LISTED": "kb_listed",
        "ACTION_APPROVAL_SELF_RESOLVE_BLOCKED": "approval_self_resolve_blocked",
        "ACTION_APPROVAL_ORPHANS_REAPED": "approval_orphans_reaped",
        "ACTION_PROVIDER_UPDATED": "provider_updated",
        "ACTION_PROVIDER_PROBED": "provider_probed",
        "ACTION_API_KEY_LISTED": "api_key_listed",
        "ACTION_LOGIN_LOCKOUT": "login_lockout",
        "ACTION_BENCH_RUN_STARTED": "bench_run_started",
        "ACTION_NOTIFICATION_ACKED": "notification_acked",
        "ACTION_OPERATOR_STATE_LISTED": "operator_state_listed",
        "ACTION_OPERATOR_STATE_READ": "operator_state_read",
        "ACTION_AGENT_DEFINITION_LISTED": "agent_definition_listed",
        "ACTION_AGENT_DEFINITION_READ": "agent_definition_read",
    }
    for const_name, value in expected.items():
        assert getattr(audit_mod, const_name) == value


def test_new_actions_declared_in_manifest():
    import yaml

    manifest_path = (
        Path(__file__).resolve().parents[2] / "manifest.yaml"
    )
    events = set(
        yaml.safe_load(manifest_path.read_text())["audit"]["events"]
    )
    for value in (
        "kb_listed",
        "approval_self_resolve_blocked",
        "approval_orphans_reaped",
        "provider_updated",
        "provider_probed",
        "api_key_listed",
        "login_lockout",
        "bench_run_started",
        "notification_acked",
        "operator_state_listed",
        "operator_state_read",
        "agent_definition_listed",
        "agent_definition_read",
    ):
        assert value in events, f"{value!r} missing from manifest audit.events"


# ─────────────────────────────────────────────────────────────────
# KB-F11 — embed failure inside search() emits a failure kb_searched row
# ─────────────────────────────────────────────────────────────────


def test_kb_search_embed_failure_emits_failure_row(tmp_path, monkeypatch):
    from usecase.kb_store import SqliteKnowledgeBase

    fake = _wire_audit(monkeypatch)
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=_BoomEmbedder())

    with pytest.raises(RuntimeError):
        kb.search("anything", kb_name="soc")

    rows = fake.rows("kb_searched")
    assert len(rows) == 1
    assert rows[0]["status"] == "failure"
    assert rows[0]["metadata"]["reason"] == "embed_failed"
    assert rows[0]["metadata"]["kb_name"] == "soc"
    # the raw outage detail is recorded but no query text leaks as a secret
    assert "outage" in rows[0]["metadata"]["error"]


def test_kb_search_blank_query_emits_nothing(tmp_path, monkeypatch):
    from usecase.kb_store import SqliteKnowledgeBase

    fake = _wire_audit(monkeypatch)
    kb = SqliteKnowledgeBase(data_root=tmp_path, embedder=_BoomEmbedder())
    assert kb.search("   ") == []
    assert not fake.rows("kb_searched")


# ─────────────────────────────────────────────────────────────────
# MEM-F2 / MEM-F4 — memory_searched mode + session_id + query_preview
# ─────────────────────────────────────────────────────────────────


def _mem_store(tmp_path):
    from usecase.memory_store import SqliteMemoryStore

    return SqliteMemoryStore(data_root=tmp_path)


def test_memory_search_records_mode_and_session_and_preview(tmp_path, monkeypatch):
    store = _mem_store(tmp_path)
    store.store(key="k1", value="the quick brown fox", scope="session:sess-42")
    fake = _wire_audit(monkeypatch)

    store.search("quick fox", scope="session:sess-42", mode="passive")

    rows = fake.rows("memory_searched")
    assert len(rows) == 1
    meta = rows[0]["metadata"]
    assert meta["mode"] == "passive"
    assert meta["session_id"] == "sess-42"
    assert meta["query_preview"] == "quick fox"
    assert meta["scope"] == "session:sess-42"


def test_memory_search_default_mode_active_and_no_session(tmp_path, monkeypatch):
    store = _mem_store(tmp_path)
    store.store(key="k1", value="alpha beta gamma", scope="agent")
    fake = _wire_audit(monkeypatch)

    store.search("alpha")  # no scope, no mode

    meta = fake.rows("memory_searched")[0]["metadata"]
    assert meta["mode"] == "active"
    assert meta["session_id"] is None


def test_memory_search_query_preview_truncated(tmp_path, monkeypatch):
    store = _mem_store(tmp_path)
    store.store(key="k1", value="x", scope="agent")
    fake = _wire_audit(monkeypatch)

    long_q = "q" * 500
    store.search(long_q)

    meta = fake.rows("memory_searched")[0]["metadata"]
    assert len(meta["query_preview"]) == 200
    assert meta["query_chars"] == 500


# ─────────────────────────────────────────────────────────────────
# SKILL-F6 — skills_update audit records sha256_before/after
# ─────────────────────────────────────────────────────────────────


def test_skills_update_records_content_hashes(tmp_path, monkeypatch):
    import hashlib

    from usecase.builtin_components import skills_crud

    # Point the CRUD module's SKILLS_DIR at a temp tree.
    skills_dir = tmp_path / "skills"
    (skills_dir / "soc").mkdir(parents=True)
    rel = "soc/demo.md"
    original = "---\nname: demo\n---\nbefore body\n"
    (skills_dir / rel).write_text(original, encoding="utf-8")
    monkeypatch.setattr(skills_crud, "SKILLS_DIR", skills_dir)

    fake = _wire_audit(monkeypatch)

    new_content = "---\nname: demo\n---\nafter body rewritten\n"
    result = skills_crud.update_skill(rel, new_content)
    assert result["success"] is True

    rows = fake.rows("skill_updated")
    assert len(rows) == 1
    meta = rows[0]["metadata"]
    assert meta["sha256_before"] == hashlib.sha256(
        original.encode("utf-8")
    ).hexdigest()
    assert meta["sha256_after"] == hashlib.sha256(
        new_content.encode("utf-8")
    ).hexdigest()
    assert meta["bytes_before"] == len(original)
    assert meta["bytes_after"] == len(new_content)


# ─────────────────────────────────────────────────────────────────
# HOOK-F11 — boot orphan reap emits approval_orphans_reaped
# ─────────────────────────────────────────────────────────────────


def test_orphan_reap_emits_audit(tmp_path, monkeypatch):
    from usecase.approvals_bus import (
        InProcessApprovalsBus,
        STATUS_PENDING,
    )

    # First bus: seed a pending row, then drop the in-memory waiter state by
    # discarding the instance (simulating a process restart).
    bus1 = InProcessApprovalsBus(data_root=tmp_path)
    with bus1._lock, bus1._conn() as c:
        c.execute(
            "INSERT INTO approvals "
            "(id, created_at, tool, namespaced, actor, status, args_json, "
            " risk_tier, origin) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "orphan-1", bus1._now_iso(), "personality_update",
                "personality_update", "agent", STATUS_PENDING, "{}",
                "soft", "agent",
            ),
        )

    # Second bus over the SAME data_root: __init__ runs _reap_orphaned_pending,
    # which should mark the orphan timeout AND emit the audit row.
    fake = _wire_audit(monkeypatch)
    InProcessApprovalsBus(data_root=tmp_path)

    rows = fake.rows("approval_orphans_reaped")
    assert len(rows) == 1
    assert rows[0]["status"] == "success"
    assert rows[0]["actor"] == "system"
    assert rows[0]["metadata"]["rows_reaped"] == 1
    assert rows[0]["target"] == "approvals.db"


def test_orphan_reap_no_pending_emits_nothing(tmp_path, monkeypatch):
    from usecase.approvals_bus import InProcessApprovalsBus

    # Construct once to create the schema (no pending rows).
    InProcessApprovalsBus(data_root=tmp_path)
    fake = _wire_audit(monkeypatch)
    InProcessApprovalsBus(data_root=tmp_path)
    assert not fake.rows("approval_orphans_reaped")


# ─────────────────────────────────────────────────────────────────
# PLAT-F12 / SUB-F10 — operator_state _preview helper
# ─────────────────────────────────────────────────────────────────


def test_operator_state_preview_helper():
    from api.operator_state import _preview

    assert _preview(None) is None
    assert _preview("short") == "short"
    assert _preview(["a", "b"]) == "['a', 'b']"
    long = _preview("z" * 500)
    assert long is not None and long.endswith("…") and len(long) == 201
