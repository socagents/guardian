"""v0.17.126 — scheduler failure back-off (#121).

Surfaced by the v0.17.124 chat smoke: the leftover test job `x`
(cron "* * * * *") 401'd on /api/chat ~24,000 times because the only
auto-disable path keyed on "references unknown tool" — a 401 sailed
right past it and the job re-fired every minute forever.

`_trailing_failure_count` underpins the new back-off: once a non-run_once
job crosses MAX_CONSECUTIVE_FAILURES consecutive failures, the runner
disables it. These tests anchor the counter's semantics (the disable
wiring + the /api/chat MCP_TOKEN bearer are verified by the deployed
smoke, which fires a one-shot prompt job and asserts a 200 not a 401).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from src.usecase.job_scheduler import (
    CroniterJobScheduler,
    MAX_CONSECUTIVE_FAILURES,
)


@pytest.fixture
def scheduler(tmp_path: Path) -> CroniterJobScheduler:
    async def _noop(tool_name: str, args: dict[str, Any], **_k: Any) -> dict[str, Any]:
        return {"ok": True}

    return CroniterJobScheduler(
        definitions=[], dispatcher=_noop, data_root=tmp_path,
    )


def _insert_run(
    db: str, job_name: str, run_id: str, status: str, fired_at: str
) -> None:
    with sqlite3.connect(db) as c:
        c.execute(
            "INSERT INTO job_runs (id, job_name, fired_at, status, trigger) "
            "VALUES (?, ?, ?, ?, 'cron')",
            (run_id, job_name, fired_at, status),
        )


def test_counts_consecutive_trailing_failures(scheduler: CroniterJobScheduler) -> None:
    db = scheduler.db_path
    _insert_run(db, "j", "r1", "failure", "2026-01-01T00:01:00Z")
    _insert_run(db, "j", "r2", "failure", "2026-01-01T00:02:00Z")
    _insert_run(db, "j", "r3", "failure", "2026-01-01T00:03:00Z")
    # The in-flight run is still 'pending' and must be excluded.
    _insert_run(db, "j", "cur", "pending", "2026-01-01T00:04:00Z")
    assert scheduler._trailing_failure_count("j", "cur") == 3


def test_streak_breaks_at_a_success(scheduler: CroniterJobScheduler) -> None:
    db = scheduler.db_path
    _insert_run(db, "j", "r1", "failure", "2026-01-01T00:01:00Z")
    _insert_run(db, "j", "r2", "success", "2026-01-01T00:02:00Z")  # breaks streak
    _insert_run(db, "j", "r3", "failure", "2026-01-01T00:03:00Z")
    _insert_run(db, "j", "cur", "pending", "2026-01-01T00:04:00Z")
    # Only the single trailing failure (r3) counts; the success stops it.
    assert scheduler._trailing_failure_count("j", "cur") == 1


def test_count_is_isolated_per_job(scheduler: CroniterJobScheduler) -> None:
    db = scheduler.db_path
    _insert_run(db, "a", "a1", "failure", "2026-01-01T00:01:00Z")
    _insert_run(db, "b", "b1", "success", "2026-01-01T00:01:30Z")
    _insert_run(db, "a", "a2", "failure", "2026-01-01T00:02:00Z")
    assert scheduler._trailing_failure_count("a", "none") == 2
    assert scheduler._trailing_failure_count("b", "none") == 0


def test_no_runs_is_zero(scheduler: CroniterJobScheduler) -> None:
    assert scheduler._trailing_failure_count("never-ran", "none") == 0


def test_threshold_is_sane() -> None:
    # A per-minute job hits the cap fast; a daily job tolerates a blip.
    assert 2 <= MAX_CONSECUTIVE_FAILURES <= 100
