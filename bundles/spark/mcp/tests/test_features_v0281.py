"""v0.2.81 feature batch — backend logic for the three #84 features.

Covers the pure-Python pieces (the TS wiring is validated by the
tsc/lint/build gate + live smoke):

  HOOK-F15 — hook `created_by` origin column + DELETE/PATCH guard.
             * migration idempotency (re-init a pre-column DB)
             * origin populated at create; immutable on update
             * is_operator_owned() classification
             * delete-guard: operator-owned + legacy-NULL deletable,
               plugin/builtin/seed → blocked

  XSIAM-F13 — audit `chain_id` correlation column + contextvar.
             * migration idempotency (re-init a pre-column DB)
             * contextvar → audit-row chain_id propagation
             * explicit chain_id arg overrides the contextvar
             * query/count filter by chain_id

(HOOK-F14's SecretStore-backed `secret:` resolution is an agent-side
TS path + a thin MCP route; the route is exercised by live smoke and
the helper logic by tsc. The Python side is just SecretStore.read,
already covered by the secret_store tests.)
"""

from __future__ import annotations

import sqlite3

import pytest

from usecase.hook_store import SqliteHookStore, Hook
from usecase.audit_log import (
    SqliteAuditLog,
    set_current_chain_id,
    reset_current_chain_id,
    get_current_chain_id,
)


# ─────────────────────────────────────────────────────────────────────
# HOOK-F15 — hook created_by origin column + guard
# ─────────────────────────────────────────────────────────────────────


def _base_hook(hook_id: str = "h1", **overrides) -> dict:
    payload = {
        "id": hook_id,
        "name": "test-hook",
        "event": "PreToolUse",
        "transport": {"type": "http", "url": "https://example.com/hook"},
    }
    payload.update(overrides)
    return payload


def test_hookf15_migration_idempotent_on_legacy_db(tmp_path):
    """A hooks.db created WITHOUT the created_by column gets the column
    added on re-init, idempotently, and the legacy row survives with
    created_by=NULL."""
    db = tmp_path / "hooks.db"
    # Simulate a pre-migration schema (no created_by column).
    c = sqlite3.connect(db)
    c.execute(
        """
        CREATE TABLE hooks (
            id           TEXT PRIMARY KEY,
            event        TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            enabled      INTEGER NOT NULL DEFAULT 1,
            priority     INTEGER NOT NULL DEFAULT 100,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        )
        """
    )
    c.execute(
        "INSERT INTO hooks (id, event, payload_json, enabled, priority, "
        "created_at, updated_at) VALUES "
        "('legacy', 'PreToolUse', '{}', 1, 100, 'T', 'T')"
    )
    c.commit()
    c.close()

    # First init runs the migration.
    store = SqliteHookStore(data_root=tmp_path)
    cols = _columns(db, "hooks")
    assert "created_by" in cols
    legacy = store.get("legacy")
    assert legacy is not None
    assert legacy.created_by is None  # existing row → NULL

    # Second init is a no-op (idempotent — no duplicate-column error).
    SqliteHookStore(data_root=tmp_path)
    assert "created_by" in _columns(db, "hooks")


def test_hookf15_created_by_set_on_insert_immutable_on_update(tmp_path):
    store = SqliteHookStore(data_root=tmp_path)
    created = store.upsert(_base_hook(), created_by="user:operator")
    assert created.created_by == "user:operator"

    # Updating the SAME hook with a different created_by must NOT relabel
    # the origin (origin is immutable after insert).
    updated = store.upsert(
        _base_hook(name="renamed"), created_by="plugin:evil"
    )
    assert updated.created_by == "user:operator"
    assert store.get("h1").created_by == "user:operator"


def test_hookf15_created_by_none_for_loaderless_insert(tmp_path):
    store = SqliteHookStore(data_root=tmp_path)
    created = store.upsert(_base_hook())  # no created_by passed
    assert created.created_by is None
    assert store.get("h1").created_by is None


def test_hookf15_plugin_origin_persists(tmp_path):
    store = SqliteHookStore(data_root=tmp_path)
    created = store.upsert(_base_hook(), created_by="plugin:acme")
    assert created.created_by == "plugin:acme"
    assert store.get("h1").created_by == "plugin:acme"


@pytest.mark.parametrize(
    "created_by,expected",
    [
        (None, True),          # legacy NULL → operator-owned/deletable
        ("operator", True),
        ("user:operator", True),
        ("apikey:abc123", True),
        ("plugin:acme", False),
        ("builtin", False),
        ("seed:soc-baseline", False),
        ("", True),            # empty string treated as legacy
    ],
)
def test_hookf15_is_operator_owned_classification(created_by, expected):
    h = Hook(
        id="x",
        event="PreToolUse",
        payload={},
        enabled=True,
        priority=100,
        created_at="T",
        updated_at="T",
        created_by=created_by,
    )
    assert h.is_operator_owned() is expected


def test_hookf15_to_dict_surfaces_created_by(tmp_path):
    store = SqliteHookStore(data_root=tmp_path)
    created = store.upsert(_base_hook(), created_by="plugin:acme")
    assert created.to_dict()["createdBy"] == "plugin:acme"


def test_hookf15_delete_guard_via_store_and_classifier(tmp_path):
    """The store.delete is unconditional (it's the API layer that guards),
    but the classifier the API guard relies on must correctly gate:
    operator/legacy deletable, plugin/builtin/seed protected."""
    store = SqliteHookStore(data_root=tmp_path)
    op = store.upsert(_base_hook("op"), created_by="user:operator")
    legacy = store.upsert(_base_hook("legacy"))  # NULL origin
    plug = store.upsert(_base_hook("plug"), created_by="plugin:acme")

    # The guard predicate the DELETE handler uses.
    assert op.is_operator_owned() is True
    assert legacy.is_operator_owned() is True
    assert plug.is_operator_owned() is False

    # Operator-owned + legacy delete OK at the store layer.
    assert store.delete("op") is True
    assert store.delete("legacy") is True
    # Protected hook would be blocked at the API layer BEFORE reaching
    # store.delete; the store itself still removes if called.
    assert store.get("plug") is not None


# ─────────────────────────────────────────────────────────────────────
# XSIAM-F13 — audit chain_id correlation column + contextvar
# ─────────────────────────────────────────────────────────────────────


def test_xsiamf13_migration_idempotent_on_legacy_db(tmp_path):
    """An audit.db with the trigger col but NO chain_id col gets chain_id
    added on re-init, idempotently; legacy rows survive."""
    db = tmp_path / "audit.db"
    c = sqlite3.connect(db)
    c.execute(
        """
        CREATE TABLE audit_events (
            id            TEXT PRIMARY KEY,
            ts            TEXT NOT NULL,
            actor         TEXT,
            action        TEXT NOT NULL,
            target        TEXT,
            status        TEXT,
            duration_ms   INTEGER,
            metadata_json TEXT NOT NULL,
            trigger       TEXT
        )
        """
    )
    c.execute(
        "INSERT INTO audit_events (id, ts, action, metadata_json) "
        "VALUES ('old', '2020-01-01T00:00:00.000000Z', 'tool_call', '{}')"
    )
    c.commit()
    c.close()

    log = SqliteAuditLog(data_root=tmp_path)
    cols = _columns(db, "audit_events")
    assert "chain_id" in cols
    rows = log.query(action="tool_call")
    assert any(r["id"] == "old" and r["chain_id"] is None for r in rows)

    # Idempotent re-init.
    SqliteAuditLog(data_root=tmp_path)
    assert "chain_id" in _columns(db, "audit_events")


def test_xsiamf13_contextvar_propagates_to_row(tmp_path):
    log = SqliteAuditLog(data_root=tmp_path)
    token = set_current_chain_id("ch_turn1")
    try:
        log.record("tool_call", target="tool:a", status="success")
        log.record("tool_call", target="tool:b", status="success")
    finally:
        reset_current_chain_id(token)
    # Both rows of the turn share the chain_id.
    rows = log.query(chain_id="ch_turn1")
    assert len(rows) == 2
    assert {r["target"] for r in rows} == {"tool:a", "tool:b"}
    assert all(r["chain_id"] == "ch_turn1" for r in rows)


def test_xsiamf13_no_contextvar_means_null(tmp_path):
    log = SqliteAuditLog(data_root=tmp_path)
    # Ensure no ambient chain id.
    assert get_current_chain_id() is None
    log.record("tool_call", target="tool:x", status="success")
    rows = log.query(action="tool_call")
    assert len(rows) == 1
    assert rows[0]["chain_id"] is None


def test_xsiamf13_explicit_arg_overrides_contextvar(tmp_path):
    log = SqliteAuditLog(data_root=tmp_path)
    token = set_current_chain_id("ch_ctx")
    try:
        log.record(
            "tool_call", target="t", status="success", chain_id="ch_explicit"
        )
    finally:
        reset_current_chain_id(token)
    rows = log.query(chain_id="ch_explicit")
    assert len(rows) == 1
    assert log.query(chain_id="ch_ctx") == []


def test_xsiamf13_query_and_count_filter_by_chain(tmp_path):
    log = SqliteAuditLog(data_root=tmp_path)
    log.record("tool_call", target="a", status="success", chain_id="ch_A")
    log.record("tool_call", target="b", status="success", chain_id="ch_A")
    log.record("tool_call", target="c", status="success", chain_id="ch_B")
    assert log.count(chain_id="ch_A") == 2
    assert log.count(chain_id="ch_B") == 1
    assert len(log.query(chain_id="ch_A")) == 2


# ─────────────────────────────────────────────────────────────────────
# XSIAM-F13 — middleware: X-Guardian-Chain-Id header → contextvar
# (mirrors test_trigger_actor.py; needs starlette — CI-only)
# ─────────────────────────────────────────────────────────────────────

try:
    from starlette.applications import Starlette
    from starlette.responses import JSONResponse as _JSONResponse
    from starlette.routing import Route
    from starlette.testclient import TestClient

    from api.trigger_context import TriggerContextMiddleware

    _HAVE_STARLETTE = True
except ImportError:  # pragma: no cover - CI has starlette
    _HAVE_STARLETTE = False

starlette_only = pytest.mark.skipif(
    not _HAVE_STARLETTE, reason="starlette not installed (CI-only)"
)


@starlette_only
def test_xsiamf13_chain_header_sets_contextvar():
    async def _chain(request):
        return _JSONResponse({"chain_id": get_current_chain_id()})

    app = Starlette(routes=[Route("/chain", _chain)])
    app.add_middleware(TriggerContextMiddleware)
    client = TestClient(app)

    r = client.get("/chain", headers={"X-Guardian-Chain-Id": "ch_turn42"})
    assert r.status_code == 200
    assert r.json()["chain_id"] == "ch_turn42"

    # Absent header → no chain id.
    r2 = client.get("/chain")
    assert r2.json()["chain_id"] is None

    # Reset after request (no cross-request leak).
    assert get_current_chain_id() is None


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _columns(db_path, table) -> set[str]:
    c = sqlite3.connect(db_path)
    try:
        return {r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}
    finally:
        c.close()
