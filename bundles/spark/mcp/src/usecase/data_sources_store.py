"""Data source install store — v0.8.0 Phase 2.

Persists the operator's installed vendor schemas (the "data sources"
that v0.8.0 Phase 1 extracts from Cortex ModelingRule schema.json
files). This is a SEPARATE store from marketplace_store.py — different
lifecycle, different domain, different operator-mental-model:

  * Marketplace store: per-connector install flag ("is the cortex-content
    connector available for instantiation?"). Granularity = 7 connectors.
  * Data sources store: per-vendor-schema install record ("is the
    FortiGate/FortiGate_1_3/fortinet_fortigate_raw schema usable as a
    log-simulation override?"). Granularity = ~217 candidate data sources
    across all XSIAM-tagged content packs, with field inventories
    ranging from 1 (rawlog-only) to 200+ fields.

The two stores must remain decoupled. An operator can uninstall a data
source without uninstalling the cortex-content connector that powered
its discovery, and vice versa.

# Schema

  data_sources (
    id                       TEXT PRIMARY KEY,    -- "<pack>/<rule>/<dataset>"
    pack_name                TEXT NOT NULL,
    rule_name                TEXT NOT NULL,
    dataset_name             TEXT NOT NULL,
    pack_version             TEXT,                 -- pack_metadata.json currentVersion
    is_rawlog_only           INTEGER NOT NULL,     -- 0 | 1 (Phase 1 classifier)
    field_count              INTEGER NOT NULL,
    non_meta_field_count     INTEGER NOT NULL,
    supported_modules        TEXT,                 -- JSON array
    pack_description         TEXT,
    logo_url                 TEXT,
    logo_type                TEXT,                 -- "svg" | "png" | NULL
    installed_at             TEXT NOT NULL,        -- ISO8601 UTC
    installed_by             TEXT,                 -- "agent" | "user:operator" | "user:<id>"
    is_pinned                INTEGER NOT NULL DEFAULT 0,
    pinned_version           TEXT,
    source_revision          TEXT                  -- catalog SHA at install (provenance)
  );

  data_source_fields (
    data_source_id           TEXT NOT NULL,
    field_name               TEXT NOT NULL,
    field_type               TEXT,
    is_array                 INTEGER NOT NULL DEFAULT 0,
    is_meta                  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (data_source_id, field_name),
    FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE CASCADE
  );

  data_source_xdm_mappings (
    data_source_id           TEXT NOT NULL,
    xdm_path                 TEXT NOT NULL,
    raw_expr                 TEXT NOT NULL,
    PRIMARY KEY (data_source_id, xdm_path),
    FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE CASCADE
  );

The XDM mappings table is created here but stays empty in Phase 2 — the
mapping extractor (parsing the .xif modeling rule) is Phase 3 work. The
schema lives in this release so a future migration doesn't have to add
the table separately.

# Why composite ID instead of UUID

`<pack>/<rule>/<dataset>` is human-readable, deterministic, and matches
the natural-key the operator would use when describing a data source
("install the FortiGate/FortiGate_1_3 data source"). A UUID would force
us to maintain a reverse-lookup index every time. The penalty is that
renames in the upstream catalog would orphan the row, but the catalog
treats pack+rule+dataset as a stable surface — visible renames are
rare and explicit.

# Concurrency

Same lock-on-connection pattern as the other stores. Multiple async
tasks inside one MCP process serialize on `self._lock`. The DB is
opened with `check_same_thread=False` for the FastMCP handler pool.

# Boundary

This is CATALOG state — agent IS allowed to mutate via MCP tools
(`data_sources_install`, `data_sources_uninstall`). Per CLAUDE.md §
Catalog boundary ≠ credential boundary (v0.5.0+).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("Phantom MCP")

DEFAULT_DATA_ROOT = Path("/app/data")
DB_FILENAME = "data_sources.db"


@dataclass
class DataSourceField:
    """One vendor field within a data source's schema."""
    name: str
    type: str | None = None
    is_array: bool = False
    is_meta: bool = False
    # v0.17.7 — operator-facing description. Sourced from the bundled
    # YAML. The agent reads this when generating logs to pick correct
    # values for each field; the UI surfaces it as a Description column
    # in the schema preview drawer.
    description: str = ""
    # v0.17.68 — operator-facing example wire value. Sourced from the
    # bundled YAML (`example:` per field). Teaches Phantom AND any
    # downstream modeling rule (Cortex / Splunk / Elastic) what shape
    # the value must take on the wire. UI renders it as an Example
    # column in the schema preview drawer.
    example: str = ""


@dataclass
class DataSourceXdmMapping:
    """One XDM path mapping for a data source. Phase 3 populates this."""
    xdm_path: str
    raw_expr: str


@dataclass
class DataSource:
    """An installed data source.

    Field count and meta-field stats are stored denormalized so list
    queries don't need to join data_source_fields just for the badge
    numbers ("17 fields • 12 non-meta"). The join is for the
    `get_with_schema` call site.
    """
    id: str
    pack_name: str
    rule_name: str
    dataset_name: str
    pack_version: str | None = None
    is_rawlog_only: bool = False
    field_count: int = 0
    non_meta_field_count: int = 0
    supported_modules: list[str] = field(default_factory=list)
    pack_description: str | None = None
    logo_url: str | None = None
    logo_type: str | None = None
    installed_at: str = ""
    installed_by: str | None = None
    is_pinned: bool = False
    pinned_version: str | None = None
    source_revision: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pack_name": self.pack_name,
            "rule_name": self.rule_name,
            "dataset_name": self.dataset_name,
            "pack_version": self.pack_version,
            "is_rawlog_only": self.is_rawlog_only,
            "field_count": self.field_count,
            "non_meta_field_count": self.non_meta_field_count,
            "supported_modules": self.supported_modules,
            "pack_description": self.pack_description,
            "logo_url": self.logo_url,
            "logo_type": self.logo_type,
            "installed_at": self.installed_at,
            "installed_by": self.installed_by,
            "is_pinned": self.is_pinned,
            "pinned_version": self.pinned_version,
            "source_revision": self.source_revision,
        }


@dataclass
class DataSourceWithSchema:
    """A data source plus its full field inventory and XDM mappings.

    Returned by `get_with_schema` — the operator UI's drill-down view
    needs this expanded form. List view uses the lighter `DataSource`.
    """
    data_source: DataSource
    fields: list[DataSourceField]
    xdm_mappings: list[DataSourceXdmMapping]

    def to_dict(self) -> dict[str, Any]:
        d = self.data_source.to_dict()
        d["fields"] = [
            {
                "name": f.name,
                "type": f.type,
                "is_array": f.is_array,
                "is_meta": f.is_meta,
                "description": f.description,
                "example": f.example,
            }
            for f in self.fields
        ]
        # v0.17.74 — xdm_mappings dropped from the serialized payload.
        # SQLite table `data_source_xdm_mappings` is left in place
        # (orphaned) for back-compat; nothing writes or reads it now.
        return d


def compose_data_source_id(pack_name: str, rule_name: str, dataset_name: str) -> str:
    """Canonical id composition. Use this everywhere rather than f-strings;
    keeps the contract centralized for future tweaks (e.g. percent-encoding
    if a dataset name ever contains a slash)."""
    return f"{pack_name}/{rule_name}/{dataset_name}"


class DataSourcesStore:
    """SQLite-backed store for installed data sources.

    The store is process-private — one instance per MCP process,
    wired at boot via `set_data_sources_store`. All other code reaches
    it via `get_data_sources_store()`.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        if db_path is None:
            root = Path(os.environ.get("DATA_ROOT", str(DEFAULT_DATA_ROOT)))
            db_path = root / DB_FILENAME
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    # ── Connection helper ─────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        # FK enforcement is OFF by default in SQLite. Cascade-delete on
        # data_source_fields + data_source_xdm_mappings requires it ON.
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    # ── Schema init ───────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS data_sources (
                    id TEXT PRIMARY KEY,
                    pack_name TEXT NOT NULL,
                    rule_name TEXT NOT NULL,
                    dataset_name TEXT NOT NULL,
                    pack_version TEXT,
                    is_rawlog_only INTEGER NOT NULL DEFAULT 0,
                    field_count INTEGER NOT NULL DEFAULT 0,
                    non_meta_field_count INTEGER NOT NULL DEFAULT 0,
                    supported_modules TEXT,
                    pack_description TEXT,
                    logo_url TEXT,
                    logo_type TEXT,
                    installed_at TEXT NOT NULL,
                    installed_by TEXT,
                    is_pinned INTEGER NOT NULL DEFAULT 0,
                    pinned_version TEXT,
                    source_revision TEXT
                );

                CREATE TABLE IF NOT EXISTS data_source_fields (
                    data_source_id TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    field_type TEXT,
                    is_array INTEGER NOT NULL DEFAULT 0,
                    is_meta INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (data_source_id, field_name),
                    FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS data_source_xdm_mappings (
                    data_source_id TEXT NOT NULL,
                    xdm_path TEXT NOT NULL,
                    raw_expr TEXT NOT NULL,
                    PRIMARY KEY (data_source_id, xdm_path),
                    FOREIGN KEY (data_source_id) REFERENCES data_sources(id) ON DELETE CASCADE
                );

                -- Helpful filter index for list-with-search
                CREATE INDEX IF NOT EXISTS idx_data_sources_pack_name
                    ON data_sources(pack_name);
                CREATE INDEX IF NOT EXISTS idx_data_sources_dataset_name
                    ON data_sources(dataset_name);
                """
            )
            # v0.17.7 — additive migration: description column on
            # data_source_fields. Existing installs predate this and need
            # the column added. PRAGMA-based guard is idempotent.
            cur = conn.execute("PRAGMA table_info(data_source_fields)")
            cols = {row[1] for row in cur.fetchall()}
            if "description" not in cols:
                conn.execute(
                    "ALTER TABLE data_source_fields "
                    "ADD COLUMN description TEXT NOT NULL DEFAULT ''"
                )
                logger.info(
                    "data_sources_store: v0.17.7 migration added "
                    "description column to data_source_fields"
                )
            # v0.17.68 — additive migration: example column. Same
            # idempotent PRAGMA-guarded pattern as description.
            if "example" not in cols:
                conn.execute(
                    "ALTER TABLE data_source_fields "
                    "ADD COLUMN example TEXT NOT NULL DEFAULT ''"
                )
                logger.info(
                    "data_sources_store: v0.17.68 migration added "
                    "example column to data_source_fields"
                )

    # ── Row → dataclass helpers ───────────────────────────────────

    def _row_to_data_source(self, row: sqlite3.Row) -> DataSource:
        modules_raw = row["supported_modules"]
        try:
            supported_modules = (
                json.loads(modules_raw) if modules_raw else []
            )
            if not isinstance(supported_modules, list):
                supported_modules = []
        except (json.JSONDecodeError, TypeError):
            supported_modules = []
        return DataSource(
            id=row["id"],
            pack_name=row["pack_name"],
            rule_name=row["rule_name"],
            dataset_name=row["dataset_name"],
            pack_version=row["pack_version"],
            is_rawlog_only=bool(row["is_rawlog_only"]),
            field_count=int(row["field_count"]),
            non_meta_field_count=int(row["non_meta_field_count"]),
            supported_modules=supported_modules,
            pack_description=row["pack_description"],
            logo_url=row["logo_url"],
            logo_type=row["logo_type"],
            installed_at=row["installed_at"],
            installed_by=row["installed_by"],
            is_pinned=bool(row["is_pinned"]),
            pinned_version=row["pinned_version"],
            source_revision=row["source_revision"],
        )

    # ── Public API ────────────────────────────────────────────────

    def install(
        self,
        data_source: DataSource,
        fields: list[DataSourceField] | None = None,
        xdm_mappings: list[DataSourceXdmMapping] | None = None,
    ) -> bool:
        """Install (or replace) a data source.

        Idempotent — re-installing the same id replaces the row + all
        its dependent fields + xdm_mappings. The cascade DELETE on the
        FK drops the dependents before we re-insert, so there's no
        stale-row risk.

        Returns True if the row was newly inserted; False if it was
        replaced. Both outcomes mean the post-condition holds: this
        data source is installed with the supplied schema.
        """
        if not data_source.id:
            raise ValueError("data_source.id is required")
        if not data_source.installed_at:
            data_source.installed_at = _iso_now()

        was_new = not self.is_installed(data_source.id)

        with self._lock, self._connect() as conn:
            # If already installed, drop the row (cascade-deletes the
            # dependents) before re-inserting. Cleaner than UPSERT
            # because we want the cascade behavior on the FKs.
            conn.execute(
                "DELETE FROM data_sources WHERE id = ?", (data_source.id,)
            )
            conn.execute(
                """
                INSERT INTO data_sources (
                    id, pack_name, rule_name, dataset_name, pack_version,
                    is_rawlog_only, field_count, non_meta_field_count,
                    supported_modules, pack_description, logo_url, logo_type,
                    installed_at, installed_by, is_pinned, pinned_version,
                    source_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data_source.id,
                    data_source.pack_name,
                    data_source.rule_name,
                    data_source.dataset_name,
                    data_source.pack_version,
                    int(data_source.is_rawlog_only),
                    data_source.field_count,
                    data_source.non_meta_field_count,
                    json.dumps(data_source.supported_modules)
                    if data_source.supported_modules
                    else None,
                    data_source.pack_description,
                    data_source.logo_url,
                    data_source.logo_type,
                    data_source.installed_at,
                    data_source.installed_by,
                    int(data_source.is_pinned),
                    data_source.pinned_version,
                    data_source.source_revision,
                ),
            )

            if fields:
                conn.executemany(
                    """
                    INSERT INTO data_source_fields (
                        data_source_id, field_name, field_type, is_array,
                        is_meta, description, example
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            data_source.id,
                            f.name,
                            f.type,
                            int(f.is_array),
                            int(f.is_meta),
                            f.description or "",
                            f.example or "",
                        )
                        for f in fields
                    ],
                )

            if xdm_mappings:
                conn.executemany(
                    """
                    INSERT INTO data_source_xdm_mappings (
                        data_source_id, xdm_path, raw_expr
                    ) VALUES (?, ?, ?)
                    """,
                    [
                        (data_source.id, m.xdm_path, m.raw_expr)
                        for m in xdm_mappings
                    ],
                )

        return was_new

    def uninstall(self, data_source_id: str) -> bool:
        """Remove a data source by id. Returns True if a row was deleted.

        Cascade FK drops the dependent fields + xdm_mappings rows.
        """
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM data_sources WHERE id = ?", (data_source_id,)
            )
            return cur.rowcount > 0

    def is_installed(self, data_source_id: str) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "SELECT 1 FROM data_sources WHERE id = ? LIMIT 1",
                (data_source_id,),
            )
            return cur.fetchone() is not None

    def get(self, data_source_id: str) -> Optional[DataSource]:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM data_sources WHERE id = ?", (data_source_id,)
            ).fetchone()
        return self._row_to_data_source(row) if row else None

    def get_with_schema(
        self, data_source_id: str
    ) -> Optional[DataSourceWithSchema]:
        """Return the data source AND its full field inventory + XDM
        mappings. UI drill-down view consumes this."""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM data_sources WHERE id = ?", (data_source_id,)
            ).fetchone()
            if not row:
                return None
            ds = self._row_to_data_source(row)
            field_rows = conn.execute(
                """
                SELECT field_name, field_type, is_array, is_meta,
                       description, example
                FROM data_source_fields
                WHERE data_source_id = ?
                ORDER BY is_meta ASC, field_name ASC
                """,
                (data_source_id,),
            ).fetchall()
            mapping_rows = conn.execute(
                """
                SELECT xdm_path, raw_expr
                FROM data_source_xdm_mappings
                WHERE data_source_id = ?
                ORDER BY xdm_path ASC
                """,
                (data_source_id,),
            ).fetchall()

        fields = [
            DataSourceField(
                name=r["field_name"],
                type=r["field_type"],
                is_array=bool(r["is_array"]),
                is_meta=bool(r["is_meta"]),
                # v0.17.7 — column added via PRAGMA-guarded ALTER.
                # `r["description"]` returns None on pre-migration rows
                # in the brief window before the migration runs; coerce.
                description=(r["description"] or "") if "description" in r.keys() else "",
                # v0.17.68 — same PRAGMA-guarded migration pattern.
                example=(r["example"] or "") if "example" in r.keys() else "",
            )
            for r in field_rows
        ]
        mappings = [
            DataSourceXdmMapping(xdm_path=r["xdm_path"], raw_expr=r["raw_expr"])
            for r in mapping_rows
        ]
        return DataSourceWithSchema(
            data_source=ds, fields=fields, xdm_mappings=mappings
        )

    def list(self, filter: str | None = None) -> list[DataSource]:
        """List installed data sources. `filter` (if provided) does a
        case-insensitive LIKE match on pack_name OR dataset_name OR
        rule_name OR pack_description.

        Result is sorted by pack_name then dataset_name.
        """
        with self._lock, self._connect() as conn:
            if filter:
                pat = f"%{filter}%"
                rows = conn.execute(
                    """
                    SELECT * FROM data_sources
                    WHERE pack_name LIKE ? COLLATE NOCASE
                       OR dataset_name LIKE ? COLLATE NOCASE
                       OR rule_name LIKE ? COLLATE NOCASE
                       OR (pack_description IS NOT NULL
                           AND pack_description LIKE ? COLLATE NOCASE)
                    ORDER BY pack_name, dataset_name
                    """,
                    (pat, pat, pat, pat),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM data_sources ORDER BY pack_name, dataset_name"
                ).fetchall()
        return [self._row_to_data_source(r) for r in rows]

    def count(self) -> int:
        with self._lock, self._connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM data_sources"
            ).fetchone()[0]

    def set_pinned(
        self, data_source_id: str, pinned: bool, pinned_version: str | None = None
    ) -> bool:
        """Pin/unpin a data source to a specific pack_version.

        Pinned data sources are excluded from the "update available"
        prompt the UI shows. When `pinned=True`, callers SHOULD also
        pass `pinned_version` (typically the data source's current
        pack_version) so the pin is anchored to a specific revision.

        Returns True if a row was updated.
        """
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                UPDATE data_sources
                SET is_pinned = ?, pinned_version = ?
                WHERE id = ?
                """,
                (int(pinned), pinned_version if pinned else None, data_source_id),
            )
            return cur.rowcount > 0


# ── Helpers ───────────────────────────────────────────────────────


def _iso_now() -> str:
    """UTC ISO 8601 — same format every other store uses."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Module-level singleton ────────────────────────────────────────
#
# Same convention as marketplace_store, instance_store, etc.
# Set once at boot from main.py; readers go through the getter.

_singleton: DataSourcesStore | None = None


def set_data_sources_store(store: DataSourcesStore | None) -> None:
    """Wire the process-wide data sources store. Called once from main.py."""
    global _singleton
    _singleton = store


def get_data_sources_store() -> DataSourcesStore | None:
    """Return the active store (or None when not yet wired).

    Callers must tolerate None — early-boot code paths may run before
    main.py finishes wiring."""
    return _singleton
