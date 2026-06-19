"""Autonomous-loop turn-failure handling — v0.2.39.

Root cause this anchors: the job scheduler used a hard-coded 300s read
timeout on a prompt-job's POST /api/chat stream. A long autonomous
investigation (the xsoar_case_investigation skill makes 30-47 tool
calls) routinely exceeded it, aborting the turn AFTER the user prompt
persisted but BEFORE the assistant turn — leaving silent
message_count=1 / ended_at=null orphan sessions in the chat sidebar.

The fix:
  1. The read timeout is configurable (JOB_CHAT_ACTION_TIMEOUT_S),
     default 1200s.
  2. On timeout / chat-error, the scheduler closes + annotates the
     orphan session via `_mark_interrupted_session` so it renders as
     an "interrupted" banner instead of a bare seed prompt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.config.config import Settings

# Import via the `usecase.*` path (no `src.` prefix) the runtime uses
# (PYTHONPATH=src). `_mark_interrupted_session` reads the session-store
# singleton via `from usecase.session_store import session_store`, so the
# test MUST wire that same module's global — `src.usecase.session_store`
# is a distinct module object whose singleton the helper never sees.
from usecase.job_scheduler import CroniterJobScheduler
from usecase.session_store import (
    SqliteSessionStore,
    set_session_store,
)


@pytest.fixture
def scheduler(tmp_path: Path) -> CroniterJobScheduler:
    async def _noop_dispatcher(
        tool_name: str, args: dict[str, Any], **_kwargs: Any
    ) -> dict[str, Any]:
        return {"ok": True}

    return CroniterJobScheduler(
        definitions=[], dispatcher=_noop_dispatcher, data_root=tmp_path,
    )


@pytest.fixture
def wired_store(tmp_path: Path):
    """A session store wired as the process singleton, torn down after."""
    store = SqliteSessionStore(data_root=tmp_path / "sessions")
    set_session_store(store)
    try:
        yield store
    finally:
        set_session_store(None)


# ─── Config: timeout is configurable + sanely defaulted ──────────────


def test_job_chat_action_timeout_default() -> None:
    assert Settings().job_chat_action_timeout_s == 1200


def test_job_chat_action_timeout_env_override(monkeypatch) -> None:
    monkeypatch.setenv("JOB_CHAT_ACTION_TIMEOUT_S", "600")
    assert Settings().job_chat_action_timeout_s == 600


# ─── _mark_interrupted_session: close + annotate the orphan ──────────


def test_mark_interrupted_appends_marker_and_ends_session(
    scheduler: CroniterJobScheduler, wired_store: SqliteSessionStore
) -> None:
    sess = wired_store.create_session(title="<skill ...>")
    wired_store.append_message(sess.id, role="user", content="seed prompt")
    assert wired_store.get_session(sess.id).ended_at is None

    scheduler._mark_interrupted_session(
        sess.id, "the chat turn exceeded the 1200s scheduler timeout"
    )

    msgs = wired_store.get_history(sess.id)
    system = [m for m in msgs if m.role == "system"]
    assert len(system) == 1
    assert system[0].meta.get("kind") == "interrupted"
    assert "interrupted" in system[0].content.lower()
    # The session is now closed (ended_at set), not a null-ended orphan.
    assert wired_store.get_session(sess.id).ended_at is not None
    # message_count is now 2 (prompt + marker), not the silent 1.
    assert wired_store.get_session(sess.id).message_count == 2


def test_mark_interrupted_noop_without_session_id(
    scheduler: CroniterJobScheduler, wired_store: SqliteSessionStore
) -> None:
    # None session_id (meta never carried one) must be a silent no-op.
    scheduler._mark_interrupted_session(None, "reason")


def test_mark_interrupted_swallows_unknown_session(
    scheduler: CroniterJobScheduler, wired_store: SqliteSessionStore
) -> None:
    # A session_id that doesn't exist must not raise into the run-record
    # path (append_message raises ValueError; the helper swallows it).
    scheduler._mark_interrupted_session("does-not-exist", "reason")


def test_mark_interrupted_noop_when_store_unwired(
    scheduler: CroniterJobScheduler,
) -> None:
    # No session store wired (singleton is None) → silent no-op.
    set_session_store(None)
    scheduler._mark_interrupted_session("any-id", "reason")
