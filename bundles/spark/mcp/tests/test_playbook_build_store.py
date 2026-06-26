"""PlaybookBuildStore — sqlite-backed history of agent-drafted playbooks.

Mirrors the InvestigationStore test style. Each test gets a fresh store at a
tmp db path so they don't share the on-disk db (and never touch /app/data).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase.playbook_build_store import (  # noqa: E402
    PlaybookBuild,
    PlaybookBuildStore,
)


@pytest.fixture()
def store(tmp_path):
    return PlaybookBuildStore(db_path=str(tmp_path / "playbook_builds.db"))


# ─── Create / get ────────────────────────────────────────────────────


def test_create_and_get_build_round_trips(store):
    build = store.create_build(
        use_case="Contain a phishing incident: block sender + isolate host",
        product="xsoar",
        playbook_name="Phishing - Contain",
        playbook_yaml="id: phishing-contain\nname: Phishing - Contain\n",
        validation_json='{"valid": true, "task_count": 4}',
        session_id="sess-123",
        created_by="user:operator",
    )
    assert isinstance(build, PlaybookBuild)
    assert build.id
    fetched = store.get_build(build.id)
    assert fetched == build
    assert fetched.use_case.startswith("Contain a phishing incident")
    assert fetched.product == "xsoar"
    assert fetched.playbook_name == "Phishing - Contain"
    assert fetched.status == "drafted"
    assert fetched.validation_json == '{"valid": true, "task_count": 4}'
    assert fetched.session_id == "sess-123"
    assert fetched.created_by == "user:operator"
    assert fetched.deploy_summary is None
    assert fetched.test_incident_id is None
    assert fetched.created_at and fetched.updated_at


def test_get_missing_build_returns_none(store):
    assert store.get_build("nope") is None


def test_create_build_defaults(store):
    build = store.create_build(use_case="bare minimum")
    assert build.product is None
    assert build.playbook_name is None
    assert build.playbook_yaml is None
    assert build.status == "drafted"
    assert build.created_by == "agent"
    assert build.session_id is None


def test_create_build_requires_use_case(store):
    with pytest.raises(ValueError):
        store.create_build(use_case="")


# ─── Listing (ordering + status filter) ──────────────────────────────


def test_list_builds_order_and_status_filter(store):
    a = store.create_build(use_case="first")
    b = store.create_build(use_case="second")
    store.update_build(b.id, status="validated")

    # desc (default) = newest first; asc = oldest first.
    desc_ids = [x.id for x in store.list_builds()]
    asc_ids = [x.id for x in store.list_builds(order="asc")]
    assert set(desc_ids) == {a.id, b.id}
    assert asc_ids == list(reversed(desc_ids))
    assert asc_ids[0] == a.id  # a created before b

    # status filter narrows to one lifecycle stage.
    drafted_ids = {x.id for x in store.list_builds(status="drafted")}
    validated_ids = {x.id for x in store.list_builds(status="validated")}
    assert drafted_ids == {a.id}
    assert validated_ids == {b.id}
    assert store.list_builds(status="deployed") == []


# ─── Update (partial fields + updated_at bump + transitions) ──────────


def test_update_build_partial_fields_and_updated_at(store):
    build = store.create_build(use_case="draft me", product="xsoar")
    updated = store.update_build(
        build.id,
        status="validated",
        playbook_name="Resolved Name",
        playbook_yaml="id: resolved\nname: Resolved Name\n",
        validation_json='{"valid": true, "errors": [], "task_count": 3}',
    )
    assert updated is not None
    assert updated.status == "validated"
    assert updated.playbook_name == "Resolved Name"
    assert updated.validation_json == '{"valid": true, "errors": [], "task_count": 3}'
    # untouched fields preserved
    assert updated.use_case == "draft me"
    assert updated.product == "xsoar"
    # updated_at advanced (or at least not regressed)
    assert updated.updated_at >= build.created_at


def test_update_build_status_transition_to_deployed_and_tested(store):
    build = store.create_build(use_case="deploy me")
    deployed = store.update_build(
        build.id, status="deployed", deploy_summary="Deployed OK", test_incident_id="inc-42",
    )
    assert deployed.status == "deployed"
    assert deployed.deploy_summary == "Deployed OK"
    assert deployed.test_incident_id == "inc-42"
    tested = store.update_build(build.id, status="tested")
    assert tested.status == "tested"
    # test_incident_id sticks across the next update (None values are skipped)
    assert tested.test_incident_id == "inc-42"


def test_update_build_ignores_unknown_keys(store):
    build = store.create_build(use_case="x")
    updated = store.update_build(build.id, bogus_field="ignored", status="failed")
    assert updated is not None
    assert updated.status == "failed"
    assert not hasattr(updated, "bogus_field")


def test_update_build_no_known_fields_returns_current(store):
    build = store.create_build(use_case="x")
    # No updatable keys → returns the existing build unchanged.
    same = store.update_build(build.id, only_unknown="nope")
    assert same is not None and same.id == build.id
    assert same.updated_at == build.updated_at


def test_update_missing_build_returns_none(store):
    assert store.update_build("nope", status="validated") is None


# ─── Delete ──────────────────────────────────────────────────────────


def test_delete_build(store):
    build = store.create_build(use_case="delete me")
    assert store.delete_build(build.id) is True
    assert store.get_build(build.id) is None
    # second delete is a no-op
    assert store.delete_build(build.id) is False


# ─── Schema bootstrap ────────────────────────────────────────────────


def test_fresh_db_auto_creates_schema(tmp_path):
    db = tmp_path / "fresh.db"
    assert not db.exists()
    s = PlaybookBuildStore(db_path=str(db))
    # Schema is created on construction; a create/list round-trips cleanly.
    assert s.list_builds() == []
    s.create_build(use_case="hello")
    assert len(s.list_builds()) == 1
    assert db.exists()
