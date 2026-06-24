"""SqliteHookStore — operator-registered lifecycle hooks.

Round-15 / Phase H. Hooks let an operator (or admin) attach
policy / notifications / context-injection to chat lifecycle events
(PreToolUse, PostToolUse, UserPromptSubmit, PreCompact, PostCompact,
RunStart, RunEnd, PostToolUseFailure) without modifying tool code.

Why a dedicated store (vs. SettingsStore):

  - A hook is a structured object: id, event, transport spec,
    matcher, timeout, failure policy, enabled bit, audit timestamps.
    SettingsStore is key-typed scalars; flattening hook fields into
    `hook.<id>.<field>` keys would balloon `overridable[]` and lose
    the validator's transport-shape checks.
  - Hooks are queried by EVENT — the chat-route fires every event
    site and asks "what hooks are registered for PreToolUse?" An
    indexed table on `event` is O(1); the settings store is
    key-string-prefix scan.
  - Multi-row by design (one row per hook). PersonalityStore is
    single-row (one persona); the shapes differ.

# Schema

    hooks (
      id            TEXT PRIMARY KEY,    -- uuid
      event         TEXT NOT NULL,       -- 'PreToolUse' | etc.
      payload_json  TEXT NOT NULL,       -- the full Hook record as
                                         -- the agent sees it (transport,
                                         -- matcher, timeout, etc.)
      enabled       INTEGER NOT NULL DEFAULT 1,
      priority      INTEGER NOT NULL DEFAULT 100,
      created_at    TEXT NOT NULL,
      updated_at    TEXT NOT NULL,
      created_by    TEXT                 -- #HOOK-F15 — creation origin:
                                         --   "operator" / "apikey:<id>" /
                                         --   "user:operator" via the REST path,
                                         --   "plugin:<name>" / "builtin" /
                                         --   "seed:<name>" via a loader.
                                         -- NULL = legacy row (pre-migration),
                                         -- treated as operator-owned/deletable.
    );
    CREATE INDEX idx_hooks_event   ON hooks(event);
    CREATE INDEX idx_hooks_enabled ON hooks(enabled);

# Why a JSON blob in `payload_json`

The full Hook record is the contract between the agent and the
operator-facing UI. Storing the canonical shape as a single JSON
column means:
  - Agent UI write/read paths stay simple (PUT /api/v1/hooks/{id}
    with the Hook body, GET returns the same shape).
  - Adding fields to the Hook contract (e.g. tenant matcher in
    Phase X) doesn't require schema migrations — only the agent-
    side validator needs to learn the new field.
  - Indexes still work on `event` + `enabled` because those are
    duplicated as columns for query planner friendliness.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("Guardian MCP")

DEFAULT_DATA_ROOT = Path("/app/data")


@dataclass
class Hook:
    """One registered hook. Matches the agent-side `Hook` interface
    in `mcp/agent/lib/hooks.ts` field-for-field; the agent passes
    the full payload through and we round-trip it as a single
    `payload_json` column."""

    id: str
    event: str
    payload: dict[str, Any]
    enabled: bool
    priority: int
    created_at: str
    updated_at: str
    # #HOOK-F15 — creation origin. None for legacy rows (pre-migration),
    # treated as operator-owned/deletable by the DELETE guard.
    created_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        # Return the full agent-shape payload (not the row shape).
        # The agent UI reads from / writes to this dict directly.
        return {
            **self.payload,
            "id": self.id,
            "event": self.event,
            "enabled": self.enabled,
            "priority": self.priority,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            # #HOOK-F15 — surface the origin so the /settings/hooks UI can
            # badge plugin/builtin/seed hooks as non-deletable. None = legacy.
            "createdBy": self.created_by,
        }

    def is_operator_owned(self) -> bool:
        """#HOOK-F15 — True iff this hook may be deleted/edited by an
        operator. A hook is operator-owned when its origin is NULL
        (legacy row, pre-migration) or starts with an operator actor
        prefix ("operator", "user:", "apikey:"). Anything else
        (plugin:<name> / builtin / seed:<name>) is owned by its source
        and must NOT be deletable via the REST/UI path — the loader
        would re-create it on the next reload anyway, so deleting it
        is spec-violating and silently lost.
        """
        cb = (self.created_by or "").strip()
        if not cb:
            # Legacy/NULL — pre-migration rows are operator-owned so we
            # never lock operators out of hooks they created before the
            # origin column existed.
            return True
        return (
            cb == "operator"
            or cb.startswith("user:")
            or cb.startswith("apikey:")
        )


class SqliteHookStore:
    """Append-modify hook store backed by sqlite. Thread-safe via a
    single lock around writes; reads are point-in-time consistent
    via the underlying sqlite WAL."""

    def __init__(self, data_root: Path | None = None) -> None:
        root = data_root or self._resolve_data_root()
        root.mkdir(parents=True, exist_ok=True)
        self._db_path = root / "hooks.db"
        self._lock = threading.Lock()
        self._init_schema()

    @staticmethod
    def _resolve_data_root() -> Path:
        from os import environ

        return Path(environ.get("GUARDIAN_DATA_ROOT", str(DEFAULT_DATA_ROOT)))

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._db_path, isolation_level=None)
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def _init_schema(self) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS hooks (
                    id           TEXT PRIMARY KEY,
                    event        TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    enabled      INTEGER NOT NULL DEFAULT 1,
                    priority     INTEGER NOT NULL DEFAULT 100,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    created_by   TEXT
                )
                """
            )
            # #HOOK-F15 — backward-compatible migration for hooks.db's that
            # predate the `created_by` origin column. SQLite has no
            # `ADD COLUMN IF NOT EXISTS`, so probe PRAGMA table_info first;
            # idempotent — re-running is a no-op. Existing rows get NULL,
            # which the DELETE guard treats as legacy/operator-owned
            # (deletable) so we never lock operators out of their own hooks.
            # Mirrors the pattern in audit_log.py (trigger col) and
            # job_scheduler.py (source col).
            cols = {
                r[1]
                for r in c.execute("PRAGMA table_info(hooks)").fetchall()
            }
            if "created_by" not in cols:
                c.execute("ALTER TABLE hooks ADD COLUMN created_by TEXT")
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_hooks_event "
                "ON hooks(event)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_hooks_enabled "
                "ON hooks(enabled)"
            )

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # ─── Public API ─────────────────────────────────────────────

    def list(
        self,
        *,
        event: str | None = None,
        enabled_only: bool = False,
    ) -> list[Hook]:
        """List hooks, optionally filtered by event + enabled bit.
        Returns priority-ascending (low priority runs first)."""
        sql = "SELECT id, event, payload_json, enabled, priority, " \
              "created_at, updated_at, created_by FROM hooks"
        clauses: list[str] = []
        params: list[Any] = []
        if event is not None:
            clauses.append("event = ?")
            params.append(event)
        if enabled_only:
            clauses.append("enabled = 1")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY priority ASC, id ASC"
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
        return [self._row_to_hook(r) for r in rows]

    def get(self, hook_id: str) -> Hook | None:
        with self._conn() as c:
            r = c.execute(
                "SELECT id, event, payload_json, enabled, priority, "
                "created_at, updated_at, created_by FROM hooks WHERE id = ?",
                (hook_id,),
            ).fetchone()
        if r is None:
            return None
        return self._row_to_hook(r)

    def upsert(
        self, payload: dict[str, Any], *, created_by: str | None = None
    ) -> Hook:
        """Insert or update a hook. Caller MUST have validated the
        shape on the agent side (lib/hooks.ts:validateHook). We do
        a minimal set of MCP-side checks (id present, event known)
        but trust the structured fields are well-formed.

        #HOOK-F15 — `created_by` records the creation origin. It is
        applied ONLY on insert; on update of an existing row the
        stored origin is preserved (origin is immutable — an operator
        editing a hook can't relabel its provenance, and a plugin
        re-registering its own hook on reload keeps its origin). The
        REST create handler passes the actor (operator id / api key);
        a plugin/seed loader passes its own origin like
        "plugin:<name>" or "seed:<name>". None falls through to NULL
        (legacy / treated as operator-owned by the DELETE guard).
        """
        hook_id = str(payload.get("id") or "").strip()
        event = str(payload.get("event") or "").strip()
        if not hook_id:
            raise ValueError("hook payload missing 'id'")
        if not event:
            raise ValueError("hook payload missing 'event'")
        priority = int(payload.get("priority") or 100)
        enabled = bool(payload.get("enabled", True))
        now = self._now()
        existing = self.get(hook_id)
        created_at = (
            existing.created_at if existing else
            str(payload.get("createdAt") or now)
        )
        # Origin is set once, at insert. Updating an existing row keeps
        # its stored origin regardless of what the caller passes.
        effective_created_by = (
            existing.created_by if existing else created_by
        )
        # Normalize the stored payload — strip top-level metadata
        # we'll re-derive at read time so the JSON blob is a clean
        # snapshot (no stale createdAt / updatedAt).
        stored = {
            k: v for k, v in payload.items()
            if k not in {"id", "event", "enabled", "priority",
                         "createdAt", "updatedAt"}
        }
        with self._lock, self._conn() as c:
            # #HOOK-F15 — created_by is deliberately omitted from the
            # ON CONFLICT UPDATE set: origin is immutable after insert.
            c.execute(
                "INSERT INTO hooks (id, event, payload_json, enabled, "
                "priority, created_at, updated_at, created_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "event=excluded.event, "
                "payload_json=excluded.payload_json, "
                "enabled=excluded.enabled, "
                "priority=excluded.priority, "
                "updated_at=excluded.updated_at",
                (
                    hook_id, event, json.dumps(stored),
                    1 if enabled else 0, priority,
                    created_at, now, effective_created_by,
                ),
            )
        return Hook(
            id=hook_id,
            event=event,
            payload=stored,
            enabled=enabled,
            priority=priority,
            created_at=created_at,
            updated_at=now,
            created_by=effective_created_by,
        )

    def delete(self, hook_id: str) -> bool:
        """Delete a hook. Returns True when a row was removed."""
        with self._lock, self._conn() as c:
            cur = c.execute("DELETE FROM hooks WHERE id = ?", (hook_id,))
            return cur.rowcount > 0

    def set_enabled(self, hook_id: str, enabled: bool) -> Hook | None:
        """Toggle enabled bit without rewriting the payload."""
        with self._lock, self._conn() as c:
            cur = c.execute(
                "UPDATE hooks SET enabled = ?, updated_at = ? "
                "WHERE id = ?",
                (1 if enabled else 0, self._now(), hook_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get(hook_id)

    @staticmethod
    def _row_to_hook(row: tuple[Any, ...]) -> Hook:
        (id_, event, payload_json, enabled, priority,
         created_at, updated_at, created_by) = row
        try:
            payload = json.loads(payload_json) if payload_json else {}
        except json.JSONDecodeError:
            logger.warning(
                "hook_store: hook %s has malformed payload_json; "
                "treating as empty", id_,
            )
            payload = {}
        return Hook(
            id=id_,
            event=event,
            payload=payload,
            enabled=bool(enabled),
            priority=int(priority),
            created_at=created_at,
            updated_at=updated_at,
            created_by=created_by,
        )
