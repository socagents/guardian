"""Splunk-mimic state — notable-event generator + minimal SPL interpreter
+ in-memory job store.

The generator emits ES "notable" events carrying the fields the XSOAR
SplunkPy integration reads (event_id, _time, _raw, rule_name, rule_title,
rule_description, urgency, owner, security_domain, status, src, dest, user,
drilldown_name, drilldown_search, source). It is DETERMINISTIC — every value
is derived from the event index, so the same window yields the same events on
rerun (no random, stable for tests + mirroring).

The SPL "interpreter" is intentionally tiny. SplunkPy never asks the mimic to
execute arbitrary SPL — it sends a small, known set of queries:
  * the ``notable`` macro (fetch-incidents + ``splunk-search query="search
    `notable`"``) → return generated notable events;
  * an indicator literal (IP / hash / domain) embedded in a search (the
    Indicator Hunting playbook's ``splunk-search``) → return rows echoing
    that indicator so the playbook task succeeds;
  * anything else → no results.

`_time` format matches what SplunkPy parses: it splits on "." and reads
``%Y-%m-%dT%H:%M:%S`` (see SplunkPy.splunk_time_to_datetime), so we emit
``2026-06-19T12:34:56.000+00:00``.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

# ── notable taxonomy ────────────────────────────────────────────────────

# A varied set of ES correlation rules spanning the security domains a SOC
# analyst sees. Each notable cycles through these by index so a fetch window
# produces a realistic mix (endpoint, access, network, threat, identity,
# audit). urgency rotates independently so severities vary within a rule too.
_RULES: list[dict[str, str]] = [
    {
        "rule_name": "Endpoint - Recurring Malware On Host - Rule",
        "rule_title": "Recurring Malware On Host",
        "security_domain": "endpoint",
        "rule_description": "A host has multiple malware detections in a short window, indicating an unremediated infection.",
    },
    {
        "rule_name": "Access - Brute Force Access Behavior Detected - Rule",
        "rule_title": "Brute Force Access Behavior Detected",
        "security_domain": "access",
        "rule_description": "Multiple failed authentications followed by a success suggest a brute-force compromise.",
    },
    {
        "rule_name": "Network - Substantial Increase In Port Activity - Rule",
        "rule_title": "Substantial Increase In Port Activity",
        "security_domain": "network",
        "rule_description": "A source produced an abnormal spike in distinct destination ports, consistent with scanning.",
    },
    {
        "rule_name": "Threat - Threat Intelligence Match - Rule",
        "rule_title": "Threat Intelligence Match",
        "security_domain": "threat",
        "rule_description": "An observed indicator matched a known-malicious entry in a threat-intelligence collection.",
    },
    {
        "rule_name": "Identity - Activity from Expired User Identity - Rule",
        "rule_title": "Activity from Expired User Identity",
        "security_domain": "identity",
        "rule_description": "Activity was observed from a user identity flagged as expired or disabled.",
    },
    {
        "rule_name": "Endpoint - Anomalous New Process - Rule",
        "rule_title": "Anomalous New Process",
        "security_domain": "endpoint",
        "rule_description": "A rarely-seen process executed on an endpoint, deviating from the host's baseline.",
    },
    {
        "rule_name": "Network - Data Exfiltration to Rare Destination - Rule",
        "rule_title": "Data Exfiltration to Rare Destination",
        "security_domain": "network",
        "rule_description": "A large outbound transfer to an uncommon external destination suggests data exfiltration.",
    },
    {
        "rule_name": "Access - Geographically Improbable Access - Rule",
        "rule_title": "Geographically Improbable Access",
        "security_domain": "access",
        "rule_description": "A user authenticated from two locations too far apart to be physically possible.",
    },
]

# ES urgency values. SplunkPy maps these to XSOAR severity on its side
# (critical→4, high→3, medium→2, low→1, informational→0.5); the mimic only
# emits the distribution.
_URGENCIES = ["critical", "high", "medium", "low", "informational"]

_OWNERS = ["unassigned", "analyst1", "analyst2", "soc_lead"]

# ── notable time grid (the rotation keystone) ───────────────────────────
#
# Notables live on a FIXED ABSOLUTE TIME GRID: one notable every
# GRID_INTERVAL seconds since a fixed EPOCH_ANCHOR. Identity AND content
# derive purely from the grid instant — never from a request's count or
# loop position. Consequences (verified against the SplunkPy fetch+dedup
# contract):
#   * re-querying the SAME [earliest, latest) window returns byte-identical
#     events (same event_id/_time/_raw) → SplunkPy's found_incidents_ids
#     dedup drops them, no duplicate incidents;
#   * an ADVANCING window (latest=now moving forward) exposes fresh grid
#     instants with brand-new event_ids → XSOAR fetches NEW incidents each
#     cycle. Rotation is purely the time-window filter; no server state.
# `count`/`offset` only SELECT how many in-window grid points are returned.
#
# EPOCH_ANCHOR is a fixed historical constant so the grid is identical
# across deployments + restarts. GRID_INTERVAL (one notable / minute by
# default) is the rate knob.
EPOCH_ANCHOR = 1_600_000_000  # 2020-09-13T12:26:40Z — fixed grid origin
GRID_INTERVAL = max(1, int(os.environ.get("SPLUNK_MIMIC_NOTABLE_INTERVAL_S", "60")))
# Safety cap so a very wide window can't materialise an unbounded result set.
MAX_NOTABLES = max(1, int(os.environ.get("SPLUNK_MIMIC_MAX_NOTABLES", "5000")))


def splunk_time(epoch: float) -> str:
    """Format an epoch as the `_time` string SplunkPy can parse."""
    dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
    # millisecond precision + explicit +00:00 offset; SplunkPy splits on "."
    # and parses the left side with %Y-%m-%dT%H:%M:%S.
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}+00:00"


def _to_epoch(value: Any, default: float) -> float:
    """Best-effort parse of a splunklib time arg into epoch seconds.

    Honours absolute epoch (int/float/numeric string) and ISO8601; returns
    `default` for None, empty, or relative modifiers like "-24h" (the mimic
    doesn't need calendar-accurate relative windows — it just needs a stable
    span to spread events across).
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        pass
    try:
        # tolerate trailing Z
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return default


def _resolve_window(earliest: Any, latest: Any) -> tuple[float, float]:
    now = time.time()
    lt = _to_epoch(latest, now)
    et = _to_epoch(earliest, lt - 86_400)
    if et >= lt:
        et = lt - 86_400
    return et, lt


def _det(prefix: str, seed: Any) -> str:
    """Deterministic short hex derived from a seed — stable across runs."""
    return hashlib.md5(f"{prefix}:{seed}".encode()).hexdigest()  # noqa: S324


def _grid_instants(earliest_epoch: float, latest_epoch: float) -> list[tuple[int, int]]:
    """Return (grid_index, grid_epoch) for every grid point in the HALF-OPEN
    window [earliest, latest), newest first.

    Half-open is deliberate: SplunkPy advances ``next earliest = old latest``,
    so a closed upper bound would emit a boundary instant in two adjacent
    windows (a duplicate-looking-but-new id at the seam). With [earliest,
    latest) each instant lives in exactly one window → advancing windows are
    disjoint.
    """
    # First grid index whose epoch is >= earliest (and >= the anchor).
    start_idx = max(0, math.ceil((earliest_epoch - EPOCH_ANCHOR) / GRID_INTERVAL))
    out: list[tuple[int, int]] = []
    idx = start_idx
    epoch = EPOCH_ANCHOR + idx * GRID_INTERVAL
    while epoch < latest_epoch and len(out) < MAX_NOTABLES + 1:
        out.append((idx, epoch))
        idx += 1
        epoch = EPOCH_ANCHOR + idx * GRID_INTERVAL
    out.reverse()  # newest first
    return out[:MAX_NOTABLES]


def _notable_at(grid_index: int, grid_epoch: int) -> dict[str, Any]:
    """Build one notable derived ENTIRELY from its absolute grid instant.

    event_id, _time, _raw, rule/urgency/owner, and the src/dest/user/host
    entities are all pure functions of (grid_index, grid_epoch). So the same
    instant is byte-identical on every re-query (dedup-stable), while
    different instants vary (rotation + realistic mix). NOTHING here depends
    on the request's count or loop position.
    """
    rule = _RULES[grid_index % len(_RULES)]
    urgency = _URGENCIES[grid_index % len(_URGENCIES)]
    owner = _OWNERS[grid_index % len(_OWNERS)]
    seed = str(grid_epoch)  # absolute grid epoch — the identity anchor
    src = f"10.0.{grid_index % 256}.{(grid_index * 7) % 256}"
    dest = f"172.16.{(grid_index * 3) % 256}.{(grid_index * 13) % 256}"
    user = f"user{grid_index % 50:02d}"
    host = f"host-{grid_index % 30:02d}"
    when = splunk_time(grid_epoch)
    # ES event_id format: <hex>@@notable@@<hex>, keyed off the grid epoch.
    event_id = f"{_det('eid', seed)[:24].upper()}@@notable@@{_det('n', seed)}"
    raw = (
        f"{grid_epoch}, search_name=\"{rule['rule_name']}\" "
        f"src={src} dest={dest} user={user} host={host} "
        f'urgency={urgency} signature="{rule["rule_title"]}"'
    )
    return {
        "event_id": event_id,
        "_time": when,
        "_raw": raw,
        # _indextime: stable per instant; SplunkPy custom_id fallback material.
        "_indextime": str(grid_epoch),
        "_cd": f"{grid_index % 1000}:{grid_epoch % 100000}",
        "rule_id": _det("rid", seed),
        "rule_name": rule["rule_name"],
        "rule_title": rule["rule_title"],
        "rule_description": rule["rule_description"],
        "security_domain": rule["security_domain"],
        "urgency": urgency,
        "severity": urgency,
        "status": "1",
        "status_label": "New",
        "owner": owner,
        "src": src,
        "dest": dest,
        "user": user,
        "host": host,
        "drilldown_name": f"View all {rule['rule_title']} events",
        "drilldown_search": (
            f'search `notable` rule_name="{rule["rule_name"]}" src={src}'
        ),
        "source": rule["rule_name"],
        "index": "notable",
    }


def generate_notables(
    count: int | None = None,
    earliest: Any = None,
    latest: Any = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return ES notable events on the fixed time grid within [earliest, latest).

    The set of notables is defined by the grid (count-INDEPENDENT). `count`
    caps how many of the in-window grid points are returned (None = all, up
    to MAX_NOTABLES); `offset` skips the first N (SplunkPy paginates large
    windows by re-issuing with an advancing offset). Newest first.
    """
    et, lt = _resolve_window(earliest, latest)
    rows = [_notable_at(idx, epoch) for (idx, epoch) in _grid_instants(et, lt)]
    if offset:
        rows = rows[max(0, int(offset)):]
    if count is not None and int(count) >= 0:
        rows = rows[: int(count)]
    return rows


# Indicator literals the Indicator Hunting playbook may search for.
_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_HASH = re.compile(r"\b[a-fA-F0-9]{32}(?:[a-fA-F0-9]{8})?(?:[a-fA-F0-9]{24})?\b")
_DOMAIN = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.IGNORECASE)


def _find_indicator(spl: str) -> str | None:
    """Extract the first indicator literal (IP / hash / domain) from a query."""
    m = _IPV4.search(spl)
    if m:
        return m.group(0)
    m = _HASH.search(spl)
    if m and len(m.group(0)) in (32, 40, 64):
        return m.group(0)
    # Domains: skip obviously-non-indicator tokens (field names like
    # rule_name happen to lack dots, so the regex won't match them).
    m = _DOMAIN.search(spl)
    if m:
        return m.group(0)
    return None


def run_query(
    spl: str,
    earliest: Any = None,
    latest: Any = None,
    count: int | None = 25,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Interpret a SplunkPy-issued SPL query into mimic results.

    * contains the `notable` macro / word → generated notable events on the
      fixed time grid (count/offset select; window filters → rotation);
    * else contains an indicator literal → rows echoing that indicator (so
      the Indicator Hunting playbook's search task returns a hit);
    * else → no results.

    `offset` is honoured on BOTH paths — SplunkPy's fetch paginates a window
    that holds more than FETCH_LIMIT notables by re-issuing with an advancing
    offset; ignoring it would re-return the same first slice forever.
    """
    spl = spl or ""
    low = spl.lower()
    if "notable" in low or "`notable`" in spl:
        return generate_notables(count, earliest, latest, offset=offset)

    indicator = _find_indicator(spl)
    if indicator:
        et, lt = _resolve_window(earliest, latest)
        # Echo rows are also placed on a coarse absolute grid so re-query is
        # stable; capped small (the playbook only needs a hit, not volume).
        instants = _grid_instants(et, lt)[:3]
        rows: list[dict[str, Any]] = []
        for idx, epoch in instants:
            when = splunk_time(epoch)
            rows.append(
                {
                    "_time": when,
                    "_raw": (
                        f"{epoch} indicator={indicator} "
                        f"action=allowed bytes={(idx % 8 + 1) * 2048}"
                    ),
                    "indicator": indicator,
                    "src": indicator if _IPV4.fullmatch(indicator) else f"10.0.0.{idx % 254 + 1}",
                    "dest": f"203.0.113.{idx % 240 + 10}",
                    "count": str((idx % 5 + 1) * 3),
                    "index": "main",
                }
            )
        if offset:
            rows = rows[max(0, int(offset)):]
        if count is not None and int(count) >= 0:
            rows = rows[: int(count)]
        return rows
    return []


# ── job store ───────────────────────────────────────────────────────────


class JobRecord:
    """A completed search job. Results are precomputed at create time — the
    mimic completes jobs instantly (no async dispatch state machine)."""

    def __init__(self, sid: str, spl: str, results: list[dict[str, Any]]) -> None:
        self.sid = sid
        self.spl = spl
        self.results = results
        self.created_at = time.time()

    @property
    def result_count(self) -> int:
        return len(self.results)


class JobStore:
    """In-memory store of search jobs keyed by sid. Thread-safe (uvicorn may
    serve concurrent requests). Jobs complete instantly."""

    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = threading.Lock()
        self._counter = 0

    def create(
        self,
        spl: str,
        earliest: Any = None,
        latest: Any = None,
        count: int | None = None,
    ) -> str:
        # Hold the FULL in-window result set (count=None) so the create→
        # poll→results path (splunk-search) can paginate via get_job_results'
        # offset/count slicing. resultCount then reflects the true total.
        results = run_query(spl, earliest, latest, count=count, offset=0)
        with self._lock:
            self._counter += 1
            # Splunk sids look like "<epoch>.<counter>"; keep that shape so
            # any client-side sid parsing stays happy. uuid suffix guards
            # uniqueness under concurrency.
            sid = f"{int(time.time())}.{self._counter}_{uuid.uuid4().hex[:8]}"
            self._jobs[sid] = JobRecord(sid, spl, results)
        return sid

    def get(self, sid: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(sid)
