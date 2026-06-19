"""scheduled_by backfill + subagent exclusion for the chat sidebar — v0.2.40.

Sessions created by the bundled autonomous jobs (seeder /
investigation-loop / judge) are now tagged `meta.scheduled_by` at
create time, but ones created before that fix — especially turns that
timed out before the old turn-end tag ran — carry empty meta and
flood the operator's chat sidebar (`exclude_scheduled` can't hide an
untagged row). `backfill_scheduled_by_for_autonomous_jobs` tags those
by matching the bundled-job prompt signatures against BOTH the title
and the first message's content (the latter catches untitled
message_count=1 orphans). `exclude_scheduled` also hides subagent
sessions.
"""

from __future__ import annotations

import pytest

from usecase.session_store import SqliteSessionStore


@pytest.fixture
def store(tmp_path) -> SqliteSessionStore:
    return SqliteSessionStore(data_root=tmp_path)


def test_backfill_tags_titled_loop_sessions(store: SqliteSessionStore) -> None:
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

    tagged = store.backfill_scheduled_by_for_autonomous_jobs()
    assert tagged == 3
    for s in (skill, seeder, judge):
        assert (
            store.get_session(s.id).meta.get("scheduled_by")
            == "autonomous-loop"
        )
    assert "scheduled_by" not in store.get_session(human.id).meta


def test_backfill_tags_untitled_orphan_by_first_message(
    store: SqliteSessionStore,
) -> None:
    # The common residue: a timed-out tick — no title, empty meta, and
    # one user message that IS the raw skill prompt. Title-only matching
    # would miss it; first-message matching catches it.
    orphan = store.create_session(title=None)
    store.append_message(
        orphan.id,
        role="user",
        content='<skill name="xsoar_case_investigation">\n---\nname: xsoar...',
    )
    # An operator session whose first message is unrelated stays visible.
    human = store.create_session(title=None)
    store.append_message(
        human.id, role="user", content="summarize case 4821 for me"
    )

    tagged = store.backfill_scheduled_by_for_autonomous_jobs()
    assert tagged == 1
    assert store.get_session(orphan.id).meta.get("scheduled_by") == "autonomous-loop"
    assert "scheduled_by" not in store.get_session(human.id).meta

    visible = {s.id for s in store.list_sessions(exclude_scheduled=True)}
    assert human.id in visible
    assert orphan.id not in visible


def test_backfill_is_idempotent_and_preserves_existing(
    store: SqliteSessionStore,
) -> None:
    store.create_session(
        title="Seed the autonomous investigation loop with ONE new case."
    )
    tagged_session = store.create_session(
        title="Seed the autonomous investigation loop with ONE new case.",
        meta={"scheduled_by": "guardian-incident-seeder"},
    )
    assert store.backfill_scheduled_by_for_autonomous_jobs() == 1
    # Second run finds nothing new.
    assert store.backfill_scheduled_by_for_autonomous_jobs() == 0
    # The pre-existing (more specific) tag is preserved.
    assert (
        store.get_session(tagged_session.id).meta["scheduled_by"]
        == "guardian-incident-seeder"
    )


def test_exclude_scheduled_hides_subagent_sessions(
    store: SqliteSessionStore,
) -> None:
    operator = store.create_session(title="my investigation")
    subagent = store.create_session(
        title=None,
        meta={
            "subagent_origin": "parent_session",
            "parent_session_id": "abc",
            "agent_name": "threat-hunter",
        },
    )
    # A fork keeps parent_session_id but NOT subagent_origin — stays visible.
    fork = store.create_session(
        title="my investigation (fork)",
        meta={"forked_from": operator.id},
    )

    visible = {s.id for s in store.list_sessions(exclude_scheduled=True)}
    assert operator.id in visible
    assert fork.id in visible
    assert subagent.id not in visible
