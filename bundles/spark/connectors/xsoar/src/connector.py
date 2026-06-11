"""Cortex XSOAR connector — tool implementations.

The Guardian incident-investigation agent's surface onto Cortex XSOAR.
Follows the standard Guardian connector structure: live config +
resolved secrets are read on every call via `from config.config import
get_config`, a stateless XSOARFetcher is built, and each tool POSTs (or
GETs) a logical XSOAR REST path. The fetcher applies the dual-
generation base-URL + header rules (v6 vs v8) — every tool here stays
generation-agnostic.

Tool catalog (13):
  xsoar_list_incidents        POST /incidents/search — filtered case list
  xsoar_get_incident          POST /incidents/search (filter.id) — one case
  xsoar_get_war_room          POST /investigation/{id} — war-room entries
  xsoar_add_entry             POST /entry — append a war-room entry
  xsoar_add_note              POST /entry + /entry/note — pinned note
  xsoar_update_incident       POST /incident — upsert metadata (needs version)
  xsoar_close_incident        POST /incident/batchClose — close one+ cases
  xsoar_list_incident_types   POST /incidents/search — derive distinct types
  xsoar_get_incident_fields   GET /incidentfields/associatedTypes/{type}
  xsoar_search_indicators     POST /indicators/search — threat-intel lookup
  xsoar_save_evidence         POST /evidence — mark an entry as evidence
  xsoar_search_evidence       POST /evidence/search — list a case's evidence
  xsoar_health_check          GET /health — server-availability probe

Auth model (see _xsoar_client.XSOARFetcher):
  XSOAR 6 — Authorization: <api_key>                       (api_id unset)
  XSOAR 8 — Authorization: <api_key> + x-xdr-auth-id: <api_id>,
            with the /xsoar/public/v1 path prefix.

Function names AND __all__ entries are fully prefixed (xsoar_*). The
connector-runtime strips the "xsoar_" (=<id>_) prefix at registration
and exposes bare names; the agent sees them namespaced as
`xsoar.<bare>` and aliased as `xsoar_<bare>`.
"""
from __future__ import annotations

import functools
from typing import Any, Optional

from ._xsoar_client import (
    XSOARAuthError,
    XSOARError,
    XSOARFetcher,
    XSOARRateLimitError,
    XSOARRequestError,
    XSOARServerError,
)


# Explicit tool exports. Listing the public tool names makes the
# connector-runtime use the explicit-export path — without it,
# auto-discovery picks up the wrapper's signature, which fastmcp
# rejects. functools.wraps below restores each tool's original typed
# signature for the runtime's schema derivation.
__all__ = [
    "xsoar_list_incidents",
    "xsoar_get_incident",
    "xsoar_get_war_room",
    "xsoar_add_entry",
    "xsoar_add_note",
    "xsoar_update_incident",
    "xsoar_close_incident",
    "xsoar_list_incident_types",
    "xsoar_get_incident_fields",
    "xsoar_search_indicators",
    "xsoar_save_evidence",
    "xsoar_search_evidence",
    "xsoar_health_check",
]


# ─── Envelopes ───────────────────────────────────────────────────────


def _err(message: str, **extra: Any) -> dict:
    """Standard error envelope. Agents branch on `ok=false`."""
    payload = {"ok": False, "error": message}
    payload.update(extra)
    return payload


def _ok(payload: dict) -> dict:
    """Standard success envelope."""
    if not isinstance(payload, dict):
        payload = {"value": payload}
    if "ok" not in payload:
        payload = {"ok": True, **payload}
    return payload


# ─── Config + fetcher resolution ─────────────────────────────────────


def _get_xsoar_config() -> dict:
    """Read live xsoar instance config + resolved secrets.

    Uses the connector-runtime's `config.config.get_config()` proxy —
    the standard Guardian container-style config path. The connector
    runs in a separate container where the agent's `usecase/` tree isn't
    importable; the runtime resolves config + secrets into a flat dict
    and stashes it on a contextvar that get_config() reads. Attribute
    access on the proxy maps to that dict.

    api_url is required; api_id (→ v8) and verify_ssl are optional.
    """
    from config.config import get_config

    proxy = get_config()
    try:
        api_url = proxy.api_url
    except AttributeError:
        raise ValueError(
            "No xsoar instance configured (api_url missing). Add an "
            "instance via /connectors with api_url + api_key (and api_id "
            "for XSOAR 8 / Cortex cloud), or configure it during "
            "first-time setup."
        )
    return {
        "api_url": api_url,
        "api_id": getattr(proxy, "api_id", None),
        "api_key": getattr(proxy, "api_key", None),
        "verify_ssl": getattr(proxy, "verify_ssl", True),
    }


def _get_fetcher() -> XSOARFetcher:
    """Resolve the XSOARFetcher from the live instance config."""
    cfg = _get_xsoar_config()

    api_url = cfg.get("api_url")
    if not api_url:
        raise ValueError(
            "xsoar instance has no api_url configured. Edit at /connectors."
        )
    api_key = cfg.get("api_key")
    if not api_key:
        raise ValueError(
            "xsoar instance has no api_key (Authorization header) configured."
        )
    api_id = cfg.get("api_id")
    verify_ssl = cfg.get("verify_ssl", True)

    return XSOARFetcher(
        str(api_url),
        str(api_key),
        api_id=str(api_id) if api_id not in (None, "") else None,
        verify_ssl=bool(verify_ssl),
    )


def _wrap_xsoar_call(fn):
    """Decorator: convert XSOAR exceptions to error envelopes.

    The MCP tool surface returns dicts uniformly — never raises — so the
    agent branches on `ok=false` instead of try/except. functools.wraps
    sets __wrapped__ so inspect.signature() unwraps to the ORIGINAL
    typed signature, which fastmcp's Tool.from_function needs to derive
    a tool schema (a bare *args/**kwargs wrapper is rejected).
    """
    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> dict:
        try:
            result = await fn(*args, **kwargs)
            return _ok(result) if isinstance(result, dict) else _ok({"value": result})
        except XSOARAuthError as exc:
            return _err(f"Cortex XSOAR auth failed: {exc}", is_auth_error=True)
        except XSOARRateLimitError as exc:
            return _err(f"Cortex XSOAR rate-limited: {exc}", retryable=True)
        except XSOARServerError as exc:
            return _err(f"Cortex XSOAR server error: {exc}", retryable=True)
        except XSOARRequestError as exc:
            return _err(f"Cortex XSOAR request rejected: {exc}")
        except XSOARError as exc:
            return _err(f"Cortex XSOAR error: {exc}")
        except ValueError as exc:
            # _get_fetcher's operator-actionable config errors
            return _err(str(exc))
        except Exception as exc:  # pragma: no cover — defensive
            return _err(f"xsoar unexpected error: {type(exc).__name__}: {exc}")
    return wrapper


# ─── Coercion helpers ────────────────────────────────────────────────


def _clamp_int(value: object, default: int, lo: int, hi: int) -> int:
    """Coerce `value` to an int clamped to [lo, hi], defaulting on bad input.

    The connector runtime passes None for unspecified optional args, so a
    bare int(value) raises TypeError on an empty-args call. Routing every
    clamped int through this helper makes those calls degrade to the
    default instead of throwing (the runtime-None-arg lesson).
    """
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def _norm_int(value: object, default: int) -> int:
    """Coerce to a non-negative int, defaulting on None / bad input."""
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        n = default
    return max(0, n)


def _as_list(value: object) -> Optional[list]:
    """Normalize a possibly-scalar value to a list (or None when empty).

    LLM tool calls frequently pass a single string where the API wants
    an array (status='active' instead of status=['active']). Wrap a bare
    scalar; pass lists through; map None/empty to None so the caller can
    skip the filter entirely.
    """
    if value is None or value == "":
        return None
    if isinstance(value, list):
        return value or None
    return [value]


def _summarize_incident(inc: dict) -> dict:
    """Project a compact case summary the agent can triage on.

    Operators don't need every XSOAR field at the list level; use
    xsoar_get_incident for the full record.
    """
    return {
        "id": inc.get("id"),
        "name": inc.get("name"),
        "type": inc.get("type"),
        "severity": inc.get("severity"),
        "status": inc.get("status"),
        "owner": inc.get("owner"),
        "created": inc.get("created"),
        "modified": inc.get("modified"),
    }


# ─── xsoar_list_incidents ────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_list_incidents(
    query: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    status: Optional[list] = None,
    severity: Optional[list] = None,
    page: int = 0,
    page_size: int = 50,
) -> dict:
    """List Cortex XSOAR incidents (cases) matching a filter.

    The primary triage entrypoint: "what cases are open?", "show me
    today's high-severity incidents", "find cases mentioning <host>".
    Returns a compact summary per case; drill into one with
    xsoar_get_incident.

    Args:
        query: Optional XSOAR search-query string (e.g.
            'status:active and severity:High', or free text like
            'phishing'). When supplied, XSOAR mostly ignores the
            structured status/severity filters below — use ONE approach
            or the other, not both.
        from_date: ISO lower bound on the created time
            (e.g. '2026-06-01T00:00:00Z'). Optional.
        to_date: ISO upper bound on the created time. Optional.
        status: Subset of XSOAR status CODES as integers:
            0 = pending, 1 = active/open, 2 = closed, 3 = archived.
            e.g. status=[1] for "open cases". A bare int or string is
            wrapped into a list automatically.
        severity: Subset of XSOAR severity LEVELS as integers 1-4:
            1 = low, 2 = medium, 3 = high, 4 = critical.
            e.g. severity=[3, 4] for "high and critical".
        page: Zero-based page index (default 0).
        page_size: Page size (default 50, max 200).

    Example body POSTed to /incidents/search:
        {"filter": {"page": 0, "size": 50, "status": [1],
                    "level": [3, 4],
                    "sort": [{"field": "created", "asc": false,
                              "fieldType": "date"}]}}

    Returns:
        {ok, incidents: [{id, name, type, severity, status, owner,
                          created, modified}], total}.
    """
    page = _norm_int(page, 0)
    size = _clamp_int(page_size, 50, 1, 200)

    filt: dict[str, Any] = {
        "page": page,
        "size": size,
        "sort": [{"field": "created", "asc": False, "fieldType": "date"}],
    }
    if query:
        filt["query"] = query
    if from_date:
        filt["fromDate"] = from_date
    if to_date:
        filt["toDate"] = to_date
    status_list = _as_list(status)
    if status_list is not None:
        filt["status"] = status_list
    severity_list = _as_list(severity)
    if severity_list is not None:
        filt["level"] = severity_list

    fetcher = _get_fetcher()
    response = await fetcher.post("/incidents/search", {"filter": filt})

    data = response.get("data") or []
    total = response.get("total", len(data))
    incidents = [_summarize_incident(inc) for inc in data]

    return {
        "incidents": incidents,
        "total": total,
        "result_count": len(incidents),
        "applied_filters": {
            "query": query,
            "from_date": from_date,
            "to_date": to_date,
            "status": status_list,
            "severity": severity_list,
            "page": page,
            "page_size": size,
        },
    }


# ─── xsoar_get_incident ──────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_get_incident(incident_id: str) -> dict:
    """Fetch the full record for one XSOAR incident by id.

    XSOAR has NO GET /incident/{id} endpoint — this searches with
    filter.id = [incident_id] and returns the first match. Use AFTER
    xsoar_list_incidents to drill into a specific case (and to read the
    `version` field you'll need for xsoar_update_incident).

    Args:
        incident_id: The XSOAR incident id (string).

    Example body POSTed to /incidents/search:
        {"filter": {"id": ["123"], "page": 0, "size": 1}}

    Returns:
        {ok, incident: {... full XSOAR incident record incl. version,
                        CustomFields, labels, investigationId ...}} or
        {ok: false, error} when the id matched no case.
    """
    if not incident_id:
        raise ValueError("incident_id is required")

    filt = {"id": [str(incident_id)], "page": 0, "size": 1}
    fetcher = _get_fetcher()
    response = await fetcher.post("/incidents/search", {"filter": filt})

    data = response.get("data") or []
    if not data:
        return _err(f"incident {incident_id} not found", incident_id=incident_id)

    return {"incident": data[0]}


# ─── xsoar_get_war_room ──────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_get_war_room(
    incident_id: str,
    page_size: int = 100,
    tags: Optional[list] = None,
    from_time: Optional[str] = None,
) -> dict:
    """Read the war-room (investigation) entries for one incident.

    The war room is the case's running log — analyst notes, playbook
    task outputs, command results, evidence markers. Read it to
    understand what's already been investigated before adding your own
    findings.

    Args:
        incident_id: The XSOAR incident id (its investigation shares
            the same id).
        page_size: Max entries to return (default 100, max 200).
        tags: Optional list of entry tags to filter by (e.g.
            ['evidence', 'note']). A bare string is wrapped.
        from_time: Optional ISO lower bound — only entries created at or
            after this time.

    Example body POSTed to /investigation/{id}:
        {"pageSize": 100, "tags": ["note"], "fromTime": "2026-06-01T00:00:00Z"}

    Returns:
        {ok, entries: [{id, type, contents, format, tags, created,
                        user}], count}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")

    body: dict[str, Any] = {"pageSize": _clamp_int(page_size, 100, 1, 200)}
    tag_list = _as_list(tags)
    if tag_list is not None:
        body["tags"] = tag_list
    if from_time:
        body["fromTime"] = from_time

    fetcher = _get_fetcher()
    response = await fetcher.post(f"/investigation/{incident_id}", body)

    # XSOAR returns the entry list under `entries` (or, on some builds,
    # as the bare array the fetcher normalized into `data`).
    raw_entries = response.get("entries")
    if raw_entries is None:
        raw_entries = response.get("data") or []

    entries = [
        {
            "id": e.get("id"),
            "type": e.get("type"),
            "contents": e.get("contents"),
            "format": e.get("format"),
            "tags": e.get("tags"),
            "created": e.get("created"),
            "user": e.get("user"),
        }
        for e in raw_entries
    ]

    return {
        "entries": entries,
        "count": len(entries),
        "incident_id": incident_id,
    }


# ─── xsoar_add_entry ─────────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_add_entry(
    incident_id: str,
    content: str,
    markdown: bool = True,
) -> dict:
    """Append a war-room entry to an incident's investigation.

    The primary "document a finding" tool: write your analysis,
    summary, or investigation step into the case's running log so other
    analysts (and the audit trail) see it. To pin the entry as a
    persistent note instead, use xsoar_add_note.

    Args:
        incident_id: The XSOAR incident id.
        content: The entry text. Markdown is rendered when markdown=True.
        markdown: Render `content` as markdown (default True). Set False
            for plain text.

    Example body POSTed to /entry:
        {"investigationId": "123", "data": "## Findings\\n...", "markdown": true}

    Returns:
        {ok, entry_id, incident_id}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")
    if not content:
        raise ValueError("content is required")

    body = {
        "investigationId": str(incident_id),
        "data": content,
        "markdown": bool(markdown),
    }
    fetcher = _get_fetcher()
    response = await fetcher.post("/entry", body)

    entry_id = response.get("id") or (response.get("entry") or {}).get("id")
    return {
        "entry_id": entry_id,
        "incident_id": incident_id,
    }


# ─── xsoar_add_note ──────────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_add_note(
    incident_id: str,
    content: str,
    markdown: bool = True,
) -> dict:
    """Add a pinned NOTE to an incident's war room.

    Two-step: POST /entry to create the entry, then POST /entry/note to
    pin it as a note (notes are highlighted in the XSOAR UI and survive
    war-room filtering). Use for durable investigation conclusions the
    operator wants flagged — vs. xsoar_add_entry for an ordinary log
    line.

    Args:
        incident_id: The XSOAR incident id.
        content: The note text (markdown-rendered when markdown=True).
        markdown: Render as markdown (default True).

    Example bodies:
        POST /entry      {"investigationId": "123", "data": "...", "markdown": true}
        POST /entry/note {"investigationId": "123", "id": "<entry id>",
                          "version": <entry version>, "note": true}

    Returns:
        {ok, entry_id, incident_id, note: true}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")
    if not content:
        raise ValueError("content is required")

    fetcher = _get_fetcher()

    # Step 1 — create the entry.
    created = await fetcher.post(
        "/entry",
        {
            "investigationId": str(incident_id),
            "data": content,
            "markdown": bool(markdown),
        },
    )
    entry = created.get("entry") if isinstance(created.get("entry"), dict) else created
    entry_id = created.get("id") or entry.get("id")
    entry_version = created.get("version", entry.get("version", 1))
    if not entry_id:
        return _err(
            "could not determine entry id after creating war-room entry",
            incident_id=incident_id,
            raw_response=created,
        )

    # Step 2 — pin it as a note.
    await fetcher.post(
        "/entry/note",
        {
            "investigationId": str(incident_id),
            "id": str(entry_id),
            "version": entry_version,
            "note": True,
        },
    )

    return {
        "entry_id": entry_id,
        "incident_id": incident_id,
        "note": True,
    }


# ─── xsoar_update_incident ───────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_update_incident(
    incident_id: str,
    version: int,
    severity: Optional[int] = None,
    owner: Optional[str] = None,
    labels: Optional[list] = None,
    custom_fields: Optional[dict] = None,
) -> dict:
    """Update an XSOAR incident's metadata (upsert).

    Use to triage a case: reassign the owner, bump severity, set labels,
    or write custom fields. Only the fields you pass are changed.

    Optimistic concurrency: `version` is REQUIRED. XSOAR rejects a stale
    version with HTTP 409 — read the current value first via
    xsoar_get_incident (the `version` field) and pass it here.

    CustomFields use the lowercase MACHINE name (cliName), NOT the
    display label. Get the cliName for a type via xsoar_get_incident_fields.

    Args:
        incident_id: The XSOAR incident id.
        version: The incident's current version (from xsoar_get_incident).
            Required for the optimistic-concurrency check.
        severity: New severity level 1-4 (1 low … 4 critical). Optional.
        owner: New owner username. Optional.
        labels: List of label dicts [{type, value}] or simple strings.
            Optional. A bare scalar is wrapped.
        custom_fields: Dict of {cliName: value} written under
            CustomFields. Optional.

    Example body POSTed to /incident:
        {"id": "123", "version": 7, "severity": 4, "owner": "analyst1",
         "CustomFields": {"detectionsource": "Guardian"}}

    Returns:
        {ok, incident_id, updated: true}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")
    if version is None:
        raise ValueError(
            "version is required (optimistic concurrency). Read the current "
            "version via xsoar_get_incident first, then pass it here."
        )

    body: dict[str, Any] = {
        "id": str(incident_id),
        "version": _norm_int(version, 0),
    }
    if severity is not None:
        body["severity"] = _clamp_int(severity, 1, 0, 4)
    if owner is not None:
        body["owner"] = owner
    label_list = _as_list(labels)
    if label_list is not None:
        body["labels"] = label_list
    if custom_fields:
        if not isinstance(custom_fields, dict):
            return _err("custom_fields must be a dict of {cliName: value}")
        body["CustomFields"] = custom_fields

    fetcher = _get_fetcher()
    response = await fetcher.post("/incident", body)

    return {
        "incident_id": incident_id,
        "updated": True,
        "raw_response": response,
    }


# ─── xsoar_close_incident ────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_close_incident(
    incident_ids: list,
    close_reason: str,
    close_notes: Optional[str] = None,
) -> dict:
    """Close one or more XSOAR incidents in a single batch.

    Sets each matched case to status closed (2). Use at the end of an
    investigation once findings are documented.

    Args:
        incident_ids: List of incident ids to close. A bare id (string or
            int) is wrapped into a single-element list.
        close_reason: The XSOAR close reason (e.g. 'Resolved',
            'False Positive', 'Duplicate', 'Other'). Required.
        close_notes: Optional free-text closing summary.

    Example body POSTed to /incident/batchClose:
        {"closeReason": "Resolved", "closeNotes": "Confirmed benign.",
         "filter": {"id": ["123", "124"]}}

    Returns:
        {ok, closed_count, incident_ids}.
    """
    ids = _as_list(incident_ids)
    if not ids:
        raise ValueError("incident_ids must be a non-empty list of incident ids")
    if not close_reason:
        raise ValueError("close_reason is required")

    str_ids = [str(i) for i in ids]
    body: dict[str, Any] = {
        "closeReason": close_reason,
        "filter": {"id": str_ids},
    }
    if close_notes:
        body["closeNotes"] = close_notes

    fetcher = _get_fetcher()
    response = await fetcher.post("/incident/batchClose", body)

    return {
        "closed_count": len(str_ids),
        "incident_ids": str_ids,
        "close_reason": close_reason,
        "raw_response": response,
    }


# ─── xsoar_list_incident_types ───────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_list_incident_types() -> dict:
    """List the distinct incident TYPES present in this XSOAR tenant.

    XSOAR has no public list-incident-types endpoint, so this DERIVES
    the set by searching a window of recent incidents (size up to 200)
    and collecting their distinct `type` values. The result reflects the
    types actually IN USE on this tenant — which is what you want when
    picking a `type` for xsoar_get_incident_fields.

    Example body POSTed to /incidents/search:
        {"filter": {"page": 0, "size": 200,
                    "sort": [{"field": "created", "asc": false,
                              "fieldType": "date"}]}}

    Returns:
        {ok, incident_types: ['Phishing', 'Malware', ...], sampled}.
    """
    filt = {
        "page": 0,
        "size": 200,
        "sort": [{"field": "created", "asc": False, "fieldType": "date"}],
    }
    fetcher = _get_fetcher()
    response = await fetcher.post("/incidents/search", {"filter": filt})

    data = response.get("data") or []
    types = sorted({inc.get("type") for inc in data if inc.get("type")})

    return {
        "incident_types": types,
        "sampled": len(data),
        "derived": True,
    }


# ─── xsoar_get_incident_fields ───────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_get_incident_fields(incident_type: str) -> dict:
    """List the incident fields associated with a given incident type.

    Returns the field schema for the type — including each field's
    cliName (the lowercase machine name you must use as a CustomFields
    key in xsoar_update_incident). Use to discover what custom fields a
    Phishing/Malware/etc. case carries before writing to them.

    Args:
        incident_type: The incident type name (e.g. 'Phishing').
            Discover available types via xsoar_list_incident_types.

    Calls: GET /incidentfields/associatedTypes/{incident_type}

    Returns:
        {ok, fields: [{id, name, cliName, type, required}], count}.
    """
    if not incident_type:
        raise ValueError("incident_type is required")

    fetcher = _get_fetcher()
    response = await fetcher.get(
        f"/incidentfields/associatedTypes/{incident_type}"
    )

    raw_fields = response.get("data") if "data" in response else response
    if not isinstance(raw_fields, list):
        raw_fields = []

    fields = [
        {
            "id": f.get("id"),
            "name": f.get("name"),
            "cliName": f.get("cliName"),
            "type": f.get("type"),
            "required": f.get("required", False),
        }
        for f in raw_fields
        if isinstance(f, dict)
    ]

    return {
        "fields": fields,
        "count": len(fields),
        "incident_type": incident_type,
    }


# ─── xsoar_search_indicators ─────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_search_indicators(
    query: Optional[str] = None,
    page: int = 0,
    size: int = 50,
) -> dict:
    """Search the XSOAR threat-intel indicator store.

    Indicators are XSOAR's IoCs — IPs, domains, hashes, URLs with
    reputation + relationship context. Use to enrich an investigation:
    "is this IP a known indicator?", "show malicious domains seen this
    week".

    Args:
        query: Optional XSOAR indicator-search query (e.g.
            'type:IP and reputation:Bad', or a bare value like
            '1.2.3.4'). Omit to list recent indicators.
        page: Zero-based page index (default 0).
        size: Page size (default 50, max 200).

    Example body POSTed to /indicators/search:
        {"filter": {"query": "type:IP and reputation:Bad",
                    "page": 0, "size": 50}}

    Returns:
        {ok, indicators: [...], total}.
    """
    filt: dict[str, Any] = {
        "page": _norm_int(page, 0),
        "size": _clamp_int(size, 50, 1, 200),
    }
    if query:
        filt["query"] = query

    fetcher = _get_fetcher()
    response = await fetcher.post("/indicators/search", {"filter": filt})

    # XSOAR returns indicators under `iocObjects` (or `data` on the bare-
    # array path the fetcher normalized).
    indicators = response.get("iocObjects")
    if indicators is None:
        indicators = response.get("data") or []
    total = response.get("total", len(indicators))

    return {
        "indicators": indicators,
        "total": total,
        "result_count": len(indicators),
    }


# ─── xsoar_save_evidence ─────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_save_evidence(
    incident_id: str,
    entry_id: str,
    description: Optional[str] = None,
) -> dict:
    """Mark a war-room entry as evidence for an incident.

    XSOAR's evidence board collects the key artifacts that justify a
    case's conclusion. Use after xsoar_add_entry / xsoar_get_war_room to
    promote a specific entry (a command output, a screenshot, an
    analysis note) to evidence.

    Args:
        incident_id: The XSOAR incident id.
        entry_id: The war-room entry id to mark as evidence (from
            xsoar_add_entry's return or xsoar_get_war_room).
        description: Optional note describing why this is evidence.

    Example body POSTed to /evidence:
        {"incidentId": "123", "id": "456",
         "description": "lsass dump confirms credential theft"}

    Returns:
        {ok, evidence_id, incident_id, entry_id}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")
    if not entry_id:
        raise ValueError("entry_id is required")

    body: dict[str, Any] = {
        "incidentId": str(incident_id),
        "id": str(entry_id),
    }
    if description:
        body["description"] = description

    fetcher = _get_fetcher()
    response = await fetcher.post("/evidence", body)

    evidence_id = response.get("id") or (response.get("evidence") or {}).get("id")
    return {
        "evidence_id": evidence_id,
        "incident_id": incident_id,
        "entry_id": entry_id,
    }


# ─── xsoar_search_evidence ───────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_search_evidence(incident_id: str) -> dict:
    """List the evidence collected for one incident.

    Returns the entries promoted to the case's evidence board. Use to
    review what's already been flagged before drawing a conclusion.

    Args:
        incident_id: The XSOAR incident id whose evidence to list.

    Example body POSTed to /evidence/search:
        {"filter": {"incidentID": "123"}}

    Returns:
        {ok, evidence: [...], count}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")

    body = {"filter": {"incidentID": str(incident_id)}}
    fetcher = _get_fetcher()
    response = await fetcher.post("/evidence/search", body)

    # XSOAR returns the evidence list under `evidences` (or the
    # normalized `data` bare-array path).
    evidence = response.get("evidences")
    if evidence is None:
        evidence = response.get("data") or []

    return {
        "evidence": evidence,
        "count": len(evidence),
        "incident_id": incident_id,
    }


# ─── xsoar_health_check ──────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_health_check() -> dict:
    """Probe XSOAR server availability (the connector test path).

    GETs /health and reports reachability. Used by the connector
    instance-test flow + as a quick "is XSOAR up and are my credentials
    valid?" check. A 401/403 surfaces as an auth error envelope (server
    reachable but credentials bad).

    Calls: GET /health

    Returns:
        {ok, reachable: true, detail, generation: 'v6' | 'v8'}.
    """
    fetcher = _get_fetcher()
    response = await fetcher.get("/health")

    return {
        "reachable": True,
        "detail": response,
        "generation": "v8" if fetcher.is_v8 else "v6",
    }
