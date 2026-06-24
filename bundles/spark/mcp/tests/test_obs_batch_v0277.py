"""v0.2.77 audit batch — observability-granularity gaps (B).

Covers the pure-Python sites in this batch:

  * #OBS-F9 — SecretStore.read() now gates the high-frequency SUCCESS
    secret_read audit row behind GUARDIAN_AUDIT_SECRET_READ (default on);
    failed reads + migration re-writes are ALWAYS audited regardless.
  * #SKILL-F13 — a scheduled prompt job whose action.skill body isn't found
    on disk emits a job_skill_skipped audit row (was logger.warning only)
    instead of silently completing status=success with no signal.
  * #OBS-F2 / #XSIAM-F9 — job lifecycle is mirrored into the runtime
    event_log (rt.job.fired / rt.job.completed / rt.job.failed), so the
    /observability/events stream has a job-cadence signal beyond the lone
    rt.tool.failed event.
  * #PLAT-F10 — the plugin install/uninstall audit rows persist the fuller
    output tails on FAILURE (stderr_full/stdout_full = [-1500:]) so a
    forensic investigator sees the same detail the HTTP body returns, and
    the uninstall row now also keeps a stdout tail.
  * manifest — every NEW v0.2.77 action string + rt.job.* event is declared.

The TypeScript sites (SKILL-F2, SUB-F13/F14, XCUT-F2/F15/F20/F22, OBS-F20)
are validated by the tsc gate + live smoke; this file covers the Python sites.

Repo has NO pytest-asyncio — anything async is driven via asyncio.run().
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from usecase import audit_log as audit_mod  # noqa: E402
from usecase import event_log as event_mod  # noqa: E402
from usecase.event_log import SqliteEventLog  # noqa: E402
from usecase.job_scheduler import CroniterJobScheduler  # noqa: E402
from usecase.secret_store import SecretStore  # noqa: E402


# ─────────────────────────────────────────────────────────────────
# shared fixtures
# ─────────────────────────────────────────────────────────────────


def _wire_real_audit(tmp_path, monkeypatch) -> audit_mod.SqliteAuditLog:
    log = audit_mod.SqliteAuditLog(data_root=tmp_path)
    monkeypatch.setattr(audit_mod, "_audit", log)
    return log


def _noop(*a, **k):
    return None


# ─────────────────────────────────────────────────────────────────
# #OBS-F9 — secret_read success row is suppressible; failures always audit
# ─────────────────────────────────────────────────────────────────


def _allow_plaintext(monkeypatch):
    # SecretStore refuses to boot without a KEK unless the plaintext-allow
    # flag is set (same as the existing test_secret_store.py suite).
    monkeypatch.setenv("GUARDIAN_SECRET_KEK_ALLOW_PLAINTEXT", "1")
    monkeypatch.delenv("GUARDIAN_SECRET_KEK", raising=False)


def test_secret_read_success_audited_by_default(tmp_path, monkeypatch):
    _allow_plaintext(monkeypatch)
    monkeypatch.delenv("GUARDIAN_AUDIT_SECRET_READ", raising=False)
    log = _wire_real_audit(tmp_path, monkeypatch)
    s = SecretStore(data_root=tmp_path)
    s.write("/agents/guardian/connectors/abc/api_key", "sk_live_xyz")
    assert s.read("/agents/guardian/connectors/abc/api_key") == "sk_live_xyz"
    reads = log.query(action=audit_mod.ACTION_SECRET_READ)
    assert any(r["status"] == "success" for r in reads), reads


def test_secret_read_success_suppressed_when_disabled(tmp_path, monkeypatch):
    _allow_plaintext(monkeypatch)
    monkeypatch.setenv("GUARDIAN_AUDIT_SECRET_READ", "0")
    log = _wire_real_audit(tmp_path, monkeypatch)
    s = SecretStore(data_root=tmp_path)
    s.write("/agents/guardian/connectors/abc/api_key", "sk_live_xyz")
    assert s.read("/agents/guardian/connectors/abc/api_key") == "sk_live_xyz"
    success_reads = [
        r for r in log.query(action=audit_mod.ACTION_SECRET_READ)
        if r["status"] == "success"
    ]
    assert success_reads == [], "success secret_read should be suppressed"


def test_secret_read_failure_always_audited_even_when_disabled(tmp_path, monkeypatch):
    _allow_plaintext(monkeypatch)
    monkeypatch.setenv("GUARDIAN_AUDIT_SECRET_READ", "false")
    log = _wire_real_audit(tmp_path, monkeypatch)
    s = SecretStore(data_root=tmp_path)
    # reading a missing secret raises but must still leave a failure row.
    try:
        s.read("/agents/guardian/connectors/abc/missing")
    except Exception:
        pass
    failures = [
        r for r in log.query(action=audit_mod.ACTION_SECRET_READ)
        if r["status"] == "failure"
    ]
    assert len(failures) == 1
    assert failures[0]["metadata"]["reason"] == "not_found"


def test_secret_write_still_audited_when_reads_disabled(tmp_path, monkeypatch):
    _allow_plaintext(monkeypatch)
    # The opt-out is read-specific — writes must remain audited.
    monkeypatch.setenv("GUARDIAN_AUDIT_SECRET_READ", "off")
    log = _wire_real_audit(tmp_path, monkeypatch)
    s = SecretStore(data_root=tmp_path)
    s.write("/p1", "v1")
    assert log.query(action=audit_mod.ACTION_SECRET_WRITE), "write must audit"


# ─────────────────────────────────────────────────────────────────
# #SKILL-F13 — missing skill body emits job_skill_skipped
# #OBS-F2 / #XSIAM-F9 — _fire mirrors lifecycle into the runtime event_log
# ─────────────────────────────────────────────────────────────────


def _scheduler_with_chat(tmp_path):
    """A scheduler whose _dispatch_chat is a no-op coroutine, so a prompt
    job's _fire completes without needing the agent HTTP endpoint."""
    sched = CroniterJobScheduler(
        definitions=[], dispatcher=_noop, data_root=tmp_path
    )

    async def _fake_dispatch_chat(*a, **k):
        return {"ok": True, "text": "done"}

    sched._dispatch_chat = _fake_dispatch_chat  # type: ignore[assignment]
    return sched


def test_missing_skill_body_emits_job_skill_skipped(tmp_path, monkeypatch):
    log = _wire_real_audit(tmp_path, monkeypatch)
    sched = _scheduler_with_chat(tmp_path)
    sched.add_job(
        name="j-skill",
        cron="0 * * * *",
        action={"type": "prompt", "message": "hello", "skill": "nope"},
    )
    # Force the skill body to be unresolvable.
    monkeypatch.setattr(sched, "_load_skill_body", lambda name: None)

    row = sched.get_job("j-skill")
    assert row is not None
    run = asyncio.run(sched._fire(row, trigger="cron"))

    # The run still completes (success) — the point of the finding.
    assert run.status == "success"
    skipped = log.query(action="job_skill_skipped")
    assert len(skipped) == 1
    md = skipped[0]["metadata"]
    assert skipped[0]["target"] == "job:j-skill"
    assert skipped[0]["status"] == "failure"
    assert md["skill_name"] == "nope"
    assert md["reason"] == "skill_body_not_found"
    assert skipped[0]["actor"] == "system"


def test_present_skill_body_does_not_emit_skipped(tmp_path, monkeypatch):
    log = _wire_real_audit(tmp_path, monkeypatch)
    sched = _scheduler_with_chat(tmp_path)
    sched.add_job(
        name="j-ok",
        cron="0 * * * *",
        action={"type": "prompt", "message": "hi", "skill": "real"},
    )
    monkeypatch.setattr(sched, "_load_skill_body", lambda name: "BODY")
    # frontmatter parse isn't needed for the skip path; stub to empty.
    monkeypatch.setattr(sched, "_parse_skill_frontmatter", lambda name: {})

    row = sched.get_job("j-ok")
    asyncio.run(sched._fire(row, trigger="cron"))
    assert log.query(action="job_skill_skipped") == []


def test_fire_emits_rt_job_runtime_events(tmp_path, monkeypatch):
    # Wire a real event_log declaring the rt.job.* events.
    el = SqliteEventLog(
        declared_events=["rt.job.fired", "rt.job.completed", "rt.job.failed"],
        data_root=tmp_path,
    )
    monkeypatch.setattr(event_mod, "_event_log", el)
    # Audit singleton too (record_event is invoked unconditionally in _fire).
    _wire_real_audit(tmp_path, monkeypatch)

    sched = _scheduler_with_chat(tmp_path)
    sched.add_job(
        name="j-ev", cron="0 * * * *",
        action={"type": "prompt", "message": "hi"},
    )
    row = sched.get_job("j-ev")
    asyncio.run(sched._fire(row, trigger="cron"))

    fired = el.query(event_name="rt.job.fired")
    completed = el.query(event_name="rt.job.completed")
    assert len(fired) == 1, "expected exactly one rt.job.fired"
    assert len(completed) == 1, "expected exactly one rt.job.completed"
    assert fired[0].payload["job"] == "j-ev"
    assert completed[0].payload["job"] == "j-ev"
    assert completed[0].payload["status"] == "success"
    assert el.query(event_name="rt.job.failed") == []


def test_fire_emits_rt_job_failed_on_failure(tmp_path, monkeypatch):
    el = SqliteEventLog(
        declared_events=["rt.job.fired", "rt.job.completed", "rt.job.failed"],
        data_root=tmp_path,
    )
    monkeypatch.setattr(event_mod, "_event_log", el)
    _wire_real_audit(tmp_path, monkeypatch)

    sched = CroniterJobScheduler(
        definitions=[], dispatcher=_noop, data_root=tmp_path
    )

    async def _boom(*a, **k):
        raise RuntimeError("dispatch blew up")

    sched._dispatch_chat = _boom  # type: ignore[assignment]
    sched.add_job(
        name="j-fail", cron="0 * * * *",
        action={"type": "prompt", "message": "hi"},
    )
    row = sched.get_job("j-fail")
    run = asyncio.run(sched._fire(row, trigger="cron"))
    assert run.status == "failure"
    failed = el.query(event_name="rt.job.failed")
    assert len(failed) == 1
    assert failed[0].payload["status"] == "failure"
    assert el.query(event_name="rt.job.completed") == []


# ─────────────────────────────────────────────────────────────────
# #PLAT-F10 — install/uninstall persist fuller output tails on failure
# ─────────────────────────────────────────────────────────────────


def test_plugin_routes_persist_full_tails_on_failure():
    p = SRC / "api" / "plugin_entry_points_routes.py"
    text = p.read_text()
    # install: the existing short keys stay (v0.2.76 OBS-F16 contract), and the
    # fuller failure-only tails are added.
    assert '"stdout_tail": out[-500:]' in text
    assert '_install_md["stderr_full"] = err[-1500:]' in text
    assert '_install_md["stdout_full"] = out[-1500:]' in text
    # uninstall: now keeps a stdout tail + the fuller failure tails.
    assert '_uninstall_md["stderr_full"] = err[-1500:]' in text
    assert '_uninstall_md["stdout_full"] = out[-1500:]' in text


# ─────────────────────────────────────────────────────────────────
# manifest — every NEW v0.2.77 action + rt.job event is declared
# ─────────────────────────────────────────────────────────────────


def test_new_actions_declared_in_manifest():
    import yaml

    manifest_path = Path(__file__).resolve().parents[2] / "manifest.yaml"
    parsed = yaml.safe_load(manifest_path.read_text())
    events = set(parsed["audit"]["events"])
    for value in (
        "job_skill_skipped",            # #SKILL-F13
        "skills_unavailable",           # #SKILL-F2
        "chat_subagent_task_uncreated", # #SUB-F13
        "proxy_request_failed",         # #XCUT-F2
        "chat_turn_finish_reason",      # #XCUT-F20
    ):
        assert value in events, f"{value!r} missing from manifest audit.events"


def test_new_runtime_events_declared_in_manifest():
    import yaml

    manifest_path = Path(__file__).resolve().parents[2] / "manifest.yaml"
    parsed = yaml.safe_load(manifest_path.read_text())
    obs_events = set(parsed["observability"]["events"])
    for value in ("rt.job.fired", "rt.job.completed", "rt.job.failed"):
        assert value in obs_events, f"{value!r} missing from observability.events"
