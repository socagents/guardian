"""scheduled_by backfill for legacy autonomous-job sessions — v0.2.40.

Sessions created by the bundled autonomous jobs (seeder /
investigation-loop / judge) are now tagged `meta.scheduled_by` at
create time, but ones created before that fix — especially turns that
timed out before the old turn-end tag ran — carry empty meta and
flood the operator's chat sidebar (`exclude_scheduled` can't hide an
untagged row). `backfill_scheduled_by_from_titles` tags those by
matching the bundled-job prompt signatures.
"""

from __future__ import annotations

import pytest

from usecase.session_store import SqliteSessionStore


@pytest.fixture
def store(tmp_path) -> SqliteSessionStore:
    return SqliteSessionStore(data_root=tmp_path)


def test_backfill_tags_loop_titles_only(store: SqliteSessionStore) -> None:
    skill = store.create_session(
        title='<skill name="xsoar_case_investigation">\n---\nname: ...'
    )
    seeder = store.create_session(
        title="Seed the autonomous investigation loop with ONE new case."
    )
    judge = store.create_session(
        title="You are the autonomous investigation-judge. Be TERSE."
    )
    human = store.create_session(title="why did incident 4137 fire?")

    tagged = store.backfill_scheduled_by_from_titles()
    assert tagged == 3

    # The three bundled-job sessions are now tagged ...
    for s in (skill, seeder, judge):
        assert (
            store.get_session(s.id).meta.get("scheduled_by")
            == "autonomous-loop"
        )
    # ... and the operator's own session is untouched.
    assert "scheduled_by" not in store.get_session(human.id).meta

    # exclude_scheduled now hides exactly the three loop sessions.
    visible = {s.id for s in store.list_sessions(exclude_scheduled=True)}
    assert human.id in visible
    assert visible.isdisjoint({skill.id, seeder.id, judge.id})


def test_backfill_is_idempotent(store: SqliteSessionStore) -> None:
    store.create_session(
        title="Seed the autonomous investigation loop with ONE new case."
    )
    assert store.backfill_scheduled_by_from_titles() == 1
    # Second run finds nothing new to tag.
    assert store.backfill_scheduled_by_from_titles() == 0


def test_backfill_never_overwrites_existing_tag(
    store: SqliteSessionStore,
) -> None:
    s = store.create_session(
        title="Seed the autonomous investigation loop with ONE new case.",
        meta={"scheduled_by": "guardian-incident-seeder"},
    )
    assert store.backfill_scheduled_by_from_titles() == 0
    # The original (more specific) tag is preserved.
    assert (
        store.get_session(s.id).meta["scheduled_by"]
        == "guardian-incident-seeder"
    )
