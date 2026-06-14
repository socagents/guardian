"""SqliteKnowledgeBase — bundle-local implementation of the spec's
`knowledge` capability (spec.md §6.10 row "knowledge").

Per spec §6.10, `knowledge` has two backend impls:

  - **Standalone**: `SqliteKnowledgeBase` — local sqlite at
                    `<data_root>/kb.db`, brute-force cosine search.
  - **Platform**:   `OpenSearchKnowledgeBase` — shared per-tenant
                    OpenSearch cluster with proper inverted index +
                    pgvector for ANN.

This module is the standalone variant. It's structurally a sibling of
`SqliteMemoryStore`: same Embedder protocol, same brute-force scan,
same row-by-row JSON-encoded metadata. The differences shape the API:

  - **Multi-KB**: a single store hosts multiple kb_name namespaces
    (manifest.knowledge.bundled[].name).
  - **Doc-id is external**: rows are keyed by (kb_name, doc_id) where
    doc_id comes from the document's frontmatter `id` field, NOT a
    uuid4 — KB contents have stable external identity (T1078, PH-SOC-001),
    unlike memories which are anonymous KV pairs.
  - **Read-only at the agent surface**: `manifest.kbWrites: []` means
    there's no `knowledge_store` tool. The store has `upsert()` and
    `delete()` for the boot-time loader to use, but the agent path
    only ever calls `search()` and `get_doc()`.
  - **Hash-based change detection**: `source_hash` lets the loader
    skip re-embedding unchanged files between boots.

# Schema

    kb_documents(
      id            TEXT PRIMARY KEY,    -- uuid4 (internal)
      kb_name       TEXT NOT NULL,        -- "guardian-soc"
      doc_id        TEXT NOT NULL,        -- frontmatter.id, e.g. "PH-SOC-001"
      title         TEXT,
      category      TEXT,                 -- frontmatter.category (indexed)
      content       TEXT NOT NULL,        -- searchable body (post-frontmatter)
      metadata_json TEXT NOT NULL,        -- frontmatter as JSON
      source_path   TEXT,                 -- relative path from bundle/kbs/
      source_hash   TEXT NOT NULL,        -- SHA-256 of the on-disk file
      embedding     BLOB NOT NULL,        -- packed float32, length = dims
      loaded_at     TEXT NOT NULL,
      UNIQUE(kb_name, doc_id)
    );
    CREATE INDEX idx_kb_kb_name ON kb_documents(kb_name);
    CREATE INDEX idx_kb_category ON kb_documents(kb_name, category);
"""

from __future__ import annotations

import json
import logging
import math
import os
import sqlite3
import struct
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from usecase.memory_store import Embedder, TextHashEmbedder

logger = logging.getLogger("Guardian MCP")

DEFAULT_DATA_ROOT = Path("/app/data")


@dataclass(frozen=True)
class KbDocument:
    id: str
    kb_name: str
    doc_id: str
    title: str | None
    category: str | None
    content: str
    metadata: dict[str, Any]
    source_path: str | None
    source_hash: str
    loaded_at: str

    def to_dict(
        self, *, score: float | None = None, include_content: bool = True
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "kb_name": self.kb_name,
            "doc_id": self.doc_id,
            "title": self.title,
            "category": self.category,
            "metadata": self.metadata,
            "source_path": self.source_path,
            "loaded_at": self.loaded_at,
        }
        if include_content:
            out["content"] = self.content
        if score is not None:
            out["score"] = score
        return out


class SqliteKnowledgeBase:
    """Multi-KB sqlite-backed knowledge store at ``<data_root>/kb.db``.

    Constructed once at boot; the `KbLoader` populates it from the
    bundle's `manifest.knowledge.bundled[]` directories. After load,
    the store is effectively read-only at the agent surface — only
    the loader writes (idempotent upserts).
    """

    def __init__(
        self,
        data_root: Path | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._data_root = (data_root or self._resolve_data_root()).resolve()
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_root / "kb.db"
        self._embedder = embedder or TextHashEmbedder()
        self._lock = threading.Lock()
        self._init_schema()
        logger.info(
            "SqliteKnowledgeBase at %s (embedder=%s, dims=%d)",
            self._db_path, type(self._embedder).__name__, self._embedder.dims,
        )

    @staticmethod
    def _resolve_data_root() -> Path:
        raw = os.getenv("DATA_ROOT", str(DEFAULT_DATA_ROOT))
        return Path(raw)

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def embedder(self) -> Embedder:
        return self._embedder

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(self._db_path, isolation_level=None, check_same_thread=False)
        c.row_factory = sqlite3.Row
        return c

    def _init_schema(self) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS kb_documents (
                    id            TEXT PRIMARY KEY,
                    kb_name       TEXT NOT NULL,
                    doc_id        TEXT NOT NULL,
                    title         TEXT,
                    category      TEXT,
                    content       TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    source_path   TEXT,
                    source_hash   TEXT NOT NULL,
                    embedding     BLOB NOT NULL,
                    loaded_at     TEXT NOT NULL,
                    UNIQUE(kb_name, doc_id)
                )
                """
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_kb_kb_name "
                "ON kb_documents(kb_name)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_kb_category "
                "ON kb_documents(kb_name, category)"
            )
            # v0.2.20 — normalized tag index so arbitrary labels (tactic,
            # platform, product, investigation-type, …) are UI-filterable.
            # Only `category` was filterable before; large KBs (full ATT&CK,
            # SOAR playbooks) need richer faceting. Tags are re-synced from
            # each doc's frontmatter on every upsert (incl. the unchanged
            # path), so adding this table to an existing kb.db backfills on
            # the next boot.
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS kb_doc_tags (
                    kb_name TEXT NOT NULL,
                    doc_id  TEXT NOT NULL,
                    tag     TEXT NOT NULL,
                    UNIQUE(kb_name, doc_id, tag)
                )
                """
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_kb_doc_tags_tag "
                "ON kb_doc_tags(kb_name, tag)"
            )

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @staticmethod
    def _normalize_tags(metadata: dict[str, Any] | None) -> list[str]:
        """Extract a doc's filterable tags from its metadata `tags` list,
        lowercased + de-duplicated. Non-list / non-str entries are ignored."""
        raw = (metadata or {}).get("tags")
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for t in raw:
            if isinstance(t, str) and t.strip():
                tag = t.strip().lower()
                if tag not in seen:
                    seen.add(tag)
                    out.append(tag)
        return out

    def _sync_tags(self, c: Any, kb_name: str, doc_id: str, metadata: dict[str, Any]) -> None:
        """Replace a doc's tag rows from its current metadata. Uses the
        caller's cursor `c` (no re-lock) so it can run inside an existing
        transaction. Cheap enough to run on every upsert, which keeps the
        index consistent AND backfills docs indexed before the table existed."""
        c.execute("DELETE FROM kb_doc_tags WHERE kb_name = ? AND doc_id = ?", (kb_name, doc_id))
        for tag in self._normalize_tags(metadata):
            c.execute(
                "INSERT OR IGNORE INTO kb_doc_tags(kb_name, doc_id, tag) VALUES (?, ?, ?)",
                (kb_name, doc_id, tag),
            )

    @staticmethod
    def _tag_clause(tags: list[str]) -> tuple[str, list[Any]]:
        """SQL fragment (+ params) requiring a kb_documents row to carry ALL
        of `tags` (AND semantics — filter chips narrow the set). References
        kb_documents.kb_name/doc_id, so it slots into any WHERE on that table."""
        placeholders = ",".join("?" for _ in tags)
        clause = (
            "(SELECT COUNT(DISTINCT t.tag) FROM kb_doc_tags t "
            "WHERE t.kb_name = kb_documents.kb_name AND t.doc_id = kb_documents.doc_id "
            f"AND t.tag IN ({placeholders})) = ?"
        )
        return clause, [*tags, len(tags)]

    def kb_tags(self, kb_name: str, *, limit: int = 200) -> list[dict[str, Any]]:
        """Distinct tags in a KB with per-tag doc counts, for UI filter chips.
        Ordered by count desc then tag asc."""
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT tag, COUNT(*) AS n FROM kb_doc_tags WHERE kb_name = ? "
                "GROUP BY tag ORDER BY n DESC, tag ASC LIMIT ?",
                (kb_name, max(1, min(limit, 1000))),
            ).fetchall()
        return [{"tag": r["tag"], "count": int(r["n"])} for r in rows]

    @staticmethod
    def _pack(vec: list[float]) -> bytes:
        return struct.pack(f"{len(vec)}f", *vec)

    @staticmethod
    def _unpack(blob: bytes, dims: int) -> list[float]:
        return list(struct.unpack(f"{dims}f", blob))

    def _resolve_embedding(
        self,
        content: str,
        precomputed: list[float] | None,
        precomputed_model: str | None,
        *,
        where: str,
    ) -> list[float]:
        """Return the embedding for `content`, preferring a TRUSTWORTHY
        pre-computed vector over a live (slow, billed) `embed()` call.

        A pre-computed vector is trusted only when its declared model matches
        the runtime embedder's `model_id` AND its length matches `dims`. Any
        other case (absent, wrong model, wrong dims) falls back to embed —
        loudly when a vector was supplied but couldn't be trusted, so a
        wrong-model bundle never silently ships bad vectors.
        """
        if precomputed is not None:
            runtime_model = getattr(self._embedder, "model_id", None)
            if (
                precomputed_model
                and runtime_model
                and precomputed_model == runtime_model
                and len(precomputed) == self._embedder.dims
            ):
                return precomputed
            logger.warning(
                "kb_store: %s pre-computed embedding NOT trusted "
                "(doc_model=%r runtime_model=%r dims=%d/expected %d) — embedding live",
                where, precomputed_model, runtime_model,
                len(precomputed), self._embedder.dims,
            )
        embedding = self._embedder.embed(content)
        if len(embedding) != self._embedder.dims:
            raise RuntimeError(
                f"embedder returned {len(embedding)} dims; expected {self._embedder.dims}"
            )
        return embedding

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
        return sum(x * y for x, y in zip(a, b)) / norm_b

    # ─── Loader-facing CRUD ────────────────────────────────────

    def upsert(
        self,
        *,
        kb_name: str,
        doc_id: str,
        content: str,
        title: str | None = None,
        category: str | None = None,
        metadata: dict[str, Any] | None = None,
        source_path: str | None = None,
        source_hash: str,
        precomputed_embedding: list[float] | None = None,
        precomputed_model: str | None = None,
    ) -> tuple[KbDocument, str]:
        """Insert or update a document. Returns (doc, action) where
        action is "insert" | "update" | "unchanged".

        "unchanged" means the source_hash matched — we skipped the
        embed step entirely. That's the v1 change-detection win: most
        boots re-load the same docs, and re-embedding is the slow
        part (especially with a future network embedder).

        v0.2.17: `precomputed_embedding` (+ `precomputed_model`) lets a KB
        bundle ship the vector baked in, so a fresh-volume install skips the
        per-doc Vertex round-trip (which is ~200ms each — minutes for a large
        KB). It is trusted ONLY when its declared model matches the runtime
        embedder's `model_id` AND its length matches `dims`; any mismatch logs
        a warning and falls back to a live `embed()` — never silently ships a
        wrong-model vector.
        """
        if not kb_name or not doc_id:
            raise ValueError("kb_name and doc_id are required")
        meta_dict = dict(metadata or {})
        with self._lock, self._conn() as c:
            existing = c.execute(
                "SELECT * FROM kb_documents WHERE kb_name = ? AND doc_id = ?",
                (kb_name, doc_id),
            ).fetchone()
            if existing and existing["source_hash"] == source_hash:
                # Content unchanged — but re-sync tags (cheap; backfills the
                # v0.2.20 kb_doc_tags index for docs indexed before it existed).
                self._sync_tags(c, kb_name, doc_id, meta_dict)
                return self._row_to_doc(existing), "unchanged"

        # Re-embed only when content actually changed (or doc is new) —
        # unless the doc shipped a trustworthy pre-computed vector.
        embedding = self._resolve_embedding(
            content,
            precomputed_embedding,
            precomputed_model,
            where=f"{kb_name}:{doc_id}",
        )
        embedding_blob = self._pack(embedding)
        now = self._now_iso()

        with self._lock, self._conn() as c:
            if existing:
                doc_uuid = existing["id"]
                c.execute(
                    "UPDATE kb_documents SET title = ?, category = ?, "
                    "content = ?, metadata_json = ?, source_path = ?, "
                    "source_hash = ?, embedding = ?, loaded_at = ? "
                    "WHERE id = ?",
                    (title, category, content, json.dumps(meta_dict),
                     source_path, source_hash, embedding_blob, now, doc_uuid),
                )
                action = "update"
            else:
                doc_uuid = str(uuid.uuid4())
                c.execute(
                    "INSERT INTO kb_documents "
                    "(id, kb_name, doc_id, title, category, content, "
                    " metadata_json, source_path, source_hash, "
                    " embedding, loaded_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (doc_uuid, kb_name, doc_id, title, category, content,
                     json.dumps(meta_dict), source_path, source_hash,
                     embedding_blob, now),
                )
                action = "insert"
            self._sync_tags(c, kb_name, doc_id, meta_dict)

        from usecase.audit_log import ACTION_KB_DOC_INDEXED, record_event
        record_event(
            ACTION_KB_DOC_INDEXED,
            target=f"kb:{kb_name}:doc:{doc_id}",
            status="success",
            metadata={
                "kb_name": kb_name,
                "doc_id": doc_id,
                "action": action,
                "content_chars": len(content),
                "source_path": source_path,
            },
        )
        return KbDocument(
            id=doc_uuid, kb_name=kb_name, doc_id=doc_id,
            title=title, category=category, content=content,
            metadata=meta_dict, source_path=source_path,
            source_hash=source_hash, loaded_at=now,
        ), action

    def remove(self, kb_name: str, doc_id: str) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute(
                "DELETE FROM kb_documents WHERE kb_name = ? AND doc_id = ?",
                (kb_name, doc_id),
            )
            c.execute(
                "DELETE FROM kb_doc_tags WHERE kb_name = ? AND doc_id = ?",
                (kb_name, doc_id),
            )
        if cur.rowcount > 0:
            from usecase.audit_log import ACTION_KB_DOC_REMOVED, record_event
            record_event(
                ACTION_KB_DOC_REMOVED,
                target=f"kb:{kb_name}:doc:{doc_id}",
                status="success",
                metadata={"kb_name": kb_name, "doc_id": doc_id},
            )
            return True
        return False

    def list_kb_names(self) -> list[str]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT DISTINCT kb_name FROM kb_documents ORDER BY kb_name"
            ).fetchall()
        return [r[0] for r in rows]

    def kb_doc_ids(self, kb_name: str) -> set[str]:
        """Return the set of doc_ids currently in `kb_name` — used by the
        loader to detect docs that vanished from disk."""
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT doc_id FROM kb_documents WHERE kb_name = ?",
                (kb_name,),
            ).fetchall()
        return {r[0] for r in rows}

    # ─── Read API ──────────────────────────────────────────────

    def get_doc(self, kb_name: str, doc_id: str) -> KbDocument | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM kb_documents WHERE kb_name = ? AND doc_id = ?",
                (kb_name, doc_id),
            ).fetchone()
        if row is None:
            return None
        from usecase.audit_log import ACTION_KB_DOC_READ, record_event
        record_event(
            ACTION_KB_DOC_READ,
            target=f"kb:{kb_name}:doc:{doc_id}",
            status="success",
            metadata={"kb_name": kb_name, "doc_id": doc_id},
        )
        return self._row_to_doc(row)

    def list_docs(
        self,
        kb_name: str,
        *,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KbDocument]:
        # v0.7.1: limit cap raised 500 → 2000. A large bundled KB grew
        # to 787 entries in v0.7.0; the old 500 cap silently truncated.
        # 2000 is a balanced max — enough to return the full set in one
        # call for any KB that's reasonable to operate on, while still
        # bounding payload size on misbehaving callers.
        clauses, params = ["kb_name = ?"], [kb_name]
        if category:
            clauses.append("category = ?")
            params.append(category)
        if tags:  # v0.2.20 — AND-filter by arbitrary tags
            clause, tparams = self._tag_clause([t.lower() for t in tags])
            clauses.append(clause)
            params.extend(tparams)
        params.extend([max(1, min(limit, 2000)), max(0, offset)])
        with self._lock, self._conn() as c:
            rows = c.execute(
                f"SELECT * FROM kb_documents WHERE {' AND '.join(clauses)} "
                "ORDER BY doc_id LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        return [self._row_to_doc(r) for r in rows]

    def count_docs(
        self,
        kb_name: str,
        *,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> int:
        """v0.7.1: total-count helper for paginated responses.

        Callers of list_docs() need to know whether there are more rows
        beyond the returned slice. Returning just `len(docs)` (the slice
        size) silently hides the true total — operators see 500 of 787
        and don't know what they're missing. This helper feeds the
        `total_count` field in the API response. v0.2.20: respects `tags`
        so the count matches a filtered list.
        """
        clauses, params = ["kb_name = ?"], [kb_name]
        if category:
            clauses.append("category = ?")
            params.append(category)
        if tags:
            clause, tparams = self._tag_clause([t.lower() for t in tags])
            clauses.append(clause)
            params.extend(tparams)
        with self._lock, self._conn() as c:
            row = c.execute(
                f"SELECT COUNT(*) AS n FROM kb_documents WHERE {' AND '.join(clauses)}",
                params,
            ).fetchone()
        return int(row["n"]) if row else 0

    def kb_summary(self) -> dict[str, dict[str, Any]]:
        """Per-KB summary used by /api/v1/kbs and the boot log."""
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT kb_name, COUNT(*) AS n, MAX(loaded_at) AS latest "
                "FROM kb_documents GROUP BY kb_name"
            ).fetchall()
        return {
            r["kb_name"]: {"doc_count": int(r["n"]), "latest_loaded_at": r["latest"]}
            for r in rows
        }

    def search(
        self,
        query: str,
        *,
        kb_name: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 5,
        offset: int = 0,
        min_score: float = 0.0,
    ) -> list[tuple[KbDocument, float]]:
        """Cosine similarity search across one or all KBs.

        Audit: every search records ACTION_KB_SEARCHED with the
        kb_name + result count + top score, like memory_searched.
        For SOC forensics, "what did the agent look up in the KB?"
        is one of the most useful questions.
        """
        if not isinstance(query, str) or not query.strip():
            return []
        query_vec = self._embedder.embed(query)
        clauses, params = [], []
        if kb_name:
            clauses.append("kb_name = ?")
            params.append(kb_name)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if tags:  # v0.2.20 — AND-filter candidates by tags before scoring
            clause, tparams = self._tag_clause([t.lower() for t in tags])
            clauses.append(clause)
            params.extend(tparams)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock, self._conn() as c:
            rows = c.execute(
                f"SELECT * FROM kb_documents {where}", params
            ).fetchall()

        scored: list[tuple[KbDocument, float]] = []
        dims = self._embedder.dims
        for row in rows:
            try:
                vec = self._unpack(row["embedding"], dims)
            except struct.error:
                continue
            score = self._cosine(query_vec, vec)
            if score < min_score:
                continue
            scored.append((self._row_to_doc(row), score))

        scored.sort(key=lambda x: x[1], reverse=True)
        _start = max(0, offset)
        scored = scored[_start : _start + max(1, min(limit, 100))]

        from usecase.audit_log import ACTION_KB_SEARCHED, record_event
        record_event(
            ACTION_KB_SEARCHED,
            target=f"kb:{kb_name or '_all_'}",
            status="success",
            metadata={
                "kb_name": kb_name,
                "category": category,
                "query_chars": len(query),
                "limit": limit,
                "result_count": len(scored),
                "top_score": scored[0][1] if scored else None,
            },
        )
        return scored

    # ─── Mappers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_doc(row: sqlite3.Row) -> KbDocument:
        return KbDocument(
            id=row["id"],
            kb_name=row["kb_name"],
            doc_id=row["doc_id"],
            title=row["title"],
            category=row["category"],
            content=row["content"],
            metadata=json.loads(row["metadata_json"]),
            source_path=row["source_path"],
            source_hash=row["source_hash"],
            loaded_at=row["loaded_at"],
        )


# ─────────────────────────────────────────────────────────────────
# Module-level singleton accessor — wired by main.py
# ─────────────────────────────────────────────────────────────────

_kb: SqliteKnowledgeBase | None = None


def set_knowledge_base(kb: SqliteKnowledgeBase | None) -> None:
    global _kb
    _kb = kb


def knowledge_base() -> SqliteKnowledgeBase | None:
    return _kb
