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


def _det(prefix: str, i: int) -> str:
    """Deterministic short hex derived from an index — stable across runs."""
    return hashlib.md5(f"{prefix}:{i}".encode()).hexdigest()  # noqa: S324


def generate_notables(
    count: int, earliest: Any = None, latest: Any = None
) -> list[dict[str, Any]]:
    """Generate `count` deterministic ES notable events within [earliest, latest].

    Each event carries the fields SplunkPy reads. Events are spread evenly
    across the window, newest first (descending _time) — the order real
    Splunk returns for a notable search.
    """
    count = max(0, int(count))
    et, lt = _resolve_window(earliest, latest)
    span = max(1.0, lt - et)
    out: list[dict[str, Any]] = []
    for i in range(count):
        rule = _RULES[i % len(_RULES)]
        urgency = _URGENCIES[i % len(_URGENCIES)]
        owner = _OWNERS[i % len(_OWNERS)]
        # newest first: event 0 is the most recent
        ts = lt - (i + 0.5) * (span / count)
        src = f"10.0.{i % 256}.{(i * 7) % 256}"
        dest = f"172.16.{(i * 3) % 256}.{(i * 13) % 256}"
        user = f"user{i % 50:02d}"
        host = f"host-{i % 30:02d}"
        # ES event_id format: <hex>@@notable@@<hex>
        event_id = f"{_det('eid', i)[:24].upper()}@@notable@@{_det('n', i)}"
        raw = (
            f'{splunk_time(ts)} rule_name="{rule["rule_name"]}" '
            f'src={src} dest={dest} user={user} host={host} '
            f'urgency={urgency} signature="{rule["rule_title"]}"'
        )
        out.append(
            {
                "event_id": event_id,
                "_time": splunk_time(ts),
                "_raw": raw,
                "rule_id": _det("rid", i),
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
                    f'search `notable` rule_name="{rule["rule_name"]}" '
                    f"src={src}"
                ),
                "source": rule["rule_name"],
                "index": "notable",
            }
        )
    return out


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
    spl: str, earliest: Any = None, latest: Any = None, count: int = 25
) -> list[dict[str, Any]]:
    """Interpret a SplunkPy-issued SPL query into mimic results.

    * contains the `notable` macro / word → generated notable events;
    * else contains an indicator literal → rows echoing that indicator (so
      the Indicator Hunting playbook's search task returns a hit);
    * else → no results.
    """
    spl = spl or ""
    low = spl.lower()
    if "notable" in low or "`notable`" in spl:
        return generate_notables(count, earliest, latest)

    indicator = _find_indicator(spl)
    if indicator:
        et, lt = _resolve_window(earliest, latest)
        rows: list[dict[str, Any]] = []
        n = max(1, min(3, int(count) if count else 3))
        for i in range(n):
            ts = lt - (i + 0.5) * ((lt - et) / n)
            rows.append(
                {
                    "_time": splunk_time(ts),
                    "_raw": (
                        f"{splunk_time(ts)} indicator={indicator} "
                        f"action=allowed bytes={(i + 1) * 2048}"
                    ),
                    "indicator": indicator,
                    "src": indicator if _IPV4.fullmatch(indicator) else f"10.0.0.{i + 1}",
                    "dest": f"203.0.113.{i + 10}",
                    "count": str((i + 1) * 3),
                    "index": "main",
                }
            )
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
        count: int = 25,
    ) -> str:
        results = run_query(spl, earliest, latest, count)
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
