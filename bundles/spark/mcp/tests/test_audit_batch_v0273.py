"""v0.2.73 audit batch — investigation/connector/xsoar/jobs attribution +
missing audit events.

Covers the pure-Python sites added/changed in this batch:

  * CONN-F-actor / JOBS-F12 — actor_from_request reads X-Guardian-Actor and
                              falls back to "user:operator".
  * CONN-F5/F6  — InstanceStore.update() records the NAMES of changed config
                  keys + secret slots and the enabled delta in instance_updated.
  * CONN-F7     — connector_disabled status is "success" (was "skipped").
  * INV-F14     — InvestigationStore.delete_issue emits issue_deleted (with the
                  destroyed issue's title/kind) before the cascade delete;
                  delete_case emits case_deleted.
  * INV-F11     — case_relate emits a case_related audit row.
  * INV-F2      — issue_set_verdict / issue_add_technique append a timeline event.
  * JOBS-F4     — _fire auto-disable (unknown-tool) emits job_disabled.
  * JOBS-F7     — _mark_interrupted_session emits job_session_interrupted.

The TypeScript sites (XSOAR-F9 / INV-F15 header forwarding) + the XSOAR
connector `steps` envelopes (XSOAR-F6, run in a separate container) are
validated by the tsc gate + live smoke; this file covers the Python sites.

Repo has NO pytest-asyncio — async paths are driven via asyncio.run().
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402

from usecase import audit_log as audit_mod  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# CONN-F-actor / JOBS-F12 — actor_from_request
# ─────────────────────────────────────────────────────────────────


class _FakeHeaders:
    def __init__(self, mapping: dict[str, str]) -> None:
        self._m = mapping

    def get(self, key: str, default: Any = None) -> Any:
        return self._m.get(key, default)


class _FakeRequest:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = _FakeHeaders(headers)


def test_actor_from_request_reads_header():
    from api.trigger_context import actor_from_request

    req = _FakeRequest({"X-Guardian-Actor": "apikey:abc123"})
    assert actor_from_request(req) == "apikey:abc123"


def test_actor_from_request_falls_back_when_absent():
    from api.trigger_context import actor_from_request

    assert actor_from_request(_FakeRequest({})) == "user:operator"


def test_actor_from_request_falls_back_on_blank_header():
    from api.trigger_context import actor_from_request

    assert actor_from_request(_FakeRequest({"X-Guardian-Actor": "   "})) == "user:operator"


def test_actor_from_request_truncates_oversized_header():
    from api.trigger_context import actor_from_request, MAX_ACTOR_LEN

    long = "user:" + ("x" * 500)
    out = actor_from_request(_FakeRequest({"X-Guardian-Actor": long}))
    assert len(out) == MAX_ACTOR_LEN


# ─────────────────────────────────────────────────────────────────
# CONN-F5 / CONN-F6 — instance_updated metadata
# ─────────────────────────────────────────────────────────────────


def _instance_store(tmp_path: Path):
    from usecase.instance_store import InstanceStore

    # No SecretStore → legacy literal-value mode (fine for tests).
    return InstanceStore(data_root=tmp_path)


def test_instance_updated_records_changed_config_keys(tmp_path, monkeypatch):
    store = _instance_store(tmp_path)
    inst = store.create(
        "xsoar", "primary",
        {"base_url": "https://a", "auth_method": "key"},
        {},
    )
    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event", lambda action, **kw: calls.append((action, kw))
    )

    store.update(inst.id, config={"base_url": "https://b", "auth_method": "key"})

    rows = [kw for a, kw in calls if a == "instance_updated"]
    assert len(rows) == 1
    meta = rows[0]["metadata"]
    # only base_url's VALUE changed → only base_url is named
    assert meta["config_keys_changed"] == ["base_url"]
    assert meta["config_changed"] is True


def test_instance_updated_records_secret_slot_names(tmp_path, monkeypatch):
    store = _instance_store(tmp_path)
    inst = store.create("xsoar", "primary", {}, {"api_key": "old"})
    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event", lambda action, **kw: calls.append((action, kw))
    )

    # rotate api_key; auth_token left as the "***" sentinel (unchanged).
    store.update(inst.id, secrets={"api_key": "new", "auth_token": "***"})

    meta = [kw for a, kw in calls if a == "instance_updated"][0]["metadata"]
    assert meta["secret_slots_changed"] == ["api_key"]
    # NEVER the secret value
    assert "new" not in str(meta)
    assert "old" not in str(meta)


def test_instance_updated_records_enabled_delta(tmp_path, monkeypatch):
    store = _instance_store(tmp_path)
    inst = store.create("xsoar", "primary", {}, {}, enabled=True)
    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event", lambda action, **kw: calls.append((action, kw))
    )

    store.update(inst.id, enabled=False)

    meta = [kw for a, kw in calls if a == "instance_updated"][0]["metadata"]
    assert meta["enabled_changed"] is True
    assert meta["enabled_value"] is False


def test_instance_updated_enabled_unchanged_when_not_passed(tmp_path, monkeypatch):
    store = _instance_store(tmp_path)
    inst = store.create("xsoar", "primary", {"base_url": "https://a"}, {}, enabled=True)
    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event", lambda action, **kw: calls.append((action, kw))
    )

    store.update(inst.id, config={"base_url": "https://b"})

    meta = [kw for a, kw in calls if a == "instance_updated"][0]["metadata"]
    assert meta["enabled_changed"] is False
    # enabled_value still reflects the (unchanged) current value
    assert meta["enabled_value"] is True


# ─────────────────────────────────────────────────────────────────
# INV-F14 — delete_issue / delete_case emit a destruction audit row
# ─────────────────────────────────────────────────────────────────


def _inv_store(tmp_path: Path):
    from usecase.investigation_store import InvestigationStore

    return InvestigationStore(data_root=tmp_path)


def test_delete_issue_emits_issue_deleted_with_identity(tmp_path, monkeypatch):
    store = _inv_store(tmp_path)
    issue = store.create_issue(title="Phishing wave", kind="phishing", severity="high")
    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event", lambda action, **kw: calls.append((action, kw))
    )

    assert store.delete_issue(issue.id) is True

    rows = [kw for a, kw in calls if a == "issue_deleted"]
    assert len(rows) == 1
    meta = rows[0]["metadata"]
    assert meta["issue_id"] == issue.id
    assert meta["title"] == "Phishing wave"
    assert meta["kind"] == "phishing"
    assert rows[0]["status"] == "success"
    assert rows[0]["target"] == f"issue:{issue.id}"


def test_delete_missing_issue_emits_nothing(tmp_path, monkeypatch):
    store = _inv_store(tmp_path)
    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event", lambda action, **kw: calls.append((action, kw))
    )
    assert store.delete_issue("does-not-exist") is False
    assert not [c for c in calls if c[0] == "issue_deleted"]


def test_delete_case_emits_case_deleted(tmp_path, monkeypatch):
    store = _inv_store(tmp_path)
    case = store.create_case(title="Campaign A")
    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event", lambda action, **kw: calls.append((action, kw))
    )

    assert store.delete_case(case.id) is True

    rows = [kw for a, kw in calls if a == "case_deleted"]
    assert len(rows) == 1
    assert rows[0]["metadata"]["case_id"] == case.id
    assert rows[0]["metadata"]["title"] == "Campaign A"


# ─────────────────────────────────────────────────────────────────
# INV-F2 / INV-F11 — investigation tools timeline + case audit
# ─────────────────────────────────────────────────────────────────


def _wire_inv_tools(tmp_path, monkeypatch):
    """Point investigation_tools._store at a fresh InvestigationStore."""
    from usecase.builtin_components import investigation_tools as it

    store = _inv_store(tmp_path)
    monkeypatch.setattr(it, "_store", lambda: (store, None))
    return it, store


def test_issue_set_verdict_appends_timeline_event(tmp_path, monkeypatch):
    it, store = _wire_inv_tools(tmp_path, monkeypatch)
    issue = store.create_issue(title="t", kind="malware")

    out = it.issue_set_verdict(issue.id, "TRUE_POSITIVE", confidence=0.9)
    assert "issue" in out

    events = store.list_events(issue.id)
    assert any(e.type == "verdict_set" for e in events)
    assert any("TRUE_POSITIVE" in e.content for e in events)


def test_issue_add_technique_appends_timeline_event(tmp_path, monkeypatch):
    it, store = _wire_inv_tools(tmp_path, monkeypatch)
    issue = store.create_issue(title="t", kind="malware")

    out = it.issue_add_technique(issue.id, "T1566.001", tactic="initial-access")
    assert "technique" in out

    events = store.list_events(issue.id)
    assert any(e.type == "technique_mapped" for e in events)
    assert any("T1566.001" in e.content for e in events)


def test_case_relate_emits_case_related_audit(tmp_path, monkeypatch):
    it, store = _wire_inv_tools(tmp_path, monkeypatch)
    a = store.create_case(title="A")
    b = store.create_case(title="B")
    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event", lambda action, **kw: calls.append((action, kw))
    )

    out = it.case_relate(a.id, b.id, "same-campaign", note="overlapping IoCs")
    assert "relationship" in out

    rows = [kw for act, kw in calls if act == "case_related"]
    assert len(rows) == 1
    meta = rows[0]["metadata"]
    assert meta["source_case_id"] == a.id
    assert meta["target_case_id"] == b.id
    assert meta["relationship_type"] == "same-campaign"


# ─────────────────────────────────────────────────────────────────
# JOBS-F4 — _fire auto-disable emits job_disabled
# ─────────────────────────────────────────────────────────────────


def _scheduler(tmp_path, dispatcher):
    from usecase.job_scheduler import CroniterJobScheduler

    return CroniterJobScheduler(
        definitions=[], dispatcher=dispatcher, data_root=tmp_path,
    )


def test_fire_unknown_tool_autodisable_emits_job_disabled(tmp_path, monkeypatch):
    async def _bad_dispatch(tool_name, args, **_kw):
        # The error string the _build_dispatch / dispatch layer produces for a
        # missing tool; _fire's auto-disable branch keys off this substring.
        raise KeyError("job action references unknown tool 'ghost_tool'")

    sched = _scheduler(tmp_path, _bad_dispatch)
    sched.add_job(
        name="ghost", cron="0 * * * *",
        action={"type": "tool_call", "name": "ghost_tool"},
    )

    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event", lambda action, **kw: calls.append((action, kw))
    )

    run = asyncio.run(sched.trigger_now("ghost"))
    assert run is not None
    assert run.status == "failure"

    disabled = [kw for a, kw in calls if a == audit_mod.ACTION_JOB_DISABLED]
    assert len(disabled) == 1
    assert disabled[0]["target"] == "job:ghost"
    assert disabled[0]["metadata"]["auto"] is True
    assert disabled[0]["metadata"]["reason"] == "unknown_tool"
    # the job row is actually disabled now
    assert sched.get_job("ghost").enabled is False


def test_fire_success_does_not_emit_job_disabled(tmp_path, monkeypatch):
    async def _ok_dispatch(tool_name, args, **_kw):
        return {"ok": True}

    sched = _scheduler(tmp_path, _ok_dispatch)
    sched.add_job(
        name="good", cron="0 * * * *",
        action={"type": "tool_call", "name": "real_tool"},
    )

    calls = []
    monkeypatch.setattr(
        audit_mod, "record_event", lambda action, **kw: calls.append((action, kw))
    )

    run = asyncio.run(sched.trigger_now("good"))
    assert run is not None
    assert run.status == "success"
    assert not [a for a, _ in calls if a == audit_mod.ACTION_JOB_DISABLED]


# ─────────────────────────────────────────────────────────────────
# JOBS-F7 — _mark_interrupted_session emits job_session_interrupted
# ─────────────────────────────────────────────────────────────────


def test_mark_interrupted_emits_audit(tmp_path, monkeypatch):
    from usecase.session_store import SqliteSessionStore, set_session_store

    sess_store = SqliteSessionStore(data_root=tmp_path / "sessions")
    set_session_store(sess_store)
    try:
        sched = _scheduler(tmp_path, lambda *a, **k: None)
        sess = sess_store.create_session(title="<skill ...>")
        sess_store.append_message(sess.id, role="user", content="seed")

        calls = []
        monkeypatch.setattr(
            audit_mod, "record_event",
            lambda action, **kw: calls.append((action, kw)),
        )

        sched._mark_interrupted_session(sess.id, "turn exceeded the scheduler timeout")

        rows = [kw for a, kw in calls if a == "job_session_interrupted"]
        assert len(rows) == 1
        assert rows[0]["target"] == f"session:{sess.id}"
        assert rows[0]["metadata"]["session_id"] == sess.id
        assert "timeout" in rows[0]["metadata"]["reason"]
    finally:
        set_session_store(None)
