"""Investigation store — sqlite-backed Issues + Cases over `data_root/investigations.db`.

Guardian's own record of investigations, distinct from upstream XSOAR
incidents. An **Issue** is a unit of investigation (of a fetched XSOAR
incident or a standalone finding) created by the agent (during an
investigation, via the issue_* MCP tools) or by the operator (in the UI).
A **Case** groups related Issues. An Issue's activity timeline — what
Guardian did + found — lives in `issue_events`.

State taxonomy (root CLAUDE.md): the catalog domain — NOT credentials, NOT
operator-personal. Mutable investigation metadata the agent reads/writes and
the UI displays. So the issue_* / case_* MCP tools are agent-accessible
(catalog side of the credential guardrail).

Schema:
    issues(
      id, title, status, severity, kind, origin, source_ref, case_id,
      summary, scope, recommendations, conclusions, next_steps,
      created_at, updated_at
    )
    cases(id, title, description, status, created_at, updated_at)
    issue_events(seq AUTOINCREMENT, id, issue_id→issues.id ON DELETE CASCADE,
                 ts, type, content)

Mirrors instance_store.py (threading.Lock + sqlite3 isolation_level=None +
foreign_keys=ON, frozen DTOs, module-level singleton accessor).
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

# Allowed enums — kept liberal (free-form `kind` accepted) but the common
# values are documented for the agent + UI. Not enforced at the store layer
# (the API/tool layer can validate); the store just persists strings.
ISSUE_STATUSES = ("open", "investigating", "resolved", "closed")
ISSUE_SEVERITIES = ("low", "medium", "high", "critical")

# The structured investigation fields an Issue carries (besides core
# metadata). update_issue accepts any subset of these + status/severity/
# title/kind.
_ISSUE_TEXT_FIELDS = ("summary", "scope", "recommendations", "conclusions", "next_steps")
# v0.2.45 (stage A) — structured investigation outcome fields. verdict is one of
# ISSUE_VERDICTS; verdict_confidence is 0..1; blast_radius + report are JSON /
# markdown text. All nullable + additively migrated.
ISSUE_VERDICTS = (
    "TRUE_POSITIVE", "FALSE_POSITIVE", "BENIGN", "NEEDS_ESCALATION", "INCONCLUSIVE",
)
_ISSUE_STRUCTURED_FIELDS = ("verdict", "verdict_confidence", "blast_radius", "report")
_ISSUE_UPDATABLE = (
    "title", "status", "severity", "kind", *_ISSUE_TEXT_FIELDS, *_ISSUE_STRUCTURED_FIELDS,
)


@dataclass(frozen=True)
class Issue:
    id: str
    title: str
    status: str
    severity: str
    kind: str
    origin: str
    source_ref: str | None
    case_id: str | None
    summary: str | None
    scope: str | None
    recommendations: str | None
    conclusions: str | None
    next_steps: str | None
    verdict: str | None
    verdict_confidence: float | None
    blast_radius: str | None
    report: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TechniqueMapping:
    id: str
    issue_id: str
    technique_id: str
    tactic: str | None
    manifestation: str | None
    evidence_ref: str | None
    confidence: float | None
    created_at: str


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    description: str | None
    status: str
    # v0.2.47 (stage C) — campaign rollup, synthesized from member issues by
    # case_rollup. infrastructure + techniques are JSON strings (flexible shape);
    # campaign_summary/threat_actor/severity_rollup are plain text. Null until rolled up.
    campaign_summary: str | None
    threat_actor: str | None
    infrastructure: str | None
    techniques: str | None
    severity_rollup: str | None
    created_at: str
    updated_at: str


# v0.2.47 (stage C) — fields case_rollup / case_update may write on a Case.
_CASE_ROLLUP_FIELDS = ("campaign_summary", "threat_actor", "infrastructure",
                       "techniques", "severity_rollup")


@dataclass(frozen=True)
class IssueEvent:
    id: str
    issue_id: str
    ts: str
    type: str
    content: str


@dataclass(frozen=True)
class Indicator:
    """An IoC seen across investigations, deduped by (value, type).

    `enrichment` is a JSON string (DBotScore detail, sources, …) so the
    shape stays flexible; `source` is 'guardian' (extracted by the agent
    during investigation) or 'xsoar' (imported from the SOAR on fetch).
    """
    id: str
    value: str
    type: str
    dbot_score: int | None
    enrichment: str | None
    source: str
    first_seen: str
    last_seen: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class PlaybookMatch:
    """A structured link from an Issue to the KB playbook the investigation was
    routed through (v0.2.47) — lets cases be typed by playbook + queried."""
    id: str
    issue_id: str
    playbook_doc_id: str
    score: float | None
    matched_criteria: str | None
    created_at: str


@dataclass(frozen=True)
class CaseRelationship:
    """A typed edge between two Cases (v0.2.47): sibling / escalation / reopen /
    same-campaign. Lets the model link a new case to a prior campaign."""
    id: str
    source_case_id: str
    target_case_id: str
    relationship_type: str
    note: str | None
    created_at: str


# Common IoC types (free-form accepted; the tool/API may validate).
INDICATOR_TYPES = ("ip", "domain", "url", "file_hash", "email", "cve", "host", "account")

# v0.2.47 (stage C) — typed cross-case edge verbs (free-form accepted).
CASE_RELATIONSHIP_TYPES = ("sibling", "escalation", "reopen", "same-campaign")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class InvestigationStore:
    """Sqlite-backed store at ``<data_root>/investigations.db``."""

    def __init__(self, data_root: Path | None = None) -> None:
        self._data_root = (data_root or self._resolve_data_root()).resolve()
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_root / "investigations.db"
        self._lock = threading.Lock()
        self._init_schema()
        logger.info("InvestigationStore at %s", self._db_path)

    @staticmethod
    def _resolve_data_root() -> Path:
        return Path(os.getenv("DATA_ROOT", str(DEFAULT_DATA_ROOT)))

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
                CREATE TABLE IF NOT EXISTS cases (
                    id          TEXT PRIMARY KEY,
                    title       TEXT NOT NULL,
                    description TEXT,
                    status      TEXT NOT NULL DEFAULT 'open',
                    attack_chain_svg TEXT,
                    relations_canvas_svg TEXT,
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL
                )
                """
            )
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS issues (
                    id              TEXT PRIMARY KEY,
                    title           TEXT NOT NULL,
                    status          TEXT NOT NULL DEFAULT 'open',
                    severity        TEXT NOT NULL DEFAULT 'medium',
                    kind            TEXT NOT NULL DEFAULT 'other',
                    origin          TEXT NOT NULL DEFAULT 'agent',
                    source_ref      TEXT,
                    case_id         TEXT REFERENCES cases(id) ON DELETE SET NULL,
                    summary         TEXT,
                    scope           TEXT,
                    recommendations TEXT,
                    conclusions     TEXT,
                    next_steps      TEXT,
                    attack_chain_svg TEXT,
                    relations_canvas_svg TEXT,
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_issues_case ON issues(case_id)")
            # v0.1.8 — attack-chain SVG (migrate existing dbs that predate the
            # column). The SVG is read only on the issue DETAIL, never in the
            # list, so it doesn't bloat list_issues payloads.
            issue_cols = {r["name"] for r in c.execute("PRAGMA table_info(issues)")}
            if "attack_chain_svg" not in issue_cols:
                c.execute("ALTER TABLE issues ADD COLUMN attack_chain_svg TEXT")
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS issue_events (
                    seq      INTEGER PRIMARY KEY AUTOINCREMENT,
                    id       TEXT NOT NULL UNIQUE,
                    issue_id TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
                    ts       TEXT NOT NULL,
                    type     TEXT NOT NULL,
                    content  TEXT NOT NULL
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_events_issue ON issue_events(issue_id)")
            # v0.2.0 — Indicators (IoCs). New tables → CREATE IF NOT EXISTS
            # creates them on existing dbs too (no column migration needed).
            # Deduped by (value, type); linked M:N to issues.
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS indicators (
                    id           TEXT PRIMARY KEY,
                    value        TEXT NOT NULL,
                    type         TEXT NOT NULL,
                    dbot_score   INTEGER,
                    enrichment   TEXT,
                    source       TEXT NOT NULL DEFAULT 'guardian',
                    first_seen   TEXT NOT NULL,
                    last_seen    TEXT NOT NULL,
                    created_at   TEXT NOT NULL,
                    updated_at   TEXT NOT NULL,
                    UNIQUE(value, type)
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_indicators_type ON indicators(type)")
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS indicator_issues (
                    indicator_id TEXT NOT NULL REFERENCES indicators(id) ON DELETE CASCADE,
                    issue_id     TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
                    PRIMARY KEY (indicator_id, issue_id)
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_ind_issues_issue ON indicator_issues(issue_id)")
            # v0.2.1 — relations canvas SVG on issues (migrate existing dbs) +
            # a generic STIX-style edge table (one Relationship-SRO analog).
            issue_cols2 = {r["name"] for r in c.execute("PRAGMA table_info(issues)")}
            if "relations_canvas_svg" not in issue_cols2:
                c.execute("ALTER TABLE issues ADD COLUMN relations_canvas_svg TEXT")
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS relationships (
                    id                TEXT PRIMARY KEY,
                    source_id         TEXT NOT NULL,
                    source_type       TEXT NOT NULL,
                    target_value      TEXT NOT NULL,
                    target_type       TEXT NOT NULL,
                    relationship_type TEXT NOT NULL,
                    description       TEXT,
                    source            TEXT NOT NULL DEFAULT 'guardian',
                    first_seen        TEXT NOT NULL,
                    last_seen         TEXT NOT NULL,
                    UNIQUE(source_id, relationship_type, target_value, target_type)
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_rel_source ON relationships(source_id)")
            # v0.2.2 — case-level diagram SVGs (migrate existing dbs). A Case
            # groups multiple issues, so these are the campaign-level attack
            # chain + relations canvas synthesized across the case's issues.
            # Kept off the Case DTO, same as the issue-level columns.
            case_cols = {r["name"] for r in c.execute("PRAGMA table_info(cases)")}
            if "attack_chain_svg" not in case_cols:
                c.execute("ALTER TABLE cases ADD COLUMN attack_chain_svg TEXT")
            if "relations_canvas_svg" not in case_cols:
                c.execute("ALTER TABLE cases ADD COLUMN relations_canvas_svg TEXT")
            # v0.2.45 (stage A) — structured investigation outcome on issues
            # (migrate existing dbs) + a queryable issue<->ATT&CK technique table.
            issue_cols3 = {r["name"] for r in c.execute("PRAGMA table_info(issues)")}
            if "verdict" not in issue_cols3:
                c.execute("ALTER TABLE issues ADD COLUMN verdict TEXT")
            if "verdict_confidence" not in issue_cols3:
                c.execute("ALTER TABLE issues ADD COLUMN verdict_confidence REAL")
            if "blast_radius" not in issue_cols3:
                c.execute("ALTER TABLE issues ADD COLUMN blast_radius TEXT")
            if "report" not in issue_cols3:
                c.execute("ALTER TABLE issues ADD COLUMN report TEXT")
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS technique_mappings (
                    id            TEXT PRIMARY KEY,
                    issue_id      TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
                    technique_id  TEXT NOT NULL,
                    tactic        TEXT,
                    manifestation TEXT,
                    evidence_ref  TEXT,
                    confidence    REAL,
                    created_at    TEXT NOT NULL,
                    UNIQUE(issue_id, technique_id)
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_techmap_issue ON technique_mappings(issue_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_techmap_tech ON technique_mappings(technique_id)")
            # v0.2.47 (stage C) — campaign rollup columns on cases (migrate existing
            # dbs) + a playbook-match table + a typed cross-case edge table.
            case_cols2 = {r["name"] for r in c.execute("PRAGMA table_info(cases)")}
            for col in ("campaign_summary", "threat_actor", "infrastructure",
                        "techniques", "severity_rollup"):
                if col not in case_cols2:
                    c.execute(f"ALTER TABLE cases ADD COLUMN {col} TEXT")
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS playbook_matches (
                    id               TEXT PRIMARY KEY,
                    issue_id         TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
                    playbook_doc_id  TEXT NOT NULL,
                    score            REAL,
                    matched_criteria TEXT,
                    created_at       TEXT NOT NULL,
                    UNIQUE(issue_id, playbook_doc_id)
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_pbmatch_issue ON playbook_matches(issue_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_pbmatch_doc ON playbook_matches(playbook_doc_id)")
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS case_relationships (
                    id                TEXT PRIMARY KEY,
                    source_case_id    TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                    target_case_id    TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
                    relationship_type TEXT NOT NULL,
                    note              TEXT,
                    created_at        TEXT NOT NULL,
                    UNIQUE(source_case_id, target_case_id, relationship_type)
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_caserel_src ON case_relationships(source_case_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_caserel_tgt ON case_relationships(target_case_id)")

    # ─── Issues ────────────────────────────────────────────────────

    def create_issue(
        self,
        title: str,
        kind: str = "other",
        severity: str = "medium",
        origin: str = "agent",
        source_ref: str | None = None,
        scope: str | None = None,
        summary: str | None = None,
    ) -> Issue:
        if not title or not isinstance(title, str):
            raise ValueError("title must be a non-empty string")
        ts = _now()
        issue = Issue(
            id=str(uuid.uuid4()),
            title=title,
            status="open",
            severity=severity or "medium",
            kind=kind or "other",
            origin=origin or "agent",
            source_ref=source_ref,
            case_id=None,
            summary=summary,
            scope=scope,
            recommendations=None,
            conclusions=None,
            next_steps=None,
            verdict=None,
            verdict_confidence=None,
            blast_radius=None,
            report=None,
            created_at=ts,
            updated_at=ts,
        )
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO issues (id, title, status, severity, kind, origin, "
                "source_ref, case_id, summary, scope, recommendations, conclusions, "
                "next_steps, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    issue.id, issue.title, issue.status, issue.severity, issue.kind,
                    issue.origin, issue.source_ref, issue.case_id, issue.summary,
                    issue.scope, issue.recommendations, issue.conclusions,
                    issue.next_steps, issue.created_at, issue.updated_at,
                ),
            )
        logger.info("InvestigationStore.create_issue id=%s kind=%s", issue.id, issue.kind)
        return issue

    def get_issue(self, issue_id: str) -> Issue | None:
        with self._lock, self._conn() as c:
            row = c.execute("SELECT * FROM issues WHERE id = ?", (issue_id,)).fetchone()
        return self._row_to_issue(row) if row else None

    def list_issues(
        self, status: str | None = None, case_id: str | None = None,
        source_ref_not_null: bool = False, order: str = "desc",
    ) -> list[Issue]:
        """List issues, optionally filtered + ordered.

        source_ref_not_null=True excludes Issues with an empty/NULL
        source_ref — manual/standalone Issues with no XSOAR incident to
        fetch. The autonomous investigation loop sets this so a sourceless
        Issue can never jam its "oldest open" pick (v0.2.11).

        order="asc" sorts oldest-first by created_at (what the loop needs to
        deterministically take the OLDEST open Issue); the default "desc"
        preserves the original newest-first ordering for the UI.
        """
        clauses: list[str] = []
        params: list[str] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if case_id:
            clauses.append("case_id = ?")
            params.append(case_id)
        if source_ref_not_null:
            clauses.append("source_ref IS NOT NULL AND TRIM(source_ref) != ''")
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        order_by = (
            "created_at ASC, updated_at ASC"
            if str(order).lower() == "asc"
            else "updated_at DESC, created_at DESC"
        )
        with self._lock, self._conn() as c:
            rows = c.execute(
                f"SELECT * FROM issues{where} ORDER BY {order_by}",
                params,
            ).fetchall()
        return [self._row_to_issue(r) for r in rows]

    def update_issue(self, issue_id: str, **fields) -> Issue | None:
        """Partial update: any of title/status/severity/kind/summary/scope/
        recommendations/conclusions/next_steps. Unknown keys ignored. None
        values skipped (leave that field alone)."""
        sets: list[str] = []
        params: list[str] = []
        for key in _ISSUE_UPDATABLE:
            if key in fields and fields[key] is not None:
                sets.append(f"{key} = ?")
                params.append(fields[key])
        if not sets:
            return self.get_issue(issue_id)
        sets.append("updated_at = ?")
        params.append(_now())
        params.append(issue_id)
        with self._lock, self._conn() as c:
            cur = c.execute(
                f"UPDATE issues SET {', '.join(sets)} WHERE id = ?", params,
            )
            if cur.rowcount == 0:
                return None
        return self.get_issue(issue_id)

    def delete_issue(self, issue_id: str) -> bool:
        # #INV-F14 — a hard delete cascades issue_events via ON DELETE CASCADE,
        # destroying the only forensic record of what existed. Capture the
        # issue's identifying fields and emit an `issue_deleted` audit row
        # BEFORE the DELETE so /observability/events records what was removed.
        existing = self.get_issue(issue_id)
        with self._lock, self._conn() as c:
            cur = c.execute("DELETE FROM issues WHERE id = ?", (issue_id,))
        deleted = cur.rowcount > 0
        if deleted:
            try:
                from usecase.audit_log import record_event
                meta = {"issue_id": issue_id}
                if existing is not None:
                    meta.update({
                        "title": getattr(existing, "title", None),
                        "kind": getattr(existing, "kind", None),
                        "status": getattr(existing, "status", None),
                        "severity": getattr(existing, "severity", None),
                        "case_id": getattr(existing, "case_id", None),
                    })
                record_event(
                    "issue_deleted",
                    target=f"issue:{issue_id}",
                    status="success",
                    metadata=meta,
                )
            except Exception:  # noqa: BLE001 — audit is best-effort
                pass
        return deleted

    # ─── Technique mappings (issue <-> ATT&CK) ──────────────────────

    def add_technique_mapping(
        self, issue_id: str, technique_id: str, tactic: str | None = None,
        manifestation: str | None = None, evidence_ref: str | None = None,
        confidence: float | None = None,
    ) -> TechniqueMapping:
        """Upsert an issue->technique mapping (dedup on issue_id+technique_id).
        Re-adding the same technique updates the provided fields, preserving any
        prior non-null values for fields left None."""
        ts = _now()
        with self._lock, self._conn() as c:
            c.execute(
                """
                INSERT INTO technique_mappings
                    (id, issue_id, technique_id, tactic, manifestation, evidence_ref, confidence, created_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(issue_id, technique_id) DO UPDATE SET
                    tactic        = COALESCE(excluded.tactic, technique_mappings.tactic),
                    manifestation = COALESCE(excluded.manifestation, technique_mappings.manifestation),
                    evidence_ref  = COALESCE(excluded.evidence_ref, technique_mappings.evidence_ref),
                    confidence    = COALESCE(excluded.confidence, technique_mappings.confidence)
                """,
                (str(uuid.uuid4()), issue_id, technique_id, tactic, manifestation,
                 evidence_ref, confidence, ts),
            )
            row = c.execute(
                "SELECT * FROM technique_mappings WHERE issue_id = ? AND technique_id = ?",
                (issue_id, technique_id),
            ).fetchone()
        return self._row_to_technique(row)

    def list_technique_mappings(self, issue_id: str) -> list[TechniqueMapping]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM technique_mappings WHERE issue_id = ? ORDER BY created_at ASC, technique_id ASC",
                (issue_id,),
            ).fetchall()
        return [self._row_to_technique(r) for r in rows]

    def list_issues_by_technique(self, technique_id: str) -> list[Issue]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT i.* FROM issues i JOIN technique_mappings tm ON tm.issue_id = i.id "
                "WHERE tm.technique_id = ? ORDER BY i.updated_at DESC",
                (technique_id,),
            ).fetchall()
        return [self._row_to_issue(r) for r in rows]

    @staticmethod
    def _row_to_technique(row: sqlite3.Row) -> TechniqueMapping:
        return TechniqueMapping(
            id=row["id"], issue_id=row["issue_id"], technique_id=row["technique_id"],
            tactic=row["tactic"], manifestation=row["manifestation"],
            evidence_ref=row["evidence_ref"], confidence=row["confidence"],
            created_at=row["created_at"],
        )

    # ─── Playbook matches (stage C) ────────────────────────────────

    def add_playbook_match(self, issue_id: str, playbook_doc_id: str,
                           score: float | None = None,
                           matched_criteria: str | None = None) -> PlaybookMatch:
        """Record (upsert) the KB playbook an investigation was routed through.
        Re-asserting the same (issue, playbook) updates the score/criteria
        (COALESCE keeps a prior value when the new one is None)."""
        ts = _now()
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO playbook_matches (id, issue_id, playbook_doc_id, score, "
                "matched_criteria, created_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(issue_id, playbook_doc_id) DO UPDATE SET "
                "score = COALESCE(excluded.score, playbook_matches.score), "
                "matched_criteria = COALESCE(excluded.matched_criteria, playbook_matches.matched_criteria)",
                (str(uuid.uuid4()), issue_id, playbook_doc_id, score, matched_criteria, ts),
            )
            row = c.execute(
                "SELECT * FROM playbook_matches WHERE issue_id = ? AND playbook_doc_id = ?",
                (issue_id, playbook_doc_id),
            ).fetchone()
        return self._row_to_playbook_match(row)

    def list_playbook_matches(self, issue_id: str) -> list[PlaybookMatch]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM playbook_matches WHERE issue_id = ? ORDER BY score DESC, created_at",
                (issue_id,),
            ).fetchall()
        return [self._row_to_playbook_match(r) for r in rows]

    def list_issues_by_playbook(self, playbook_doc_id: str) -> list[Issue]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT i.* FROM issues i JOIN playbook_matches pm ON pm.issue_id = i.id "
                "WHERE pm.playbook_doc_id = ? ORDER BY i.updated_at DESC",
                (playbook_doc_id,),
            ).fetchall()
        return [self._row_to_issue(r) for r in rows]

    @staticmethod
    def _row_to_playbook_match(row: sqlite3.Row) -> PlaybookMatch:
        return PlaybookMatch(
            id=row["id"], issue_id=row["issue_id"], playbook_doc_id=row["playbook_doc_id"],
            score=row["score"], matched_criteria=row["matched_criteria"],
            created_at=row["created_at"],
        )

    # ─── Case relationships (stage C) ──────────────────────────────

    def add_case_relationship(self, source_case_id: str, target_case_id: str,
                              relationship_type: str, note: str | None = None) -> CaseRelationship:
        """Record (upsert) a typed edge between two cases. Re-asserting the same
        (source, type, target) updates the note."""
        ts = _now()
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO case_relationships (id, source_case_id, target_case_id, "
                "relationship_type, note, created_at) VALUES (?,?,?,?,?,?) "
                "ON CONFLICT(source_case_id, target_case_id, relationship_type) DO UPDATE SET "
                "note = COALESCE(excluded.note, case_relationships.note)",
                (str(uuid.uuid4()), source_case_id, target_case_id, relationship_type, note, ts),
            )
            row = c.execute(
                "SELECT * FROM case_relationships WHERE source_case_id = ? AND "
                "target_case_id = ? AND relationship_type = ?",
                (source_case_id, target_case_id, relationship_type),
            ).fetchone()
        return self._row_to_case_relationship(row)

    def list_case_relationships(self, case_id: str) -> list[CaseRelationship]:
        """Every edge touching this case (as source OR target)."""
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM case_relationships WHERE source_case_id = ? OR target_case_id = ? "
                "ORDER BY created_at",
                (case_id, case_id),
            ).fetchall()
        return [self._row_to_case_relationship(r) for r in rows]

    @staticmethod
    def _row_to_case_relationship(row: sqlite3.Row) -> CaseRelationship:
        return CaseRelationship(
            id=row["id"], source_case_id=row["source_case_id"],
            target_case_id=row["target_case_id"], relationship_type=row["relationship_type"],
            note=row["note"], created_at=row["created_at"],
        )

    def set_attack_chain(self, issue_id: str, svg: str | None) -> bool:
        """Store (or clear, with None) the issue's attack-chain SVG.

        Kept off the Issue DTO so list_issues stays lean; read back via
        get_attack_chain and surfaced only on the issue detail response.
        """
        with self._lock, self._conn() as c:
            cur = c.execute(
                "UPDATE issues SET attack_chain_svg = ?, updated_at = ? WHERE id = ?",
                (svg, _now(), issue_id),
            )
        return cur.rowcount > 0

    def get_attack_chain(self, issue_id: str) -> str | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT attack_chain_svg FROM issues WHERE id = ?", (issue_id,)
            ).fetchone()
        return row["attack_chain_svg"] if row else None

    # ─── Case-level diagram SVGs (v0.2.2) ──────────────────────────
    # Campaign-level attack chain + relations canvas, synthesized across the
    # case's issues. Mirror the issue-level columns; kept off the Case DTO so
    # list_cases stays lean (read back only on the case detail).

    def set_case_attack_chain(self, case_id: str, svg: str | None) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute(
                "UPDATE cases SET attack_chain_svg = ?, updated_at = ? WHERE id = ?",
                (svg, _now(), case_id),
            )
        return cur.rowcount > 0

    def get_case_attack_chain(self, case_id: str) -> str | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT attack_chain_svg FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
        return row["attack_chain_svg"] if row else None

    def set_case_relations_canvas(self, case_id: str, svg: str | None) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute(
                "UPDATE cases SET relations_canvas_svg = ?, updated_at = ? WHERE id = ?",
                (svg, _now(), case_id),
            )
        return cur.rowcount > 0

    def get_case_relations_canvas(self, case_id: str) -> str | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT relations_canvas_svg FROM cases WHERE id = ?", (case_id,)
            ).fetchone()
        return row["relations_canvas_svg"] if row else None

    # ─── Cases ─────────────────────────────────────────────────────

    def create_case(self, title: str, description: str | None = None) -> Case:
        if not title or not isinstance(title, str):
            raise ValueError("title must be a non-empty string")
        ts = _now()
        case = Case(
            id=str(uuid.uuid4()),
            title=title,
            description=description,
            status="open",
            campaign_summary=None,
            threat_actor=None,
            infrastructure=None,
            techniques=None,
            severity_rollup=None,
            created_at=ts,
            updated_at=ts,
        )
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO cases (id, title, description, status, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?)",
                (case.id, case.title, case.description, case.status, case.created_at, case.updated_at),
            )
        logger.info("InvestigationStore.create_case id=%s", case.id)
        return case

    def get_case(self, case_id: str) -> Case | None:
        with self._lock, self._conn() as c:
            row = c.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        return self._row_to_case(row) if row else None

    def list_cases(self) -> list[dict]:
        """Cases with an `issue_count` (for the case list UI).

        Single-pass LEFT JOIN + GROUP BY rather than a correlated
        `(SELECT COUNT(*) …)` per case (which was N+1 at the SQL level —
        1 outer + 1 per case — and made the Cases list noticeably slower
        than the Issues list). `c.*` columns are functionally dependent on
        the GROUP BY key (`c.id`, the primary key) so SQLite returns them
        deterministically. The `issues(case_id)` index backs the join.
        Response shape is unchanged: case fields + an `issue_count` key.
        """
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT c.*, COUNT(i.id) AS issue_count "
                "FROM cases c LEFT JOIN issues i ON i.case_id = c.id "
                "GROUP BY c.id "
                "ORDER BY c.updated_at DESC, c.created_at DESC"
            ).fetchall()
        out: list[dict] = []
        for r in rows:
            case = self._row_to_case(r)
            out.append({**case.__dict__, "issue_count": int(r["issue_count"])})
        return out

    def update_case(self, case_id: str, **fields) -> Case | None:
        sets: list[str] = []
        params: list[str] = []
        for key in ("title", "description", "status", *_CASE_ROLLUP_FIELDS):
            if key in fields and fields[key] is not None:
                sets.append(f"{key} = ?")
                params.append(fields[key])
        if not sets:
            return self.get_case(case_id)
        sets.append("updated_at = ?")
        params.append(_now())
        params.append(case_id)
        with self._lock, self._conn() as c:
            cur = c.execute(f"UPDATE cases SET {', '.join(sets)} WHERE id = ?", params)
            if cur.rowcount == 0:
                return None
        return self.get_case(case_id)

    def delete_case(self, case_id: str) -> bool:
        # issues.case_id → ON DELETE SET NULL (issues survive, ungrouped).
        # #INV-F14 — capture the case identity and emit `case_deleted` before
        # the DELETE so the destruction of a case grouping is traceable.
        existing = self.get_case(case_id)
        with self._lock, self._conn() as c:
            cur = c.execute("DELETE FROM cases WHERE id = ?", (case_id,))
        deleted = cur.rowcount > 0
        if deleted:
            try:
                from usecase.audit_log import record_event
                meta = {"case_id": case_id}
                if existing is not None:
                    meta.update({
                        "title": getattr(existing, "title", None),
                        "status": getattr(existing, "status", None),
                    })
                record_event(
                    "case_deleted",
                    target=f"case:{case_id}",
                    status="success",
                    metadata=meta,
                )
            except Exception:  # noqa: BLE001 — audit is best-effort
                pass
        return deleted

    # ─── Membership ────────────────────────────────────────────────

    def add_issue_to_case(self, issue_id: str, case_id: str) -> Issue | None:
        """Set issues.case_id (move). Returns the updated Issue, or None if
        either the issue or the case doesn't exist."""
        if self.get_case(case_id) is None:
            return None
        with self._lock, self._conn() as c:
            cur = c.execute(
                "UPDATE issues SET case_id = ?, updated_at = ? WHERE id = ?",
                (case_id, _now(), issue_id),
            )
            if cur.rowcount == 0:
                return None
        return self.get_issue(issue_id)

    def remove_issue_from_case(self, issue_id: str) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute(
                "UPDATE issues SET case_id = NULL, updated_at = ? WHERE id = ?",
                (_now(), issue_id),
            )
        return cur.rowcount > 0

    # ─── Events (activity timeline) ────────────────────────────────

    def add_event(self, issue_id: str, type: str, content: str) -> IssueEvent | None:
        """Append an activity entry to an issue's timeline. Returns None if
        the issue doesn't exist."""
        if self.get_issue(issue_id) is None:
            return None
        event = IssueEvent(
            id=str(uuid.uuid4()),
            issue_id=issue_id,
            ts=_now(),
            type=type or "note",
            content=content if content is not None else "",
        )
        with self._lock, self._conn() as c:
            c.execute(
                "INSERT INTO issue_events (id, issue_id, ts, type, content) "
                "VALUES (?,?,?,?,?)",
                (event.id, event.issue_id, event.ts, event.type, event.content),
            )
            # touch the issue's updated_at so activity bumps it in the list
            c.execute("UPDATE issues SET updated_at = ? WHERE id = ?", (event.ts, issue_id))
        return event

    def list_events(self, issue_id: str) -> list[IssueEvent]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT id, issue_id, ts, type, content FROM issue_events "
                "WHERE issue_id = ? ORDER BY seq ASC",
                (issue_id,),
            ).fetchall()
        return [
            IssueEvent(
                id=r["id"], issue_id=r["issue_id"], ts=r["ts"],
                type=r["type"], content=r["content"],
            )
            for r in rows
        ]

    # ─── Indicators (IoCs) ─────────────────────────────────────────

    def upsert_indicator(
        self,
        value: str,
        type: str,
        issue_id: str | None = None,
        dbot_score: int | None = None,
        enrichment: str | None = None,
        source: str = "guardian",
    ) -> Indicator:
        """Insert or update an IoC (deduped by value+type), bumping last_seen
        and optionally linking it to an issue. Re-seeing an IoC updates the
        existing row + adds the link, never duplicating."""
        value = (value or "").strip()
        type = (type or "").strip().lower()
        if not value or not type:
            raise ValueError("value and type are required")
        ts = _now()
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT id FROM indicators WHERE value = ? AND type = ?", (value, type)
            ).fetchone()
            if row:
                ind_id = row["id"]
                sets = ["last_seen = ?", "updated_at = ?"]
                params: list = [ts, ts]
                if dbot_score is not None:
                    sets.append("dbot_score = ?"); params.append(int(dbot_score))
                if enrichment is not None:
                    sets.append("enrichment = ?"); params.append(enrichment)
                if source:
                    sets.append("source = ?"); params.append(source)
                params.append(ind_id)
                c.execute(f"UPDATE indicators SET {', '.join(sets)} WHERE id = ?", params)
            else:
                ind_id = str(uuid.uuid4())
                c.execute(
                    "INSERT INTO indicators (id, value, type, dbot_score, enrichment, "
                    "source, first_seen, last_seen, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (ind_id, value, type,
                     int(dbot_score) if dbot_score is not None else None,
                     enrichment, source or "guardian", ts, ts, ts, ts),
                )
            if issue_id:
                # Link only if the issue exists (FK is ON); skip silently otherwise.
                if c.execute("SELECT 1 FROM issues WHERE id = ?", (issue_id,)).fetchone():
                    c.execute(
                        "INSERT OR IGNORE INTO indicator_issues (indicator_id, issue_id) "
                        "VALUES (?, ?)",
                        (ind_id, issue_id),
                    )
            r = c.execute("SELECT * FROM indicators WHERE id = ?", (ind_id,)).fetchone()
        return self._row_to_indicator(r)

    def list_indicators(self, type: str | None = None, issue_id: str | None = None) -> list[dict]:
        """Indicators with an `issue_count` (for the list UI). Optional filter
        by type or by the issue they're linked to. Single-pass GROUP BY."""
        clauses: list[str] = []
        params: list = []
        join = ""
        if issue_id:
            join = "JOIN indicator_issues li2 ON li2.indicator_id = i.id "
            clauses.append("li2.issue_id = ?"); params.append(issue_id)
        if type:
            clauses.append("i.type = ?"); params.append(type.lower())
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT i.*, COUNT(DISTINCT li.issue_id) AS issue_count "
                "FROM indicators i LEFT JOIN indicator_issues li ON li.indicator_id = i.id "
                f"{join}{where} GROUP BY i.id "
                "ORDER BY i.last_seen DESC, i.created_at DESC",
                params,
            ).fetchall()
        return [
            {**self._row_to_indicator(r).__dict__, "issue_count": int(r["issue_count"])}
            for r in rows
        ]

    def get_indicator(self, indicator_id: str) -> dict | None:
        """One indicator + the issues it's linked to (id/title/kind/status/ref)."""
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM indicators WHERE id = ?", (indicator_id,)
            ).fetchone()
            if row is None:
                return None
            issues = c.execute(
                "SELECT s.id, s.title, s.kind, s.status, s.source_ref FROM issues s "
                "JOIN indicator_issues li ON li.issue_id = s.id "
                "WHERE li.indicator_id = ? ORDER BY s.updated_at DESC",
                (indicator_id,),
            ).fetchall()
        return {
            **self._row_to_indicator(row).__dict__,
            "issues": [
                {"id": r["id"], "title": r["title"], "kind": r["kind"],
                 "status": r["status"], "source_ref": r["source_ref"]}
                for r in issues
            ],
        }

    def list_indicators_for_issue(self, issue_id: str) -> list[Indicator]:
        """The indicators linked to one issue (the issue's extracted-IoCs section)."""
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT i.* FROM indicators i "
                "JOIN indicator_issues li ON li.indicator_id = i.id "
                "WHERE li.issue_id = ? ORDER BY i.type, i.value",
                (issue_id,),
            ).fetchall()
        return [self._row_to_indicator(r) for r in rows]

    # ─── Relationships (STIX edges) + relations canvas ─────────────

    def add_relationship(
        self,
        source_id: str,
        source_type: str,
        target_value: str,
        target_type: str,
        relationship_type: str,
        description: str | None = None,
        source: str = "guardian",
    ) -> dict:
        """Upsert a STIX-style edge, deduped by (source_id, relationship_type,
        target_value, target_type). Re-asserting bumps last_seen. The
        relationship_type is the STIX verb stored verbatim (resolves-to,
        communicates-with, indicates, attributed-to, uses, related-to, …)."""
        if not (source_id and source_type and target_value and target_type and relationship_type):
            raise ValueError("source_id, source_type, target_value, target_type, relationship_type are required")
        ts = _now()
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT id FROM relationships WHERE source_id=? AND relationship_type=? "
                "AND target_value=? AND target_type=?",
                (source_id, relationship_type, target_value, target_type),
            ).fetchone()
            if row:
                rid = row["id"]
                c.execute(
                    "UPDATE relationships SET last_seen=?, "
                    "description=COALESCE(?, description), source=? WHERE id=?",
                    (ts, description, source or "guardian", rid),
                )
            else:
                rid = str(uuid.uuid4())
                c.execute(
                    "INSERT INTO relationships (id, source_id, source_type, target_value, "
                    "target_type, relationship_type, description, source, first_seen, last_seen) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (rid, source_id, source_type, target_value, target_type,
                     relationship_type, description, source or "guardian", ts, ts),
                )
            r = c.execute("SELECT * FROM relationships WHERE id=?", (rid,)).fetchone()
        return dict(r)

    def list_relationships(self, source_id: str | None = None) -> list[dict]:
        with self._lock, self._conn() as c:
            if source_id:
                rows = c.execute(
                    "SELECT * FROM relationships WHERE source_id=? ORDER BY last_seen DESC",
                    (source_id,),
                ).fetchall()
            else:
                rows = c.execute("SELECT * FROM relationships ORDER BY last_seen DESC").fetchall()
        return [dict(r) for r in rows]

    def set_relations_canvas(self, issue_id: str, svg: str | None) -> bool:
        with self._lock, self._conn() as c:
            cur = c.execute(
                "UPDATE issues SET relations_canvas_svg=?, updated_at=? WHERE id=?",
                (svg, _now(), issue_id),
            )
        return cur.rowcount > 0

    def get_relations_canvas(self, issue_id: str) -> str | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT relations_canvas_svg FROM issues WHERE id=?", (issue_id,)
            ).fetchone()
        return row["relations_canvas_svg"] if row else None

    # ─── Row mappers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_issue(row: sqlite3.Row) -> Issue:
        return Issue(
            id=row["id"], title=row["title"], status=row["status"],
            severity=row["severity"], kind=row["kind"], origin=row["origin"],
            source_ref=row["source_ref"], case_id=row["case_id"],
            summary=row["summary"], scope=row["scope"],
            recommendations=row["recommendations"], conclusions=row["conclusions"],
            next_steps=row["next_steps"],
            verdict=row["verdict"], verdict_confidence=row["verdict_confidence"],
            blast_radius=row["blast_radius"], report=row["report"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_case(row: sqlite3.Row) -> Case:
        keys = row.keys()
        return Case(
            id=row["id"], title=row["title"], description=row["description"],
            status=row["status"],
            campaign_summary=row["campaign_summary"] if "campaign_summary" in keys else None,
            threat_actor=row["threat_actor"] if "threat_actor" in keys else None,
            infrastructure=row["infrastructure"] if "infrastructure" in keys else None,
            techniques=row["techniques"] if "techniques" in keys else None,
            severity_rollup=row["severity_rollup"] if "severity_rollup" in keys else None,
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_indicator(row: sqlite3.Row) -> Indicator:
        return Indicator(
            id=row["id"], value=row["value"], type=row["type"],
            dbot_score=row["dbot_score"], enrichment=row["enrichment"],
            source=row["source"], first_seen=row["first_seen"],
            last_seen=row["last_seen"], created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


# ─────────────────────────────────────────────────────────────────
# Module-level singleton accessor — wired by main.py (mirrors
# instance_store / memory_store). Lets the issue_* / case_* MCP tools
# look up the store at call time without threading it through every
# signature. None pre-boot or in tests that construct the store directly.
# ─────────────────────────────────────────────────────────────────

_investigation_store: InvestigationStore | None = None


def set_investigation_store(s: InvestigationStore | None) -> None:
    global _investigation_store
    _investigation_store = s


def investigation_store() -> InvestigationStore | None:
    return _investigation_store
