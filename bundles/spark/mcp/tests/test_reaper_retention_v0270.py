"""v0.2.70 reapers/retention — MEM-F3 (memory TTL) + OBS-F10 (audit.db).

MEM-F3: expired memory rows must not be returned by get/list/search even
between reaper runs (reap-on-read), the reaper deletes them, and the delete
leaves an audit trace.

OBS-F10: audit.db retention is OFF by default; when AUDIT_RETENTION_DAYS is
set, the reaper deletes old rows and records an audit_reaped row.
"""

import sqlite3

from usecase import audit_log as audit_mod
from usecase.audit_log import SqliteAuditLog, set_audit_log
from usecase.memory_store import SqliteMemoryStore, TextHashEmbedder


def _store(tmp_path):
    return SqliteMemoryStore(embedder=TextHashEmbedder(dims=64), data_root=tmp_path)


def _expire(store, key, scope="agent"):
    """Force a stored row to be long-expired by back-dating updated_at."""
    with sqlite3.connect(store._db_path) as c:
        c.execute(
            "UPDATE memories SET updated_at = ?, ttl_seconds = ? "
            "WHERE key = ? AND scope = ?",
            ("2020-01-01T00:00:00Z", 3600, key, scope),
        )


def test_expired_row_hidden_from_get_list_search(tmp_path):
    s = _store(tmp_path)
    s.store(key="ephemeral", value="firewall blocked 1.2.3.4", scope="agent", ttl_seconds=3600)
    s.store(key="durable", value="permanent note about hosts", scope="agent")
    _expire(s, "ephemeral")

    # get → None (reap-on-read)
    assert s.get(key="ephemeral", scope="agent") is None
    # durable still visible
    assert s.get(key="durable", scope="agent") is not None
    # list_all excludes the expired one
    keys = {m.key for m in s.list_all(scope="agent")}
    assert "ephemeral" not in keys and "durable" in keys
    # search excludes the expired one
    hits = s.search("firewall blocked", scope="agent", limit=10)
    assert all(m.key != "ephemeral" for m, _score in hits)


def test_reaper_deletes_and_audits(tmp_path):
    set_audit_log(SqliteAuditLog(data_root=tmp_path))
    s = _store(tmp_path)
    s.store(key="ephemeral", value="x", scope="agent", ttl_seconds=3600)
    _expire(s, "ephemeral")

    deleted = s._reap_expired()
    assert deleted == 1
    # row is gone from the table
    with sqlite3.connect(s._db_path) as c:
        assert c.execute("SELECT COUNT(*) FROM memories WHERE key='ephemeral'").fetchone()[0] == 0
    # audit trace: a memory_deleted row tagged trigger=ttl_reaper, actor=system
    rows = audit_mod.audit_log().query(action=audit_mod.ACTION_MEMORY_DELETED)
    reaped = [r for r in rows if (r.get("metadata") or {}).get("trigger") == "ttl_reaper"]
    assert len(reaped) == 1
    assert reaped[0]["actor"] == "system"
    assert reaped[0]["metadata"]["reaped_count"] == 1


def test_audit_retention_off_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("AUDIT_RETENTION_DAYS", raising=False)
    a = SqliteAuditLog(data_root=tmp_path)
    assert a._retention_days is None
    # an ancient row survives because retention is off
    a.record("settings_changed", target="t", status="success", actor="system")
    with sqlite3.connect(a._db_path) as c:
        c.execute("UPDATE audit_events SET ts = '2020-01-01T00:00:00Z'")
    assert a._reap_old() == 0
    with sqlite3.connect(a._db_path) as c:
        assert c.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 1


def test_resolve_retention_days_env(monkeypatch):
    monkeypatch.setenv("AUDIT_RETENTION_DAYS", "365")
    assert SqliteAuditLog._resolve_retention_days() == 365
    monkeypatch.setenv("AUDIT_RETENTION_DAYS", "0")
    assert SqliteAuditLog._resolve_retention_days() is None
    monkeypatch.setenv("AUDIT_RETENTION_DAYS", "nonsense")
    assert SqliteAuditLog._resolve_retention_days() is None


def test_audit_reaper_deletes_old_and_records(tmp_path):
    a = SqliteAuditLog(data_root=tmp_path, retention_days=30)
    set_audit_log(a)
    a.record("settings_changed", target="old", status="success", actor="system")
    # back-date the one existing row past the 30-day window
    with sqlite3.connect(a._db_path) as c:
        c.execute("UPDATE audit_events SET ts = '2020-01-01T00:00:00Z'")
    n = a._reap_old()
    assert n == 1
    # the audit_reaped row was written (and survives, being newer than cutoff)
    reaped = a.query(action=audit_mod.ACTION_AUDIT_REAPED)
    assert len(reaped) == 1
    assert reaped[0]["actor"] == "system"
    assert reaped[0]["metadata"]["rows_deleted"] == 1
