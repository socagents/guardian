"""SqliteMemoryStore — bundle-local implementation of the spec's
`memory` capability (spec.md §6.10 row "memory").

Per spec §6.10, `memory` has two backend impls:

  - **Standalone**: `SqliteMemoryStore` — local sqlite at
                    `<data_root>/memory.db` with embeddings as BLOBs
                    and brute-force cosine similarity search.
  - **Platform**:   `PgvectorMemoryStore` — shared per-tenant Postgres
                    with the pgvector extension for ANN search.

This module is the standalone variant. The agent's `memory_store(key,
value)` and `memory_search(query, limit)` built-in tools call into it.

# Why a brute-force scan is fine here

With the operator-scale workloads Guardian targets (a SOC analyst's
day-to-day notes, target hostnames, recent IOCs), memory tables will
sit in the low thousands of rows. Even with 768-dim float32 vectors,
that's ~3 MB scanned per search — well under 100ms on any modern
disk. Adding a vector index (annoy / hnswlib / faiss) is a real
optimization but premature for this scale. The Postgres backend gets
pgvector for free; standalone stays simple.

# Embedder protocol

The constructor takes an `Embedder` object satisfying:

    class Embedder:
        dims: int
        def embed(self, text: str) -> list[float]: ...

Phase 8 ships `TextHashEmbedder` (deterministic, 768-dim, no network)
as the v1 default. A future `VertexEmbedder` will call out to the
configured Google provider — same interface, drop-in. The embedder
choice is held by the store (set at construction); rotating embedders
requires re-embedding all existing memory rows, which would be a
migration step.

# Schema

    memories(
      id           TEXT PRIMARY KEY,    -- uuid4
      key          TEXT NOT NULL,        -- caller-supplied label
      value        TEXT NOT NULL,        -- the recallable content
      scope        TEXT NOT NULL,        -- "agent" | "session:<id>" | ...
      created_at   TEXT NOT NULL,
      updated_at   TEXT NOT NULL,
      ttl_seconds  INTEGER,              -- nullable; null = no TTL
      embedding    BLOB NOT NULL,        -- packed float32, length = dims
      meta_json    TEXT NOT NULL,
      UNIQUE(key, scope)                  -- (key, scope) is the natural id;
                                          -- writing the same (key, scope)
                                          -- updates in place
    );
    CREATE INDEX idx_memories_scope ON memories(scope);
    CREATE INDEX idx_memories_updated ON memories(updated_at);
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sqlite3
import struct
import threading
import time
from datetime import datetime
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

logger = logging.getLogger("Guardian MCP")

DEFAULT_DATA_ROOT = Path("/app/data")
DEFAULT_EMBED_DIMS = 768  # matches manifest.memory.embeddingDims

# #MEM-F3 — reap-on-read predicate. The boot-only TTL reaper meant expired
# rows kept being returned by get/list/search until the next restart. AND-ing
# this into every read WHERE clause hides expired rows immediately, even
# before the periodic reaper deletes them. updated_at is stored as
# 'YYYY-MM-DDTHH:MM:SSZ'; substr(...,1,19) strips the 'Z' so SQLite's
# datetime() parses it reliably across versions, and both sides are UTC.
_NOT_EXPIRED_SQL = (
    "(ttl_seconds IS NULL OR "
    "datetime(substr(updated_at, 1, 19)) >= "
    "datetime('now', '-' || ttl_seconds || ' seconds'))"
)


class Embedder(Protocol):
    """Minimal interface the memory store needs from any embedding backend."""

    dims: int
    # Stable identifier of the embedding model, e.g. "text-embedding-004"
    # (Vertex) or "texthash-v1" (stub). Used to validate that a doc's
    # PRE-COMPUTED embedding (baked into a KB bundle, v0.2.17+) was
    # produced by the SAME model the runtime uses before trusting it —
    # see kb_store.upsert(precomputed_embedding=...).
    model_id: str

    def embed(self, text: str) -> list[float]: ...


class TextHashEmbedder:
    """Deterministic stub embedder for v1.

    NOT a real semantic embedder — produces a vector from token-level
    SHA-256 hashes. Useful properties:
      - Deterministic: same text → same vector, every time.
      - Locality: shared substrings produce overlapping non-zero dims,
        so cosine distance does discriminate "similar" texts at coarse
        granularity (it won't distinguish synonyms, but it does pick up
        shared keywords).
      - Zero deps: no model files, no network, no GPU.

    Phase 8 ships this so the memory_store/search tools work end-to-end.
    A real `VertexEmbedder` (which calls
    google.cloud.aiplatform.TextEmbeddingModel) is a drop-in
    replacement — just instantiate it instead and the store behavior
    is unchanged.
    """

    def __init__(self, dims: int = DEFAULT_EMBED_DIMS) -> None:
        self.dims = dims
        # Pre-computed Vertex embeddings must NEVER match the stub, so a
        # bundle baked with "text-embedding-004" falls back to embed-on-boot
        # when the runtime is the stub (and vice-versa). The dims suffix
        # guards the rare mismatched-dims stub case too.
        self.model_id = f"texthash-v1-{dims}d"

    def embed(self, text: str) -> list[float]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        # Tokenize crudely (lowercase, split on non-alphanumerics).
        tokens: list[str] = []
        cur: list[str] = []
        for ch in text.lower():
            if ch.isalnum():
                cur.append(ch)
            elif cur:
                tokens.append("".join(cur))
                cur = []
        if cur:
            tokens.append("".join(cur))

        if not tokens:
            return [0.0] * self.dims

        vec = [0.0] * self.dims
        for tok in tokens:
            digest = hashlib.sha256(tok.encode("utf-8")).digest()
            # Spread the digest across dims by 4-byte groups → unsigned
            # int → bucket. Each token contributes to ~8 dims with the
            # SAME magnitude, making the scoring stable.
            for i in range(0, len(digest), 4):
                bucket = int.from_bytes(digest[i:i + 4], "big") % self.dims
                vec[bucket] += 1.0

        # L2-normalize so cosine similarity is just a dot product.
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


@dataclass(frozen=True)
class Memory:
    id: str
    key: str
    value: str
    scope: str
    created_at: str
    updated_at: str
    ttl_seconds: int | None
    meta: dict[str, Any]

    def to_dict(
        self,
        *,
        score: float | None = None,
        fts_promoted: bool | None = None,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "scope": self.scope,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "ttl_seconds": self.ttl_seconds,
            "meta": self.meta,
        }
        if score is not None:
            out["score"] = score
        # #MEM-F5 — surface whether the FTS5 keyword index promoted this
        # hit (vs pure embedding similarity) so the UI's "FTS hit" badge
        # can render. Only emitted when True to keep list payloads lean.
        if fts_promoted:
            out["fts_promoted"] = True
        return out


class SqliteMemoryStore:
    """Sqlite-backed semantic memory at ``<data_root>/memory.db``.

    Search is brute-force cosine similarity over all rows in the
    selected scope; see module docstring for why that's fine at this
    scale.
    """

    def __init__(
        self,
        data_root: Path | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self._data_root = (data_root or self._resolve_data_root()).resolve()
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_root / "memory.db"
        self._embedder = embedder or TextHashEmbedder()
        self._lock = threading.Lock()
        self._init_schema()
        n_expired = self._reap_expired()
        if n_expired:
            logger.info(
                "MemoryStore: reaped %d expired row(s) at boot", n_expired
            )
        logger.info(
            "SqliteMemoryStore at %s (embedder=%s, dims=%d)",
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
                CREATE TABLE IF NOT EXISTS memories (
                    id           TEXT PRIMARY KEY,
                    key          TEXT NOT NULL,
                    value        TEXT NOT NULL,
                    scope        TEXT NOT NULL,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    ttl_seconds  INTEGER,
                    embedding    BLOB NOT NULL,
                    meta_json    TEXT NOT NULL,
                    UNIQUE(key, scope)
                )
                """
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_scope "
                "ON memories(scope)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_updated "
                "ON memories(updated_at)"
            )

            # ── Phase 4.3 — FTS5 hybrid index ─────────────────
            #
            # Catches exact-keyword queries (UUIDs, hostnames, IP
            # addresses, vendor names) that the embedder misses
            # because the tokens have no semantic meaning to it. We
            # use a CONTENTLESS FTS5 table — manually synced from
            # store() / delete() — instead of `content='memories'`
            # because:
            #
            #   - Our primary key is TEXT not INTEGER, so the rowid
            #     mapping FTS expects (`content_rowid='rowid'`)
            #     would point at SQLite's implicit rowid which is
            #     unstable across VACUUM. Contentless avoids that
            #     class of sync bug entirely.
            #   - Storage cost is small (we duplicate key+value
            #     text into the FTS index) but search latency drops
            #     from O(n) full-text scan to O(log n) prefix lookup.
            #
            # Tokenizer: porter (English stemming) + unicode61 (case
            # folding + punctuation handling). Same defaults sqlite3's
            # docs recommend for general English text.
            try:
                c.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                    USING fts5(
                        id UNINDEXED,
                        key,
                        value,
                        scope UNINDEXED,
                        tokenize='porter unicode61'
                    )
                    """
                )
                self._fts_available = True
            except sqlite3.OperationalError as exc:
                # FTS5 not compiled into this sqlite3 build (rare on
                # macOS Homebrew Pythons, common on stripped-down
                # Linux containers). Continue without it — vector-only
                # search degrades gracefully.
                logger.warning(
                    "memory_store: FTS5 unavailable (%s) — falling back "
                    "to vector-only search",
                    exc,
                )
                self._fts_available = False
                return

            # Backfill: if FTS is empty but memories has rows
            # (upgrade from pre-FTS deploy), populate from existing.
            existing_count = c.execute(
                "SELECT COUNT(*) FROM memories_fts"
            ).fetchone()[0]
            mem_count = c.execute(
                "SELECT COUNT(*) FROM memories"
            ).fetchone()[0]
            if existing_count == 0 and mem_count > 0:
                logger.info(
                    "memory_store: backfilling FTS5 index from "
                    "%d existing memories",
                    mem_count,
                )
                c.execute(
                    "INSERT INTO memories_fts (id, key, value, scope) "
                    "SELECT id, key, value, scope FROM memories"
                )

    @staticmethod
    def _now_iso() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    @staticmethod
    def _pack(vec: list[float]) -> bytes:
        return struct.pack(f"{len(vec)}f", *vec)

    @staticmethod
    def _unpack(blob: bytes, dims: int) -> list[float]:
        return list(struct.unpack(f"{dims}f", blob))

    @staticmethod
    def _fts_safe_query(query: str) -> str:
        """Sanitize an operator-typed query for FTS5 MATCH.

        FTS5 has its own little query DSL — `*` is prefix match, `:` is
        column scope, `"..."` is phrase, AND/OR/NEAR are operators. Most
        operator queries are bare keyword strings ("firewall destination",
        "10.10.0.5"), but pathological inputs (`*` alone, `:` mid-token,
        unmatched quotes) cause SQLite to error.

        Rather than parse the operator's intent, we conservatively quote
        each whitespace-separated token as a phrase, dropping ones that
        contain only special chars. Result: search behaves like AND-of-
        phrases, which matches operator expectation for "did we see
        this IP" / "what did we test against vendor X."

        Examples:
          "firewall destination"     → '"firewall" "destination"'
          "10.10.0.5"                → '"10.10.0.5"'
          "  *  "                    → '' (caller falls back to vector-only)
          'tech_stack:firewall'      → '"tech_stack" "firewall"'  (the `:`
                                       acts as a delimiter — operator
                                       likely typed the canonical key
                                       name, both halves are useful
                                       tokens for FTS).
        """
        if not query:
            return ""
        # Split on whitespace AND FTS-tokenizer-delimiters. Dots
        # are explicitly delimiters: porter+unicode61 splits "10.0.0.1"
        # into ["10", "0", "0", "1"] when indexing, so we must split
        # the query the same way to match. We keep `_` and `-` since
        # the default tokenizer treats them as letters.
        tokens: list[str] = []
        current: list[str] = []
        for ch in query:
            if ch.isalnum() or ch in "_-":
                current.append(ch)
            else:
                if current:
                    tokens.append("".join(current))
                    current = []
        if current:
            tokens.append("".join(current))
        usable = [t for t in tokens if any(c.isalnum() for c in t)]
        if not usable:
            return ""
        quoted = [f'"{t}"' for t in usable]
        return " ".join(quoted)

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        # Embedder returns L2-normalized vectors; cosine == dot product.
        # Defense-in-depth: re-normalize one factor in case a future
        # embedder doesn't pre-normalize.
        norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
        return sum(x * y for x, y in zip(a, b)) / norm_b

    # ─── CRUD ──────────────────────────────────────────────────

    def store(
        self,
        *,
        key: str,
        value: str,
        scope: str = "agent",
        ttl_seconds: int | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Memory:
        """Insert or update a memory row keyed by (key, scope).

        Re-stores update value/meta/ttl AND re-embed (since the value
        text may have changed). Idempotent: re-storing identical
        content is fine, just bumps `updated_at`.
        """
        if not key or not isinstance(key, str):
            raise ValueError("key must be a non-empty string")
        if not isinstance(value, str):
            raise ValueError("value must be a string")
        scope = scope or "agent"
        now = self._now_iso()
        embedding = self._embedder.embed(value)
        if len(embedding) != self._embedder.dims:
            raise RuntimeError(
                f"embedder returned {len(embedding)} dims; expected {self._embedder.dims}"
            )
        embedding_blob = self._pack(embedding)
        meta_dict = dict(meta or {})
        with self._lock, self._conn() as c:
            existing = c.execute(
                "SELECT id, created_at FROM memories WHERE key = ? AND scope = ?",
                (key, scope),
            ).fetchone()
            if existing:
                mid = existing["id"]
                created_at = existing["created_at"]
                c.execute(
                    "UPDATE memories SET value = ?, updated_at = ?, "
                    "ttl_seconds = ?, embedding = ?, meta_json = ? "
                    "WHERE id = ?",
                    (value, now, ttl_seconds, embedding_blob,
                     json.dumps(meta_dict), mid),
                )
                # Phase 4.3 — keep FTS5 in sync. Contentless table, so
                # we can't rely on triggers; manual delete-then-insert
                # is the FTS5-recommended pattern for re-indexing a row.
                if self._fts_available:
                    c.execute(
                        "DELETE FROM memories_fts WHERE id = ?", (mid,)
                    )
                    c.execute(
                        "INSERT INTO memories_fts (id, key, value, scope) "
                        "VALUES (?, ?, ?, ?)",
                        (mid, key, value, scope),
                    )
                action = "update"
            else:
                mid = str(uuid.uuid4())
                created_at = now
                c.execute(
                    "INSERT INTO memories "
                    "(id, key, value, scope, created_at, updated_at, "
                    " ttl_seconds, embedding, meta_json) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (mid, key, value, scope, now, now, ttl_seconds,
                     embedding_blob, json.dumps(meta_dict)),
                )
                if self._fts_available:
                    c.execute(
                        "INSERT INTO memories_fts (id, key, value, scope) "
                        "VALUES (?, ?, ?, ?)",
                        (mid, key, value, scope),
                    )
                action = "insert"

        # Audit (writes are higher-value forensic events than reads).
        from usecase.audit_log import ACTION_MEMORY_STORED, record_event
        record_event(
            ACTION_MEMORY_STORED,
            target=f"memory:{mid}",
            status="success",
            metadata={
                "memory_id": mid,
                "key": key,
                "scope": scope,
                "value_chars": len(value),
                "ttl_seconds": ttl_seconds,
                "action": action,
            },
        )
        return Memory(
            id=mid, key=key, value=value, scope=scope,
            created_at=created_at, updated_at=now,
            ttl_seconds=ttl_seconds, meta=meta_dict,
        )

    def get(self, *, key: str, scope: str = "agent") -> Memory | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                f"SELECT * FROM memories WHERE key = ? AND scope = ? "
                f"AND {_NOT_EXPIRED_SQL}",
                (key, scope),
            ).fetchone()
        return self._row_to_memory(row) if row else None

    def get_by_id(self, memory_id: str) -> Memory | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                f"SELECT * FROM memories WHERE id = ? AND {_NOT_EXPIRED_SQL}",
                (memory_id,),
            ).fetchone()
        return self._row_to_memory(row) if row else None

    def list_all(
        self,
        *,
        scope: str | None = None,
        scope_prefix: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Memory]:
        # #MEM-F3 — always exclude expired rows from listings.
        # #MEM-F13 — `scope_prefix` matches scope LIKE '<prefix>%' so the UI's
        # "session" tab can list the dynamic `session:<uuid>` rows (the literal
        # scope "session" has no entries — context_assembler writes
        # scope=f"session:{id}"). When both scope and scope_prefix are given,
        # scope_prefix wins (the caller wants the family, not the literal).
        clauses, params = [_NOT_EXPIRED_SQL], []
        if scope_prefix is not None:
            clauses.append("scope LIKE ? ESCAPE '\\'")
            # Escape LIKE wildcards in the caller-supplied prefix.
            safe = (
                scope_prefix.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            params.append(f"{safe}%")
        elif scope is not None:
            clauses.append("scope = ?")
            params.append(scope)
        where = "WHERE " + " AND ".join(clauses)
        params.extend([max(1, min(limit, 500)), max(0, offset)])
        with self._lock, self._conn() as c:
            rows = c.execute(
                f"SELECT * FROM memories {where} "
                "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def delete(self, *, key: str, scope: str = "agent") -> bool:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT id FROM memories WHERE key = ? AND scope = ?",
                (key, scope),
            ).fetchone()
            if row is None:
                return False
            mid = row["id"]
            c.execute("DELETE FROM memories WHERE id = ?", (mid,))
            if self._fts_available:
                c.execute("DELETE FROM memories_fts WHERE id = ?", (mid,))
        from usecase.audit_log import ACTION_MEMORY_DELETED, record_event
        record_event(
            ACTION_MEMORY_DELETED,
            target=f"memory:{mid}",
            status="success",
            metadata={"memory_id": mid, "key": key, "scope": scope},
        )
        return True

    # ─── Search ────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        scope: str | None = None,
        min_score: float = 0.0,
        mmr_lambda: float = 0.7,
        temporal_decay_lambda: float = 0.01,
        mode: str | None = None,
    ) -> list[tuple[Memory, float]]:
        """Top-K hybrid-relevance memory search.

        Pipeline:
          1. Score every row by cosine similarity to the query embedding.
          2. (Phase 4.2) Apply temporal decay: score *= exp(-age_days × λ_decay).
             Default λ=0.01 → half-life ~70 days. Recent memories outrank
             older ones at equal cosine, but old-and-very-relevant still
             wins over new-but-tangential.
          3. (Phase 4.1) Greedy MMR rerank for diversity. λ_mmr=0.7 means
             70% relevance / 30% diversity. Avoids the near-duplicate
             dilution problem (5 entries that all say roughly the same
             thing crowd out useful info further down).
          4. Slice to `limit`.

        Returns (Memory, score) tuples sorted by their MMR-adjusted
        score. Score is post-decay-and-MMR; for raw cosine, set
        mmr_lambda=1.0 and temporal_decay_lambda=0.0.

        Args:
          query: Free-form text to match against. Embedded once.
          limit: Max results returned. Soft-capped at 100.
          scope: Restrict to this scope; None searches all scopes.
          min_score: Threshold on cosine (BEFORE decay+MMR) — filters
            out clearly-unrelated rows before the more expensive
            ranking steps.
          mmr_lambda: Diversity weighting. 1.0 = pure relevance (no
            diversification), 0.0 = pure diversity (max-cover-style),
            0.7 default (relevance-favoring).
          temporal_decay_lambda: Recency weighting per day of age.
            0.01 default (half-life ~70 days), 0.0 disables.
          mode: #MEM-F4 — discriminator for the memory_searched audit row,
            mirroring kb_searched's mode field: "active" (agent memory_search
            tool / operator REST search) vs "passive" (per-turn ContextAssembler
            injection). None → recorded as "active" (the default caller).

        Notes:
          - When `scope` is None, search ALL scopes (useful for the
            agent's "what do I know about X" query).
          - When `scope` is set, restrict to that scope. Common cases:
            "agent" (cross-session memory), "session:<id>" (this
            conversation only).
        """
        if not isinstance(query, str) or not query.strip():
            return []
        query_vec = self._embedder.embed(query)
        # #MEM-F3 — exclude expired rows from the candidate pool so they can't
        # surface in search results between reaper runs.
        clauses, params = [_NOT_EXPIRED_SQL], []
        if scope is not None:
            clauses.append("scope = ?")
            params.append(scope)
        where = "WHERE " + " AND ".join(clauses)

        # Phase 4.3 — hybrid candidate gathering. The vector query
        # below scans all rows (n is small for SOC ops; brute-force is
        # fine). FTS5 contributes its own top-K candidates on top — for
        # exact-token queries (UUIDs, hostnames, IP addresses) the
        # embedder misses, the FTS branch surfaces them.
        #
        # We don't hard-merge scores here; instead, we union the
        # candidate sets by id (vector ∪ FTS), then let the cosine +
        # decay scoring + MMR rerank below produce the final order.
        # The FTS contribution is "guarantee these rows make the
        # candidate pool"; ranking is still embedder-driven.
        fts_promoted_ids: set[str] = set()
        fts_query = self._fts_safe_query(query) if self._fts_available else ""
        if fts_query:
            try:
                fts_clauses = ["memories_fts MATCH ?"]
                fts_params = [fts_query]
                if scope is not None:
                    fts_clauses.append("scope = ?")
                    fts_params.append(scope)
                fts_where = " AND ".join(fts_clauses)
                with self._lock, self._conn() as c:
                    fts_rows = c.execute(
                        f"SELECT id FROM memories_fts WHERE {fts_where} "
                        f"ORDER BY bm25(memories_fts) LIMIT ?",
                        [*fts_params, max(1, min(limit * 3, 50))],
                    ).fetchall()
                fts_promoted_ids = {r["id"] for r in fts_rows}
            except sqlite3.OperationalError as exc:
                # Bad MATCH syntax (rare after sanitization) → log +
                # degrade to vector-only. Empty-query case skipped
                # before the try.
                logger.warning("memory_store: FTS5 query failed (%s)", exc)

        with self._lock, self._conn() as c:
            rows = c.execute(
                f"SELECT * FROM memories {where}", params
            ).fetchall()

        # ── Cosine + temporal-decay scoring ────────────────────
        # Hold the embedding vector alongside score for the MMR pass
        # below. Stripped before return.
        now_epoch = time.time()
        # 4-tuple: (Memory, adjusted_score, vec, is_fts_match). The vec is
        # used by the MMR pass; is_fts_match (#MEM-F5) rides through to the
        # returned tuples so the UI "FTS hit" badge can render.
        scored: list[tuple[Memory, float, list[float], bool]] = []
        dims = self._embedder.dims
        for row in rows:
            try:
                vec = self._unpack(row["embedding"], dims)
            except struct.error:
                continue
            cosine = self._cosine(query_vec, vec)
            # Phase 4.3 — FTS-promoted rows skip the min_score gate.
            # An exact-keyword match (e.g., a UUID or IP) can have very
            # low cosine because the embedder doesn't model bare
            # identifiers, but the operator obviously wants it back.
            is_fts_match = row["id"] in fts_promoted_ids
            if cosine < min_score and not is_fts_match:
                continue
            mem = self._row_to_memory(row)
            # Phase 4.2 — temporal decay on `updated_at`. We use updated_at
            # not created_at: a stored memory that's been re-confirmed
            # (re-stored) effectively resets its decay clock, which
            # matches operator intuition ("the operator just told me
            # this again — it's still current").
            decay_factor = 1.0
            if temporal_decay_lambda > 0.0 and mem.updated_at:
                try:
                    # updated_at is ISO-8601 with `Z` or `+00:00` suffix.
                    iso = mem.updated_at.replace("Z", "+00:00")
                    updated_epoch = datetime.fromisoformat(iso).timestamp()
                    age_days = max(0.0, (now_epoch - updated_epoch) / 86400.0)
                    decay_factor = math.exp(-age_days * temporal_decay_lambda)
                except (ValueError, AttributeError):
                    # Bad timestamp — keep the default 1.0 factor.
                    pass
            adjusted_score = cosine * decay_factor
            scored.append((mem, adjusted_score, vec, is_fts_match))

        # Sort by adjusted score (relevance + recency) and trim to a
        # candidate pool larger than `limit` so MMR has room to pick
        # diverse winners. 3× limit is the standard heuristic.
        scored.sort(key=lambda x: x[1], reverse=True)
        candidate_pool_size = max(1, min(limit * 3, 100))
        candidates = scored[:candidate_pool_size]

        # ── Phase 4.1 — MMR rerank ─────────────────────────────
        final = self._apply_mmr(
            candidates, limit=limit, mmr_lambda=mmr_lambda,
        )

        from usecase.audit_log import ACTION_MEMORY_SEARCHED, record_event
        # #MEM-F2 — when scope is "session:<id>" derive the session_id so the
        # memory_searched row is linkable to a conversation; cross-session
        # searches (scope=None) leave it None. turn_id isn't available at the
        # store layer (no turn context propagates here) — the caller's tool_call
        # row carries the turn linkage for the active path.
        session_id = (
            scope.split(":", 1)[1]
            if isinstance(scope, str) and scope.startswith("session:")
            else None
        )
        record_event(
            ACTION_MEMORY_SEARCHED,
            target="memory:_search_",
            status="success",
            metadata={
                "query_chars": len(query),
                # #MEM-F2 — bounded query preview so "what was searched?" is
                # answerable for the passive path too (no tool_call row there).
                "query_preview": query[:200],
                "scope": scope,
                "session_id": session_id,
                # #MEM-F4 — active (agent tool / REST) vs passive (per-turn
                # ContextAssembler) discriminator, like kb_searched's mode.
                "mode": mode or "active",
                "limit": limit,
                "result_count": len(final),
                "top_score": final[0][1] if final else None,
                "mmr_lambda": mmr_lambda,
                "temporal_decay_lambda": temporal_decay_lambda,
            },
        )
        return final

    @staticmethod
    def _apply_mmr(
        candidates: list[tuple[Memory, float, list[float], bool]],
        *,
        limit: int,
        mmr_lambda: float = 0.7,
    ) -> list[tuple[Memory, float, bool]]:
        """Greedy MMR (Maximal Marginal Relevance) selection.

        At each step, pick the candidate that maximizes:
            λ × relevance_score - (1 - λ) × max_similarity_to_already_picked

        First pick is pure relevance (nothing to diversify against yet).
        Subsequent picks balance new-information vs already-known.

        Returns (Memory, score, fts_promoted) tuples — vectors stripped —
        in selection order. #MEM-F5 — the fts_promoted flag rides through
        so the search() caller can surface it to the UI badge.

        Edge cases:
          - mmr_lambda >= 1.0 → degenerate to pure relevance (no
            diversity penalty); fast-path returns the slice as-is.
          - <= 1 candidate → pass through unchanged.
        """
        if mmr_lambda >= 1.0 or len(candidates) <= 1:
            return [(m, s, fts) for m, s, _, fts in candidates[:limit]]

        remaining = list(candidates)
        selected: list[tuple[Memory, float, list[float], bool]] = []
        target = max(1, min(limit, len(remaining)))

        while remaining and len(selected) < target:
            best_idx = 0
            best_mmr = float("-inf")
            for i, (_mem, score, vec, _fts) in enumerate(remaining):
                if not selected:
                    # First pick: pure relevance — diversity term is 0.
                    mmr_score = mmr_lambda * score
                else:
                    max_sim_to_picked = max(
                        SqliteMemoryStore._cosine(vec, sel_vec)
                        for _, _, sel_vec, _ in selected
                    )
                    mmr_score = (
                        mmr_lambda * score
                        - (1.0 - mmr_lambda) * max_sim_to_picked
                    )
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = i
            selected.append(remaining.pop(best_idx))

        return [(m, s, fts) for m, s, _, fts in selected]

    # ─── TTL reaper ────────────────────────────────────────────

    def _reap_expired(self) -> int:
        """Delete memory rows whose TTL has passed.

        TTL is interpreted as seconds since `updated_at`. #MEM-F3 — this runs
        at boot AND now on a periodic loop (main.py async task), and emits an
        audit row + metric when it deletes anything; reads also filter expired
        rows (see _NOT_EXPIRED_SQL) so nothing leaks between sweeps.
        """
        import calendar

        now_epoch = time.time()
        deleted = 0
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT id, updated_at, ttl_seconds FROM memories "
                "WHERE ttl_seconds IS NOT NULL"
            ).fetchall()
            to_delete: list[str] = []
            for r in rows:
                ttl = r["ttl_seconds"]
                if ttl is None:
                    continue
                # Parse updated_at (ISO8601 UTC, seconds precision). Use
                # calendar.timegm so the struct_time is interpreted as UTC —
                # time.mktime() treats it as LOCAL time and the manual
                # `- time.timezone` correction broke under DST.
                try:
                    upd = time.strptime(r["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
                    upd_epoch = calendar.timegm(upd)
                except ValueError:
                    continue
                if upd_epoch + ttl < now_epoch:
                    to_delete.append(r["id"])
            for mid in to_delete:
                c.execute("DELETE FROM memories WHERE id = ?", (mid,))
                if self._fts_available:
                    c.execute("DELETE FROM memories_fts WHERE id = ?", (mid,))
                deleted += 1
        if deleted > 0:
            # #MEM-F3 — the boot-only reaper used to delete silently (log
            # only). Leave a forensic trace + a metric for the deletion.
            try:
                from usecase.audit_log import ACTION_MEMORY_DELETED, record_event
                record_event(
                    ACTION_MEMORY_DELETED,
                    target="memory:_expired_",
                    status="success",
                    actor="system",
                    metadata={"reaped_count": deleted, "trigger": "ttl_reaper"},
                )
            except Exception:  # pragma: no cover - audit best-effort
                pass
            try:
                from usecase.metrics_registry import metrics_registry
                reg = metrics_registry()
                if reg is not None:
                    reg.counter(
                        "guardian_memory_ttl_reaped_total",
                        "Total expired memory rows deleted by the TTL reaper.",
                    ).inc(float(deleted))
            except Exception:  # pragma: no cover - metric best-effort
                pass
        return deleted

    # ─── Mappers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> Memory:
        return Memory(
            id=row["id"],
            key=row["key"],
            value=row["value"],
            scope=row["scope"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            ttl_seconds=row["ttl_seconds"],
            meta=json.loads(row["meta_json"]),
        )


# ─────────────────────────────────────────────────────────────────
# Module-level singleton accessor — wired by main.py
# ─────────────────────────────────────────────────────────────────

_memory_store: SqliteMemoryStore | None = None


def set_memory_store(store: SqliteMemoryStore | None) -> None:
    global _memory_store
    _memory_store = store


def memory_store() -> SqliteMemoryStore | None:
    return _memory_store
