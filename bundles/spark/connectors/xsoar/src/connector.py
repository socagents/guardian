"""Cortex XSOAR connector — tool implementations.

The Guardian incident-investigation agent's surface onto Cortex XSOAR.
Follows the standard Guardian connector structure: live config +
resolved secrets are read on every call via `from config.config import
get_config`, a stateless XSOARFetcher is built, and each tool POSTs (or
GETs) a logical XSOAR REST path. The fetcher applies the dual-
generation base-URL + header rules (v6 vs v8) — every tool here stays
generation-agnostic.

Tool catalog (21):
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
  ── action toolset (v0.2.0) ──
  xsoar_run_command           POST /entry/execute/sync — run any !command (playground)
  xsoar_enrich_indicator      POST /entry/execute/sync — ip/url/domain/file/cve reputation
  xsoar_complete_task         POST /entry/execute/sync — !taskComplete a playbook task
  xsoar_get_list              GET /lists/ — read an XSOAR list by name
  xsoar_set_list              POST /lists/save — overwrite/create a list
  xsoar_append_to_list        GET /lists/ + POST /lists/save — append to a list
  xsoar_create_incident       POST /incident — create a case
  xsoar_run_playbook          POST /inv-playbook/{pb}/{inv} — run a playbook on a case

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
import json
import re
import yaml
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
    "xsoar_list_integrations",
    "xsoar_run_command",
    "xsoar_enrich_indicator",
    "xsoar_complete_task",
    "xsoar_get_list",
    "xsoar_set_list",
    "xsoar_append_to_list",
    "xsoar_create_incident",
    "xsoar_run_playbook",
    "xsoar_import_playbook",
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
        "playground_id": getattr(proxy, "playground_id", None),
        "version": getattr(proxy, "version", None),
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
    version = cfg.get("version")

    return XSOARFetcher(
        str(api_url),
        str(api_key),
        api_id=str(api_id) if api_id not in (None, "") else None,
        verify_ssl=bool(verify_ssl),
        version=str(version) if version not in (None, "") else None,
    )


# ─── Command-engine helpers (playground war-room) ────────────────────


# XSOAR's "investigation not found" error markers — used to give a clean
# "bad playground_id" message instead of a raw 4xx.
_PLAYGROUND_NOT_FOUND_MARKERS = ("noInv", "Could not find investigation")


def _get_playground_id() -> str:
    """Resolve the playground/war-room investigation id from instance config.

    The three command-engine tools (run_command, enrich_indicator,
    complete_task) run XSOAR `!commands` inside a playground investigation,
    which needs an id. Raising ValueError here surfaces as the standard
    operator-actionable error envelope via _wrap_xsoar_call.
    """
    cfg = _get_xsoar_config()
    playground_id = cfg.get("playground_id")
    if not playground_id:
        raise ValueError(
            "playground_id is not configured on this XSOAR instance. Set it "
            "(the Playground / War Room investigation ID — find it in the XSOAR "
            "UI: open your Playground and copy the id from the URL) at "
            "/connectors to use run_command, enrich_indicator, or complete_task."
        )
    return str(playground_id)


def _parse_war_room_entries(response: Any) -> str:
    """Concatenate war-room entry `contents` from an execute/sync response.

    The fetcher normalizes a bare-array body into {"data": [...]}, so entries
    arrive under `data`; a single-entry dict is treated as one entry. type==4
    entries are errors (prefixed "Error:"). Unlike the reference port
    (docs/ref/trevor-mcp.py:541) we do NOT skip type==1 — in XSOAR type 1 is the
    standard note entry, so skipping it drops legitimate output (e.g. !Print).
    We include every entry that carries non-empty contents.
    """
    if isinstance(response, dict) and isinstance(response.get("data"), list):
        entries = response["data"]
    elif isinstance(response, list):
        entries = response
    elif isinstance(response, dict):
        entries = [response]
    else:
        entries = []

    parts: list[str] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        contents = e.get("contents")
        if contents in (None, ""):
            continue
        text = contents if isinstance(contents, str) else json.dumps(contents)
        parts.append(f"Error: {text}" if e.get("type") == 4 else text)

    return "\n".join(parts).strip() or "Command executed (no text output returned)."


def _quote_arg(value: object) -> str:
    """Double-quote a war-room command argument value.

    XSOAR `!command arg="value"` syntax. Embedded double-quotes are escaped;
    newlines pass through verbatim (verified — `!setList` stores multi-line
    listData correctly). Used to build !getList/!setList/!setPlaybook etc.
    """
    return '"' + str(value).replace('"', '\\"') + '"'


def _parse_getlist_output(output: str) -> Optional[str]:
    """Extract list data from a `!getList` war-room output.

    XSOAR returns `Done: list <name> was succesfully loaded:\\n\\n<DATA>` on
    success (note the upstream typo "succesfully"). Returns <DATA>, or None
    when the success marker is absent (list missing / command error) so the
    caller can surface a clean not-found.
    """
    marker = "loaded:"
    idx = output.find(marker)
    if idx == -1:
        return None
    return output[idx + len(marker):].strip()


def _command_reported_error(output: str) -> bool:
    """True when a war-room `!command` output signals failure, not success.

    XSOAR renders command errors as a leading `Error:` (e.g. `!setList` /
    `!createList` on a problem return `Error: Item not found`). Successful
    list writes return `Done: list <name> was updated`. The list-write tools
    previously returned ok=True regardless of the output, so a failed write
    looked successful — see the set_list/append_to_list fix (issue #45).
    Only the WRITE tools use this; get_list's "not found" is a legitimate
    result handled by _parse_getlist_output returning None.
    """
    s = (output or "").strip().lower()
    return s.startswith("error") or "item not found" in s


async def _execute_command(
    fetcher: XSOARFetcher,
    investigation_id: str,
    command: str,
    return_context_keys: Optional[str] = None,
) -> dict:
    """Run an XSOAR `!command` synchronously in an investigation's war room.

    Ports docs/ref/trevor-mcp.py:489-577. `investigation_id` is the war room to
    run in — the playground (run_command/enrich/complete_task/list tools) OR a
    specific incident's investigation (run_playbook targets the incident's own
    war room, since an incident id IS its investigation id). When
    return_context_keys (a comma-separated string) is given, each key's context
    is cleared before the run and retrieved after; otherwise only the war-room
    text is returned.

    Returns {output, context?} — context is present only when keys were asked
    for. Raises ValueError on a missing/invalid investigation (→ clean envelope).
    """
    keys = (
        [k.strip() for k in return_context_keys.split(",") if k.strip()]
        if return_context_keys
        else []
    )

    # 1. Clear context (best-effort — a clear failure must not abort the run).
    for key in keys:
        try:
            await fetcher.post(
                "/entry",
                {"investigationId": investigation_id, "data": f"!DeleteContext key={key}"},
            )
        except XSOARError:
            pass

    # 2. Execute synchronously.
    try:
        response = await fetcher.post(
            "/entry/execute/sync",
            {"investigationId": investigation_id, "data": command},
        )
    except XSOARRequestError as exc:
        if any(marker in str(exc) for marker in _PLAYGROUND_NOT_FOUND_MARKERS):
            raise ValueError(
                f"investigation '{investigation_id}' not found — check the id "
                f"(the instance's playground_id, or the incident id for run_playbook)."
            )
        raise

    output = _parse_war_room_entries(response)

    # 3. Retrieve requested context keys (literal ${Key} syntax).
    context: Optional[dict] = None
    if keys:
        context = {}
        for key in keys:
            try:
                context[key] = await fetcher.post(
                    f"/investigation/{investigation_id}/context",
                    {"query": f"${{{key}}}"},
                )
            except XSOARError as exc:
                context[key] = {"error": str(exc)}

    result: dict[str, Any] = {"output": output}
    if context is not None:
        result["context"] = context
    return result


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


_OPTIMISTIC_LOCK_RE = re.compile(r"has been modified \((-?\d+)\)")


async def _post_incident_resolving_version(
    fetcher: XSOARFetcher, body: dict, max_attempts: int = 5
) -> Any:
    """POST /incident, auto-resolving the optimistic-lock version.

    Cortex 8 enforces a per-incident `version` on writes, but the version
    returned by /incidents/search is unreliable (often -1). When the
    upsert is rejected with `errOptimisticLock`, XSOAR includes the
    server's CURRENT version in the message ("object has been modified
    (N)"). We parse N and retry with it. The version is a moving target
    (every war-room entry bumps it), so we retry a few times to absorb a
    concurrent bump between read and write.

    `body` is mutated in place so the caller sees the version that
    actually succeeded.
    """
    last_exc: Optional[Exception] = None
    for _ in range(max_attempts):
        try:
            return await fetcher.post("/incident", body)
        except XSOARRequestError as exc:
            msg = str(exc)
            if "errOptimisticLock" not in msg and "has been modified" not in msg:
                raise
            m = _OPTIMISTIC_LOCK_RE.search(msg)
            if not m:
                raise
            body["version"] = int(m.group(1))
            last_exc = exc
    if last_exc:
        raise last_exc
    raise XSOARError("update_incident: exhausted version-resolve retries")


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
    version: Optional[int] = None,
    severity: Optional[int] = None,
    owner: Optional[str] = None,
    labels: Optional[list] = None,
    custom_fields: Optional[dict] = None,
) -> dict:
    """Update an XSOAR incident's metadata (upsert).

    Use to triage a case: reassign the owner, bump severity, set labels,
    or write custom fields. Only the fields you pass are changed.

    Optimistic concurrency is handled automatically: XSOAR enforces a
    per-incident `version` on writes, but the version returned by search
    (xsoar_get_incident) is unreliable on Cortex 8 (often -1). So this
    tool resolves the live version on the fly — it submits the update,
    and if XSOAR rejects it with an optimistic-lock error it parses the
    server's current version out of the error and retries. You normally
    do NOT need to pass `version`; leave it unset.

    CustomFields use the lowercase MACHINE name (cliName), NOT the
    display label. Get the cliName for a type via xsoar_get_incident_fields.

    Args:
        incident_id: The XSOAR incident id.
        version: Optional. The incident's optimistic-lock version. Leave
            unset (default) to let the connector resolve it automatically.
        severity: New severity level 1-4 (1 low … 4 critical). Optional.
        owner: New owner username. Optional.
        labels: List of label dicts [{type, value}] or simple strings.
            Optional. A bare scalar is wrapped.
        custom_fields: Dict of {cliName: value} written under
            CustomFields. Optional.

    Returns:
        {ok, incident_id, updated: true, version: <resolved>}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")
    if custom_fields is not None and not isinstance(custom_fields, dict):
        return _err("custom_fields must be a dict of {cliName: value}")

    fetcher = _get_fetcher()

    # Cortex 8's POST /incident is a full-object upsert: posting a PARTIAL
    # incident ({id, version, labels}) is treated as a CREATE and fails
    # (playbook-lock / create errors). So read the current full record,
    # merge the requested changes, and post the whole object back. The
    # read-object's version is authoritative for the optimistic-lock
    # check (search-returned versions like -1 are unreliable).
    search = await fetcher.post("/incidents/search", {"filter": {"id": [str(incident_id)]}})
    data = search.get("data") if isinstance(search, dict) else None
    if not data:
        return _err(f"incident {incident_id} not found")
    inc: dict[str, Any] = dict(data[0])

    if severity is not None:
        inc["severity"] = _clamp_int(severity, 1, 0, 4)
    if owner is not None:
        inc["owner"] = owner
    label_list = _as_list(labels)
    if label_list is not None:
        existing = inc.get("labels") or []
        normalized = [
            x if isinstance(x, dict) else {"type": "Label", "value": x}
            for x in label_list
        ]
        inc["labels"] = existing + normalized
    if custom_fields:
        cf = dict(inc.get("CustomFields") or {})
        cf.update(custom_fields)
        inc["CustomFields"] = cf
    if version is not None:
        inc["version"] = _norm_int(version, inc.get("version", 0))

    response = await _post_incident_resolving_version(fetcher, inc)

    return {
        "incident_id": incident_id,
        "updated": True,
        "version": inc.get("version"),
        "raw_response": {"id": response.get("id"), "version": response.get("version")}
        if isinstance(response, dict) else response,
    }


# ─── xsoar_close_incident ────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_close_incident(
    incident_ids: list,
    close_reason: str,
    close_notes: Optional[str] = None,
) -> dict:
    """Close one or more XSOAR incidents.

    Sets each case to status closed (2). Use at the end of an
    investigation once findings are documented.

    Args:
        incident_ids: List of incident ids to close. A bare id (string or
            int) is wrapped into a single-element list.
        close_reason: The XSOAR close reason (e.g. 'Resolved',
            'False Positive', 'Duplicate', 'Other'). Required.
        close_notes: Optional free-text closing summary.

    Each id is closed via POST /incident/close (the `/incident/batchClose`
    endpoint is not exposed on the Cortex 8 public API). Per-id results are
    returned so a partial failure is visible.

    Example body POSTed to /incident/close:
        {"id": "123", "closeReason": "Resolved", "closeNotes": "Benign."}

    Returns:
        {ok, closed_count, incident_ids, results: [{id, closed, error?}]}.
    """
    ids = _as_list(incident_ids)
    if not ids:
        raise ValueError("incident_ids must be a non-empty list of incident ids")
    if not close_reason:
        raise ValueError("close_reason is required")

    str_ids = [str(i) for i in ids]
    fetcher = _get_fetcher()

    results: list[dict[str, Any]] = []
    closed = 0
    for cid in str_ids:
        body: dict[str, Any] = {"id": cid, "closeReason": close_reason}
        if close_notes:
            body["closeNotes"] = close_notes
        try:
            await fetcher.post("/incident/close", body)
            results.append({"id": cid, "closed": True})
            closed += 1
        except XSOARError as exc:
            results.append({"id": cid, "closed": False, "error": str(exc)})

    return {
        "closed_count": closed,
        "incident_ids": str_ids,
        "close_reason": close_reason,
        "results": results,
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
async def xsoar_get_incident_fields(incident_type: Optional[str] = None) -> dict:
    """List incident fields, optionally scoped to one incident type.

    Returns the field schema — including each field's cliName (the
    lowercase machine name you must use as a CustomFields key in
    xsoar_update_incident). Use to discover what custom fields a case
    carries before writing to them.

    The endpoint returns ALL incident fields; when `incident_type` is
    given, the result is filtered to fields associated with that type
    (or associated with all types). Cortex 8 has no public
    `/associatedTypes/{type}` endpoint, so the filtering is done here.

    Args:
        incident_type: Optional incident type name (e.g. 'Phishing') to
            scope the fields to. Omit to return every incident field.
            Discover types via xsoar_list_incident_types.

    Calls: GET /incidentfields

    Returns:
        {ok, fields: [{id, name, cliName, type, required, associatedTypes}],
         count, incident_type}.
    """
    fetcher = _get_fetcher()
    response = await fetcher.get("/incidentfields")

    raw_fields = response.get("data") if isinstance(response, dict) and "data" in response else response
    if not isinstance(raw_fields, list):
        raw_fields = []

    def _matches(f: dict) -> bool:
        if not incident_type:
            return True
        if f.get("associatedToAll"):
            return True
        assoc = f.get("associatedTypes") or []
        return isinstance(assoc, list) and incident_type in assoc

    fields = [
        {
            "id": f.get("id"),
            "name": f.get("name"),
            "cliName": f.get("cliName"),
            "type": f.get("type"),
            "required": f.get("required", False),
            "associatedTypes": f.get("associatedTypes"),
        }
        for f in raw_fields
        if isinstance(f, dict) and _matches(f)
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

    On Cortex 8 the `/evidence` POST endpoint is not exposed on the
    public API (it redirects to the SPA 404); evidence is promoted by
    tagging the war-room entry with the `evidence` tag, which is what
    this tool does via POST /entry/tags.

    Args:
        incident_id: The XSOAR incident id (the investigation id).
        entry_id: The war-room entry id to mark as evidence (from
            xsoar_add_entry's return or xsoar_get_war_room).
        description: Optional note describing why this is evidence
            (added as an extra tag when provided).

    Example body POSTed to /entry/tags:
        {"investigationId": "123", "id": "456@123", "tags": ["evidence"]}

    Returns:
        {ok, incident_id, entry_id, tagged: true}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")
    if not entry_id:
        raise ValueError("entry_id is required")

    tags = ["evidence"]
    body: dict[str, Any] = {
        "investigationId": str(incident_id),
        "id": str(entry_id),
        "tags": tags,
    }

    fetcher = _get_fetcher()
    response = await fetcher.post("/entry/tags", body)

    return {
        "incident_id": incident_id,
        "entry_id": entry_id,
        "tagged": True,
        "tags": tags,
        "raw_response": response,
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
        {"incidentID": "123"}

    Returns:
        {ok, evidence: [...], count}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")

    # Cortex 8 requires the incident id as a top-level `incidentID`
    # field (NOT nested under `filter`) — a missing/nested id returns
    # HTTP 400 "Incident ID must be specified in the request body".
    body = {"incidentID": str(incident_id)}
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
    """Probe XSOAR server availability + credential validity.

    Issues a minimal `POST /incidents/search` (size 1) and reports
    reachability + the total incident count. Used by the connector
    instance-test flow + as a quick "is XSOAR up and are my credentials
    valid?" check. A 401/403 surfaces as an auth error envelope (server
    reachable but credentials bad).

    (A dedicated `/health` endpoint is not exposed on the Cortex 8
    public API surface — it redirects to the SPA 404 — so the lightest
    real authenticated call is used as the probe instead.)

    Calls: POST /incidents/search {filter:{size:1}}

    Returns:
        {ok, reachable: true, total_incidents, generation: 'v6' | 'v8'}.
    """
    fetcher = _get_fetcher()
    response = await fetcher.post("/incidents/search", {"filter": {"page": 0, "size": 1}})

    total = response.get("total") if isinstance(response, dict) else None

    return {
        "reachable": True,
        "total_incidents": total,
        "generation": "v8" if fetcher.is_v8 else "v6",
    }


# ─── xsoar_list_integrations (integration + command discovery) ───────


def _integration_commands(entry: dict) -> list:
    """Pull an integration's command list from a search-response entry.

    Commands live under `integrationScript.commands[]` (the API surface of
    the integration YAML's `script.commands[]`); some surfaces also expose a
    flattened top-level `commands[]`. Returns [] when neither is present.
    """
    if not isinstance(entry, dict):
        return []
    script = entry.get("integrationScript")
    if isinstance(script, dict) and isinstance(script.get("commands"), list):
        return script["commands"]
    flat = entry.get("commands")
    return flat if isinstance(flat, list) else []


def _integration_enabled(inst: dict) -> bool:
    """True when a configured instance is enabled.

    XSOAR's integration surface returns `enabled` as the STRING "true"/"false"
    (not a JSON bool), so handle both forms.
    """
    v = inst.get("enabled")
    return v is True or (isinstance(v, str) and v.strip().lower() == "true")


@_wrap_xsoar_call
async def xsoar_list_integrations(
    brand: Optional[str] = None,
    enabled_only: bool = True,
    include_commands: bool = True,
    command_detail: bool = False,
    size: int = 1000,
) -> dict:
    """List the integrations configured on this XSOAR tenant + the commands each exposes.

    Discovery tool that PAIRS WITH xsoar_run_command: it tells you which
    integrations are actually wired up and which `!commands` you can run,
    instead of guessing. Without this you can call run_command but don't know
    what's available. Calls POST /settings/integration/search once and joins
    the configured instances to their integration definitions' command
    catalog. Does NOT require playground_id (a /settings endpoint, not the
    command engine).

    Args:
        brand: optional — filter to one integration (case-insensitive
            substring match on the integration brand or instance name, e.g.
            "virustotal", "splunk"). When set, full command argument specs are
            returned for that integration (implies command_detail).
        enabled_only: default true — return only ENABLED instances (the ones
            whose commands you can actually run). False also lists disabled
            instances.
        include_commands: default true — attach each integration's command
            list. False gives a fast name-only inventory.
        command_detail: default false — when true (or when `brand` is set),
            each command also carries its `arguments` (name / required /
            description) so you can build the exact `!command arg=value`
            string to pass to xsoar_run_command. Off keeps the response
            compact (command name + description only).
        size: max integration DEFINITIONS to scan for the command join
            (default 1000, max 2000) — a tenant exposes many integration
            definitions but only a few configured instances; a generous size
            ensures every configured instance's commands are found.

    Returns:
        {ok, integrations: [{brand, instance_name, enabled, category,
        command_count, commands: [{name, description, arguments?}]}], total}.
        `total` is the number of configured integrations returned.

    Example: xsoar_list_integrations(brand="VirusTotal") →
        {"ok": true, "total": 1, "integrations": [{"brand": "VirusTotal",
        "instance_name": "VT_prod", "enabled": true, "command_count": 6,
        "commands": [{"name": "file", "description": "Check file reputation",
        "arguments": [{"name": "file", "required": true, "description": "..."}]},
        ...]}]}
    """
    fetcher = _get_fetcher()
    want_detail = bool(command_detail) or bool(brand)
    n = _clamp_int(size, 1000, 1, 2000)

    resp = await fetcher.post("/settings/integration/search", {"size": n})
    if not isinstance(resp, dict):
        resp = {}

    # `configurations[]` = integration DEFINITIONS (hold the command catalog);
    # `instances[]` = the CONFIGURED instances. A bare-array response is
    # normalized to `data` by the client — treat that as the instance list.
    configurations = resp.get("configurations") or []
    instances = resp.get("instances")
    if instances is None:
        instances = resp.get("data") or []

    # Index command catalogs by brand from the definitions, so a configured
    # instance without its own embedded commands can borrow its brand's.
    commands_by_brand: dict[str, list] = {}
    for conf in configurations:
        if not isinstance(conf, dict):
            continue
        key = conf.get("brand") or conf.get("name")
        if key and str(key) not in commands_by_brand:
            commands_by_brand[str(key)] = _integration_commands(conf)

    def _shape_command(cmd: dict) -> dict:
        out: dict[str, Any] = {
            "name": cmd.get("name"),
            "description": (cmd.get("description") or "").strip(),
        }
        if want_detail:
            args = cmd.get("arguments")
            if isinstance(args, list):
                out["arguments"] = [
                    {
                        "name": a.get("name"),
                        "required": bool(a.get("required", False)),
                        "description": (a.get("description") or "").strip()[:240],
                    }
                    for a in args
                    if isinstance(a, dict)
                ]
        return out

    brand_filter = str(brand).strip().lower() if brand else None
    out_integrations: list[dict] = []
    for inst in instances:
        if not isinstance(inst, dict):
            continue
        if enabled_only and not _integration_enabled(inst):
            continue
        b = str(inst.get("brand") or inst.get("name") or "")
        name = str(inst.get("name") or "")
        if (
            brand_filter
            and brand_filter not in b.lower()
            and brand_filter not in name.lower()
        ):
            continue

        row: dict[str, Any] = {
            "brand": b,
            "instance_name": name,
            "enabled": _integration_enabled(inst),
            "category": inst.get("category") or "",
        }
        if include_commands:
            cmds = _integration_commands(inst) or commands_by_brand.get(b, [])
            shaped = [_shape_command(c) for c in cmds if isinstance(c, dict)]
            row["command_count"] = len(shaped)
            row["commands"] = shaped
        out_integrations.append(row)

    return {"integrations": out_integrations, "total": len(out_integrations)}


# ─── xsoar_run_command ───────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_run_command(
    command: str,
    return_context_keys: Optional[str] = None,
) -> dict:
    """Run an arbitrary Cortex XSOAR command in the playground war room.

    The escape hatch onto XSOAR's full command surface — run any `!command`
    (e.g. '!ip ip=8.8.8.8', '!Print value=hi', '!setIncident ...') synchronously
    and get the war-room output back. For indicator reputation specifically,
    prefer xsoar_enrich_indicator (it picks the right command + context keys).

    Requires the instance's playground_id to be set (the War Room the command
    runs in). Returns a clean error if it isn't.

    Args:
        command: The full XSOAR command including the leading '!'
            (e.g. '!ip ip=8.8.8.8'). Quote values with spaces.
        return_context_keys: Optional comma-separated XSOAR context keys to
            return as structured data after the run (e.g. 'IP,DBotScore'). Each
            key is cleared before the run and read back after. Omit to get only
            the war-room text output.

    Returns:
        {ok, output: <war-room text>, context?: {<key>: <value>, ...}}.
    """
    if not command:
        raise ValueError("command is required (e.g. '!ip ip=8.8.8.8')")
    playground_id = _get_playground_id()
    fetcher = _get_fetcher()
    return await _execute_command(fetcher, playground_id, command, return_context_keys)


# ─── xsoar_enrich_indicator ──────────────────────────────────────────


# Indicator-type → (command template, comma-separated context keys to return).
# Ported from docs/ref/trevor-mcp.py:580. The value is double-quoted into the
# command (e.g. !ip ip="8.8.8.8").
_ENRICH_CMD_MAP: dict[str, tuple[str, str]] = {
    "ip": ("!ip ip={}", "IP,DBotScore,IPinfo,AutoFocus"),
    "url": ("!url url={}", "URL,DBotScore,AutoFocus"),
    "domain": ("!domain domain={}", "Domain,DBotScore,Whois,AutoFocus"),
    "file": ("!file file={}", "File,DBotScore"),
    "cve": ("!cve cve_id={}", "CVE"),
}


@_wrap_xsoar_call
async def xsoar_enrich_indicator(indicator_type: str, value: str) -> dict:
    """Enrich an indicator (IoC) with reputation + threat context.

    Runs the matching XSOAR enrichment command in the playground and returns the
    structured DBotScore + reputation context. The investigation workhorse: "is
    this IP/domain/hash malicious?". Requires the instance's playground_id.

    Args:
        indicator_type: One of ip, url, domain, file, cve (case-insensitive).
        value: The indicator value (e.g. '8.8.8.8', 'evil.com', a SHA256, a
            CVE id like 'CVE-2024-1234').

    Returns:
        {ok, indicator_type, value, output, context: {<key>: <value>, ...}}
        where context carries the enrichment keys (e.g. IP, DBotScore).
    """
    if not value:
        raise ValueError("value is required")
    normalized = (indicator_type or "").lower()
    if normalized not in _ENRICH_CMD_MAP:
        return _err(
            f"unsupported indicator_type '{indicator_type}' "
            f"(expected one of: ip, url, domain, file, cve)"
        )
    template, context_keys = _ENRICH_CMD_MAP[normalized]
    command = template.format(f'"{value}"')

    playground_id = _get_playground_id()
    fetcher = _get_fetcher()
    result = await _execute_command(fetcher, playground_id, command, context_keys)
    return {"indicator_type": normalized, "value": value, **result}


# ─── xsoar_complete_task ─────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_complete_task(
    incident_id: str,
    task_id: str,
    comment: Optional[str] = None,
) -> dict:
    """Complete a playbook / war-room task on an incident.

    Runs XSOAR's `!taskComplete` command (a war-room automation command, not a
    REST endpoint) in the playground, targeting the given incident's task. Use
    to advance a stuck playbook task. Requires the instance's playground_id.

    Args:
        incident_id: The XSOAR incident id that owns the task.
        task_id: The playbook task id (or tag) to complete.
        comment: Optional completion note recorded on the task.

    Returns:
        {ok, incident_id, task_id, output}.
    """
    if not incident_id:
        raise ValueError("incident_id is required")
    if not task_id:
        raise ValueError("task_id is required")
    command = f"!taskComplete id={task_id} incidentId={incident_id}"
    if comment:
        command += f' comment="{comment}"'

    playground_id = _get_playground_id()
    fetcher = _get_fetcher()
    result = await _execute_command(fetcher, playground_id, command)
    return {"incident_id": incident_id, "task_id": task_id, **result}


# ─── xsoar_get_list / set_list / append_to_list (command engine) ─────
#
# Cortex XSOAR 8 / Cortex cloud does NOT serve the v6 `GET /lists/` REST
# endpoint (it returns HTTP 500). The reliable cross-generation path is the
# war-room list commands run via the playground: `!getList` (read) +
# `!createList` (create-or-overwrite write). So the three list tools route
# through the command engine and require the instance's playground_id — same
# as run_command / enrich_indicator.
#
# Issue #45: writes use `!createList`, NOT `!setList`. `!setList` only UPDATES
# an EXISTING list — on a new list it returns `Error: Item not found`, so the
# list was never created (and the connector used to mask that as ok=True).
# `!createList` creates the list if missing and overwrites it if present.


@_wrap_xsoar_call
async def xsoar_get_list(name: str) -> dict:
    """Read a Cortex XSOAR list (a named line/key list) by name.

    XSOAR Lists hold reusable data — allow/block lists, lookup tables, config.
    Reads via the `!getList` war-room command, so the instance's playground_id
    must be configured.

    Args:
        name: The list name.

    Returns:
        {ok, name, data} where data is the list's raw contents, or
        {ok: false, error} when the list doesn't exist / can't be read.
    """
    if not name:
        raise ValueError("name is required")
    playground_id = _get_playground_id()
    fetcher = _get_fetcher()
    result = await _execute_command(fetcher, playground_id, f"!getList listName={_quote_arg(name)}")
    data = _parse_getlist_output(result.get("output", ""))
    if data is None:
        return _err(
            f"list '{name}' not found or unreadable",
            name=name,
            detail=result.get("output"),
        )
    return {"name": name, "data": data}


@_wrap_xsoar_call
async def xsoar_set_list(name: str, data: str) -> dict:
    """Create or overwrite a Cortex XSOAR list.

    Writes the full contents — CREATING the list if it doesn't exist — via the
    `!createList` war-room command, so the instance's playground_id must be
    configured. (Issue #45: `!setList` only UPDATES an existing list and
    returns `Error: Item not found` for a new one; `!createList` is the
    create-or-overwrite command.) To add a single value without clobbering the
    rest, use xsoar_append_to_list.

    Args:
        name: The list name.
        data: The full list contents (often newline-separated lines).

    Returns:
        {ok, name, output} on success, or {ok: false, error, detail} when the
        list write fails.
    """
    if not name:
        raise ValueError("name is required")
    playground_id = _get_playground_id()
    fetcher = _get_fetcher()
    command = f"!createList listName={_quote_arg(name)} listData={_quote_arg(data if data is not None else '')}"
    result = await _execute_command(fetcher, playground_id, command)
    output = result.get("output", "")
    if _command_reported_error(output):
        return _err(f"could not create or update list '{name}'", name=name, detail=output)
    return {"name": name, "output": output}


@_wrap_xsoar_call
async def xsoar_append_to_list(name: str, value: str) -> dict:
    """Append a value (as a new line) to a Cortex XSOAR list.

    Read-modify-write via the `!getList` + `!createList` war-room commands, so
    the instance's playground_id must be configured. CREATES the list with
    `value` if it doesn't exist yet (issue #45: `!createList`, not `!setList`,
    is the create-or-overwrite command). Use to add an IoC to a block/allow
    list during response without overwriting the rest.

    Args:
        name: The list name.
        value: The value to append (added on its own line).

    Returns:
        {ok, name, data} with the post-append contents, or
        {ok: false, error, detail} when the write fails.
    """
    if not name:
        raise ValueError("name is required")
    if value is None:
        raise ValueError("value is required")
    playground_id = _get_playground_id()
    fetcher = _get_fetcher()

    current = _parse_getlist_output(
        (await _execute_command(fetcher, playground_id, f"!getList listName={_quote_arg(name)}")).get("output", "")
    )
    new_data = f"{current}\n{value}" if current else str(value)
    result = await _execute_command(
        fetcher, playground_id, f"!createList listName={_quote_arg(name)} listData={_quote_arg(new_data)}"
    )
    output = result.get("output", "")
    if _command_reported_error(output):
        return _err(f"could not append to list '{name}'", name=name, detail=output)
    return {"name": name, "data": new_data}


# ─── xsoar_create_incident ───────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_create_incident(
    name: str,
    incident_type: Optional[str] = None,
    severity: Optional[int] = None,
    details: Optional[str] = None,
    owner: Optional[str] = None,
    labels: Optional[list] = None,
    custom_fields: Optional[dict] = None,
    create_investigation: bool = True,
) -> dict:
    """Create a new Cortex XSOAR incident (case).

    Use to open a case from Guardian — e.g. to record a finding as a tracked
    incident. Only `name` is required; createInvestigation spins up the war room.

    Args:
        name: The incident name/title (required).
        incident_type: The XSOAR incident type (e.g. 'Phishing'). Discover types
            via xsoar_list_incident_types. Optional.
        severity: Severity level 0-4 (0 unknown … 4 critical). Optional.
        details: Free-text description / details. Optional.
        owner: Owner username. Optional.
        labels: List of label strings (or [{type, value}] dicts). Optional.
        custom_fields: Dict of {cliName: value} written under CustomFields
            (lowercase machine names from xsoar_get_incident_fields). Optional.
        create_investigation: Create the war-room investigation (default True).

    Returns:
        {ok, incident_id, name, created: true}.
    """
    if not name:
        raise ValueError("name is required")
    if custom_fields is not None and not isinstance(custom_fields, dict):
        return _err("custom_fields must be a dict of {cliName: value}")

    body: dict[str, Any] = {"name": name, "createInvestigation": bool(create_investigation)}
    if incident_type:
        body["type"] = incident_type
    if severity is not None:
        body["severity"] = _clamp_int(severity, 0, 0, 4)
    if details:
        body["details"] = details
    if owner:
        body["owner"] = owner
    label_list = _as_list(labels)
    if label_list is not None:
        body["labels"] = [
            x if isinstance(x, dict) else {"type": "Label", "value": x}
            for x in label_list
        ]
    if custom_fields:
        body["CustomFields"] = custom_fields

    fetcher = _get_fetcher()
    response = await fetcher.post("/incident", body)

    incident_id = response.get("id") if isinstance(response, dict) else None
    return {
        "incident_id": incident_id,
        "name": name,
        "created": True,
        "raw_response": {"id": incident_id, "version": response.get("version")}
        if isinstance(response, dict) else response,
    }


# ─── xsoar_run_playbook ──────────────────────────────────────────────


@_wrap_xsoar_call
async def xsoar_run_playbook(incident_id: str, playbook_id: str) -> dict:
    """Assign + run a playbook on an existing XSOAR incident.

    Runs the `!setPlaybook` war-room command IN the target incident's own war
    room (an incident id IS its investigation id), which assigns the playbook
    and starts it. This does NOT use the playground — it runs in the incident's
    investigation directly — so it does NOT require playground_id (but the
    incident must have an investigation: created with createInvestigation).

    Cortex 8 note: the v6 `POST /inv-playbook/{pb}/{inv}` REST endpoint is not
    served on Cortex cloud (it 303-redirects); the war-room command path works
    on both generations.

    Args:
        incident_id: The XSOAR incident id (its investigation id) to run on.
        playbook_id: The playbook name to assign and run.

    Returns:
        {ok, incident_id, playbook_id, output}, or {ok:false, error} when the
        playbook isn't found / the incident has no investigation.
    """
    if not incident_id:
        raise ValueError("incident_id is required")
    if not playbook_id:
        raise ValueError("playbook_id is required")

    fetcher = _get_fetcher()
    # Run in the incident's OWN investigation (not the playground).
    result = await _execute_command(
        fetcher, str(incident_id), f"!setPlaybook name={_quote_arg(playbook_id)}"
    )
    output = result.get("output", "")
    if "was not found" in output or output.lower().startswith("error"):
        return _err(
            f"run_playbook failed: {output}",
            incident_id=incident_id,
            playbook_id=playbook_id,
        )
    return {
        "incident_id": incident_id,
        "playbook_id": playbook_id,
        "output": output,
    }


# ─── xsoar_import_playbook ───────────────────────────────────────────
#
# Cortex 8 import path (issue #46). The v6 `POST /playbook/import` (multipart
# YAML) is NOT proxied by the Cortex 8 public API gateway (405). When the Core
# REST API integration is installed AND the instance has a playground_id, we
# import via that integration's command engine instead:
#
#   !core-api-post uri=/playbook/save body=`[<playbook-as-json>]`
#
# run in the playground war room. /playbook/save takes a JSON ARRAY of
# playbooks (verified live on Cortex 8: a single object → 400 "cannot
# unmarshal object into []domain.Playbook"; the array form creates the
# playbook). yaml.safe_load also accepts JSON, so a JSON playbook works too.


async def _import_via_core_api(fetcher: XSOARFetcher, playbook_yaml: str) -> Optional[dict]:
    """Cortex 8 fallback: import a playbook through the Core REST API
    integration (core-api-post → /playbook/save), executed in the instance's
    playground. Returns a success/error envelope, or None when no playground_id
    is configured (the caller then surfaces the guided-manual message)."""
    cfg = _get_xsoar_config()
    playground_id = cfg.get("playground_id")
    if not playground_id:
        return None
    try:
        pb = yaml.safe_load(playbook_yaml)
    except yaml.YAMLError as exc:
        return _err(f"playbook_yaml is not valid YAML/JSON: {exc}")
    if not isinstance(pb, dict):
        return _err("playbook_yaml must define a single playbook object (mapping)")
    # /playbook/save expects a JSON ARRAY of playbooks.
    body = json.dumps([pb], separators=(",", ":"))
    if "`" in body:
        return _err(
            "playbook content contains a backtick, which the war-room command "
            "engine can't pass safely — import this playbook manually via "
            "Playbooks → Import.",
            import_unavailable=True,
        )
    command = f"!core-api-post uri=/playbook/save body=`{body}`"
    result = await _execute_command(fetcher, str(playground_id), command)
    output = result.get("output", "") or ""
    if _command_reported_error(output):
        return _err(
            "Core REST API import failed (core-api-post /playbook/save).",
            reason="core_api_save_failed",
            detail=output[:600],
        )
    # Success — best-effort extract the saved playbook id/name from the
    # {"response":[{...}]} body; fall back to the YAML's own id/name.
    playbook_id = pb.get("id")
    playbook_name = pb.get("name")
    try:
        saved = json.loads(output).get("response")
        if isinstance(saved, list) and saved and isinstance(saved[0], dict):
            playbook_id = saved[0].get("id", playbook_id)
            playbook_name = saved[0].get("name", playbook_name)
    except (ValueError, AttributeError):
        pass
    return {
        "playbook_id": playbook_id,
        "playbook_name": playbook_name,
        "imported": True,
        "via": "core-api",
        "raw_response": output[:600],
    }


@_wrap_xsoar_call
async def xsoar_import_playbook(
    playbook_yaml: str,
    filename: Optional[str] = None,
) -> dict:
    """Import (deploy) a playbook DEFINITION into the Cortex XSOAR tenant.

    Uploads the playbook YAML to XSOAR's playbook-import endpoint so the
    playbook appears in the tenant's library, ready to assign + run. This is
    distinct from xsoar_run_playbook, which RUNS an already-existing playbook
    by name. To deploy + test-run a freshly authored playbook, pair them:
    import here → xsoar_create_incident → xsoar_run_playbook on that incident.

    The YAML must be a valid XSOAR playbook (id, name, starttaskid, tasks…);
    validate structure first with playbook_validate. This WRITES to the tenant
    — it is approval-gated like every connector action.

    Path by generation: XSOAR 6 uses the direct `POST /playbook/import`
    (multipart). Cortex 8's public API doesn't proxy that (405), so — when the
    Core REST API integration is installed AND the instance has a playground_id
    — Guardian imports via that integration (core-api-post → /playbook/save).
    Without the integration/playground, returns a guided-manual message
    (import_unavailable=True).

    Args:
        playbook_yaml: The full playbook definition as a YAML (or JSON) string.
        filename: Optional upload filename (default 'guardian-playbook.yml';
            used only on the direct v6 multipart path).

    Returns:
        {ok, playbook_id, playbook_name, imported, raw_response} (with `via:
        "core-api"` on the Cortex 8 path) or {ok:false, error}.
    """
    if not playbook_yaml or not playbook_yaml.strip():
        raise ValueError("playbook_yaml is required")

    fname = filename or "guardian-playbook.yml"
    fetcher = _get_fetcher()
    files = {
        "file": (fname, playbook_yaml.encode("utf-8"), "application/octet-stream"),
    }
    try:
        response = await fetcher.post_multipart("/playbook/import", files=files)
    except XSOARRequestError as exc:
        # Cortex 8's public API gateway doesn't proxy /playbook/import (405),
        # and v6 REST endpoints 303-redirect on Cortex 8. When the direct path
        # is unavailable, try the Core REST API integration path (issue #46):
        # core-api-post → /playbook/save run in the playground. That needs the
        # integration installed AND a playground_id; if either is missing we
        # fall through to the guided-manual message (still correct behavior).
        msg = str(exc)
        _markers = ("405", "method not allowed", "redirect", "not served")
        if any(m in msg.lower() for m in _markers):
            via_core_api = await _import_via_core_api(fetcher, playbook_yaml)
            if via_core_api is not None:
                return via_core_api  # Core REST API import succeeded (or its own error)
            return _err(
                "Direct playbook import isn't available on this tenant's public "
                "API. For one-click import, install the Core REST API "
                "integration AND set this instance's playground_id (the "
                "Playground / War Room investigation ID) at /connectors — "
                "Guardian then imports via that integration. Otherwise import "
                "the YAML manually via Playbooks → Import. The test-run still "
                "works once the playbook exists in the tenant.",
                import_unavailable=True,
                reason="import_endpoint_unavailable_and_no_core_api_path",
                detail=msg,
            )
        raise

    # XSOAR returns the imported playbook object, or {data:[...]} for a bare
    # array body — normalize to the first playbook's id/name.
    pb: Any = response
    if (
        isinstance(response, dict)
        and isinstance(response.get("data"), list)
        and response["data"]
    ):
        pb = response["data"][0]
    playbook_id = pb.get("id") if isinstance(pb, dict) else None
    playbook_name = pb.get("name") if isinstance(pb, dict) else None

    return {
        "playbook_id": playbook_id,
        "playbook_name": playbook_name,
        "imported": True,
        "raw_response": response,
    }
