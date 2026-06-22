"""#77 — update_job emits a `job_updated` audit event.

Before this fix update_job wrote NOTHING to the audit log, so changing a
job's cron/action/model_id/permission_policy — and crucially toggling
bypass_approvals=true (arming unattended auto-approval of every gated
tool) — left no trace. (set_enabled / add_job / delete_job already audit.)
"""

from pathlib import Path

import pytest

from usecase import audit_log as audit_mod
from usecase.job_scheduler import CroniterJobScheduler


def _noop(*a, **k):
    return None


@pytest.fixture
def scheduler(tmp_path: Path) -> CroniterJobScheduler:
    return CroniterJobScheduler(definitions=[], dispatcher=_noop, data_root=tmp_path)


def test_update_job_emits_audit(scheduler, monkeypatch):
    scheduler.add_job(name="j", cron="0 * * * *",
                      action={"type": "prompt", "message": "hi"})
    calls = []
    monkeypatch.setattr(audit_mod, "record_event",
                        lambda action, **kw: calls.append((action, kw)))

    scheduler.update_job("j", bypass_approvals=True)

    updated = [kw for a, kw in calls if a == audit_mod.ACTION_JOB_UPDATED]
    assert len(updated) == 1
    assert updated[0]["target"] == "job:j"
    assert updated[0]["status"] == "success"
    assert "bypass_approvals" in updated[0]["metadata"]["changed_fields"]
    assert updated[0]["metadata"]["job_name"] == "j"


def test_update_job_records_all_changed_fields(scheduler, monkeypatch):
    scheduler.add_job(name="j2", cron="0 * * * *",
                      action={"type": "prompt", "message": "hi"})
    calls = []
    monkeypatch.setattr(audit_mod, "record_event",
                        lambda action, **kw: calls.append((action, kw)))

    scheduler.update_job("j2", cron="*/5 * * * *",
                         action={"type": "prompt", "message": "bye"})

    updated = [kw for a, kw in calls if a == audit_mod.ACTION_JOB_UPDATED][0]
    assert set(updated["metadata"]["changed_fields"]) == {"cron", "action"}


def test_update_missing_job_no_audit(scheduler, monkeypatch):
    calls = []
    monkeypatch.setattr(audit_mod, "record_event",
                        lambda action, **kw: calls.append((action, kw)))
    assert scheduler.update_job("nope", cron="0 0 * * *") is None
    assert not any(a == audit_mod.ACTION_JOB_UPDATED for a, _ in calls)
