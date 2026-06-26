"""Playbook-build store — sqlite-backed history of agent-drafted XSOAR
playbooks over ``<data_root>/playbook_builds.db``.

Guardian's own record of the playbooks the agent authored for an operator:
each row captures one "build" — the operator's use-case prompt, the drafted
YAML, its validation result, and (once deployed + test-run against XSOAR) a
deploy summary + the test incident id. A build moves through a small
status lifecycle: ``drafted → validated → deployed → tested`` (or ``failed``
at any step). The store is the durable backing for the playbook-builder UI +
the autonomous "draft → validate → deploy → test-run" loop.

State taxonomy (root CLAUDE.md): the catalog domain — NOT credentials, NOT
operator-personal. Mutable build metadata the agent reads/writes and the UI
displays. The drafted YAML + validation/deploy detail carry no secret
material (the XSOAR creds live in the connector instance's SecretStore), so
the playbook_build_* surface is agent-accessible (catalog side of the
credential guardrail).

Schema:
    playbook_builds(
      id, use_case, product, playbook_name, playbook_yaml, status,
      validation_json, deploy_summary, test_incident_id, session_id,
      created_by, created_at, updated_at
    )

Mirrors investigation_store.py (threading.Lock + sqlite3 isolation_level=None
+ foreign_keys=ON, frozen DTO, module-level singleton accessor, best-effort
audit on mutation).
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("Guardian MCP")

DEFAULT_DATA_ROOT = Path("/app/data")

# Allowed status values — kept liberal (the store persists whatever string the
# caller sets) but the lifecycle is documented for the agent + UI. The
# API/tool layer can validate; the store just persists strings.
BUILD_STATUSES = ("drafted", "validated", "deployed", "tested", "failed")

# Columns update_build accepts a partial of. id/created_at/created_by are
# immutable (set once at create); updated_at is bumped automatically. Unknown
# keys are ignored (mirrors investigation_store.update_issue's allow-list).
_BUILD_UPDATABLE = (
    "use_case", "product", "playbook_name", "playbook_yaml", "status",
    "validation_json", "deploy_summary", "test_incident_id", "session_id",
)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass(frozen=True)
class PlaybookBuild:
    id: str
    use_case: str
    product: str | None
    playbook_name: str | None
    playbook_yaml: str | None
    status: str
    validation_json: str | None
    deploy_summary: str | None
    test_incident_id: str | None
    session_id: str | None
    created_by: str
    created_at: str
    updated_at: str


class PlaybookBuildStore:
    """Sqlite-backed store at ``<data_root>/playbook_builds.db``."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else self._resolve_db_path()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()
        logger.info("PlaybookBuildStore at %s", self._db_path)

    @staticmethod
    def _resolve_db_path() -> Path:
        data_root = Path(os.getenv("DATA_ROOT", str(DEFAULT_DATA_ROOT)))
        return data_root / "playbook_builds.db"

    @property
    def db_path(self) -> Path:
        return self._db_path

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._db_path, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        return c

    def _init_schema(self) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS playbook_builds (
                    id                TEXT PRIMARY KEY,
                    use_case          TEXT NOT NULL,
                    product           TEXT,
                    playbook_name     TEXT,
                    playbook_yaml     TEXT,
                    status            TEXT NOT NULL DEFAULT 'drafted',
                    validation_json   TEXT,
                    deploy_summary    TEXT,
                    test_incident_id  TEXT,
                    session_id        TEXT,
                    created_by        TEXT NOT NULL DEFAULT 'agent',
                    created_at        TEXT NOT NULL,
                    updated_at        TEXT NOT NULL
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_pbbuild_status ON playbook_builds(status)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_pbbuild_session ON playbook_builds(session_id)")
            # Additive migrations for dbs that predate a column. Same
            # PRAGMA-probe + ADD COLUMN idiom investigation_store uses; each
            # guard is idempotent (re-running is a no-op). New columns land
            # here so existing playbook_builds.db files pick them up at boot.
            cols = {r["name"] for r in c.execute("PRAGMA table_info(playbook_builds)")}
            for col in ("product", "playbook_name", "playbook_yaml", "validation_json",
                        "deploy_summary", "test_incident_id", "session_id"):
                if col not in cols:
                    c.execute(f"ALTER TABLE playbook_builds ADD COLUMN {col} TEXT")

    # ─── Builds ────────────────────────────────────────────────────

    def create_build(
        self,
        *,
        use_case: str,
        product: str | None = None,
        playbook_name: str | None = None,
        playbook_yaml: str | None = None,
        status: str = "drafted",
        validation_json: str | None = None,
        session_id: str | None = None,
        created_by: str = "agent",
    ) -> PlaybookBuild:
        if not use_case or not isinstance(use_case, str):
            raise ValueError("use_case must be a non-empty string")
        ts = _now()
        build = PlaybookBuild(
            id=uuid.uuid4().hex,
            use_case=use_case,
            product=product,
            playbook_name=playbook_name,
            playbook_yaml=playbook_yaml,
            status=status or "drafted",
            validation_json=validation_json,
            deploy_summary=None,
            test_incident_id=None,
            session_id=session_id,
            created_by=created_by or "agent",
            created_at=ts,
            updated_at=ts,
        )
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO playbook_builds (id, use_case, product, playbook_name, "
                "playbook_yaml, status, validation_json, deploy_summary, "
                "test_incident_id, session_id, created_by, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    build.id, build.use_case, build.product, build.playbook_name,
                    build.playbook_yaml, build.status, build.validation_json,
                    build.deploy_summary, build.test_incident_id, build.session_id,
                    build.created_by, build.created_at, build.updated_at,
                ),
            )
        logger.info("PlaybookBuildStore.create_build id=%s status=%s", build.id, build.status)
        try:
            from usecase.audit_log import record_event
            record_event(
                "playbook_drafted",
                target=f"playbook_build:{build.id}",
                status="success",
                metadata={
                    "product": product,
                    "playbook_name": playbook_name,
                    "status": status,
                },
            )
        except Exception:  # noqa: BLE001 — audit is best-effort
            pass
        return build

    def get_build(self, build_id: str) -> PlaybookBuild | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM playbook_builds WHERE id = ?", (build_id,)
            ).fetchone()
        return self._row_to_build(row) if row else None

    def list_builds(
        self, *, status: str | None = None, order: str = "desc",
    ) -> list[PlaybookBuild]:
        """List builds, optionally filtered by status + ordered by created_at.

        order="desc" (the default) sorts newest-first for the build-history
        UI; order="asc" sorts oldest-first. The status filter narrows to one
        lifecycle stage (drafted / validated / deployed / tested / failed).
        """
        clauses: list[str] = []
        params: list[str] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        order_by = (
            "created_at ASC, id ASC"
            if str(order).lower() == "asc"
            else "created_at DESC, id DESC"
        )
        with self._lock, self._conn() as c:
            rows = c.execute(
                f"SELECT * FROM playbook_builds{where} ORDER BY {order_by}",
                params,
            ).fetchall()
        return [self._row_to_build(r) for r in rows]

    def update_build(self, build_id: str, **fields) -> PlaybookBuild | None:
        """Partial update: any of use_case/product/playbook_name/playbook_yaml/
        status/validation_json/deploy_summary/test_incident_id/session_id.
        Unknown keys ignored. None values skipped (leave that field alone).
        Always bumps updated_at. Returns None if the build doesn't exist."""
        sets: list[str] = []
        params: list[str] = []
        for key in _BUILD_UPDATABLE:
            if key in fields and fields[key] is not None:
                sets.append(f"{key} = ?")
                params.append(fields[key])
        if not sets:
            return self.get_build(build_id)
        sets.append("updated_at = ?")
        params.append(_now())
        params.append(build_id)
        with self._lock, self._conn() as c:
            cur = c.execute(
                f"UPDATE playbook_builds SET {', '.join(sets)} WHERE id = ?", params,
            )
            if cur.rowcount == 0:
                return None
        updated = self.get_build(build_id)
        # Audit the lifecycle transitions an operator cares about, but only
        # when the caller actually set `status` in this update (a metadata-only
        # edit shouldn't emit a deploy/test event). Best-effort, like create.
        new_status = fields.get("status")
        if new_status is not None and updated is not None:
            try:
                from usecase.audit_log import record_event
                if new_status == "deployed":
                    record_event(
                        "playbook_deployed",
                        target=f"playbook_build:{build_id}",
                        status="success",
                        metadata={
                            "playbook_name": updated.playbook_name,
                            "test_incident_id": updated.test_incident_id,
                        },
                    )
                elif new_status == "tested":
                    record_event(
                        "playbook_test_run",
                        target=f"playbook_build:{build_id}",
                        status="success",
                        metadata={
                            "playbook_name": updated.playbook_name,
                            "test_incident_id": updated.test_incident_id,
                        },
                    )
                elif new_status == "failed":
                    record_event(
                        "playbook_test_run",
                        target=f"playbook_build:{build_id}",
                        status="failure",
                        metadata={
                            "playbook_name": updated.playbook_name,
                            "test_incident_id": updated.test_incident_id,
                        },
                    )
            except Exception:  # noqa: BLE001 — audit is best-effort
                pass
        return updated

    def delete_build(self, build_id: str) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute("DELETE FROM playbook_builds WHERE id = ?", (build_id,))
        deleted = cur.rowcount > 0
        if deleted:
            try:
                from usecase.audit_log import record_event
                record_event(
                    "playbook_build_deleted",
                    target=f"playbook_build:{build_id}",
                    status="success",
                    metadata={"build_id": build_id},
                )
            except Exception:  # noqa: BLE001 — audit is best-effort
                pass
        return deleted

    # ─── Row mappers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_build(row: sqlite3.Row) -> PlaybookBuild:
        return PlaybookBuild(
            id=row["id"], use_case=row["use_case"], product=row["product"],
            playbook_name=row["playbook_name"], playbook_yaml=row["playbook_yaml"],
            status=row["status"], validation_json=row["validation_json"],
            deploy_summary=row["deploy_summary"], test_incident_id=row["test_incident_id"],
            session_id=row["session_id"], created_by=row["created_by"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )


# ─────────────────────────────────────────────────────────────────
# Module-level singleton accessor — wired by main.py (mirrors
# investigation_store / instance_store). Lets the playbook_build_* MCP
# tools + REST layer look up the store at call time without threading it
# through every signature. None pre-boot or in tests that construct the
# store directly.
# ─────────────────────────────────────────────────────────────────

_playbook_build_store: PlaybookBuildStore | None = None


def set_playbook_build_store(s: PlaybookBuildStore | None) -> None:
    global _playbook_build_store
    _playbook_build_store = s


def playbook_build_store() -> PlaybookBuildStore | None:
    return _playbook_build_store
