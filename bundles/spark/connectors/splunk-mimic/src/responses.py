"""splunkd response builders — the exact byte shapes splunklib parses.

splunklib expects:
  * auth/login  → XML with a <sessionKey> element;
  * search/jobs (create) → XML with a <sid> element;
  * job status  → JSON `entry[0].content` with dispatchState/isDone/...;
  * results     → JSON {preview, init_offset, messages, fields, results}.

Keeping these in one module makes the byte-format contract auditable in a
single place; the round-trip test (test_server.py) proves splunklib accepts
them.
"""

from __future__ import annotations

from typing import Any
from xml.sax.saxutils import escape


def auth_xml(session_key: str) -> str:
    """POST /services/auth/login success body. splunklib reads <sessionKey>."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<response>\n"
        f"  <sessionKey>{escape(session_key)}</sessionKey>\n"
        '  <messages>\n    <msg code=""></msg>\n  </messages>\n'
        "</response>"
    )


def auth_error_xml(message: str = "Login failed") -> str:
    """401 body for a rejected login. splunklib raises AuthenticationError."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<response>\n"
        "  <messages>\n"
        f'    <msg type="WARN">{escape(message)}</msg>\n'
        "  </messages>\n"
        "</response>"
    )


def sid_xml(sid: str) -> str:
    """POST /services/search/jobs (non-oneshot) body. splunklib reads <sid>."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f"<response>\n  <sid>{escape(sid)}</sid>\n</response>"
    )


def job_status_json(sid: str, result_count: int) -> dict[str, Any]:
    """GET /services/search/jobs/{sid}?output_mode=json — a completed job.

    splunklib's Job.state reads entry[0].content; SplunkPy reads
    dispatchState / isDone / doneProgress / resultCount. The mimic completes
    jobs instantly so dispatchState is always DONE.
    """
    return {
        "links": {},
        "origin": "",
        "updated": "",
        "generator": {"build": "mimic", "version": "9.0.0"},
        "entry": [
            {
                "name": sid,
                "id": f"https://localhost:8089/services/search/jobs/{sid}",
                "content": {
                    "sid": sid,
                    "dispatchState": "DONE",
                    "isDone": True,
                    "isFailed": False,
                    "isFinalized": False,
                    "isPaused": False,
                    "isZombie": False,
                    "doneProgress": 1.0,
                    "resultCount": result_count,
                    "eventCount": result_count,
                    "resultPreviewCount": result_count,
                    "scanCount": result_count,
                    "statusBuckets": 0,
                    "ttl": 600,
                },
            }
        ],
        "paging": {"total": 1, "perPage": 30, "offset": 0},
    }


# ── ATOM feeds — splunklib reads MANAGEMENT entities as ATOM XML ─────────
#
# splunklib's data.load parses Splunk's `s:dict`/`s:key`/`s:list` structure
# under <feed><entry><content>. server/info and job status are read this way
# (only search RESULTS come back as JSON). Values are strings, the way real
# splunkd renders them (e.g. isDone "1", doneProgress "1.0").

_ATOM_NS = "http://www.w3.org/2005/Atom"
_REST_NS = "http://dev.splunk.com/ns/rest"


def _sdict_xml(d: dict[str, Any], indent: str = "      ") -> str:
    lines = [f"{indent}<s:dict>"]
    for k, v in d.items():
        key = escape(str(k))
        if isinstance(v, dict):
            lines.append(f'{indent}  <s:key name="{key}">')
            lines.append(_sdict_xml(v, indent + "    "))
            lines.append(f"{indent}  </s:key>")
        elif isinstance(v, (list, tuple)):
            lines.append(f'{indent}  <s:key name="{key}">')
            lines.append(f"{indent}    <s:list>")
            for item in v:
                lines.append(f"{indent}      <s:item>{escape(str(item))}</s:item>")
            lines.append(f"{indent}    </s:list>")
            lines.append(f"{indent}  </s:key>")
        else:
            lines.append(f'{indent}  <s:key name="{key}">{escape(str(v))}</s:key>')
    lines.append(f"{indent}</s:dict>")
    return "\n".join(lines)


def atom_entry_feed(title: str, content: dict[str, Any]) -> str:
    """A single-entry ATOM feed whose content is `content` as an s:dict —
    the shape splunklib's _load_atom + _parse_atom_entry consume for an
    entity read (server/info, a search job)."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<feed xmlns="{_ATOM_NS}" xmlns:s="{_REST_NS}">\n'
        f"  <title>{escape(title)}</title>\n"
        "  <entry>\n"
        f"    <title>{escape(title)}</title>\n"
        '    <content type="text/xml">\n'
        f"{_sdict_xml(content)}\n"
        "    </content>\n"
        "  </entry>\n"
        "</feed>"
    )


def server_info_atom(version: str = "8.2.0") -> str:
    """server/info as ATOM. version < 9.0.2 keeps splunklib on the v1
    search/jobs path (its disable_v2_api gate), avoiding the v2 endpoints —
    and matches the older bundled SDK the XSOAR SplunkPy integration uses.
    instance_type is omitted so splunklib treats it as on-prem (not cloud)."""
    return atom_entry_feed(
        "server-info",
        {
            "version": version,
            "build": "mimic",
            "serverName": "splunk-mimic",
            "isFree": "0",
            "isTrial": "0",
            "licenseState": "OK",
            "server_roles": ["search_head", "indexer"],
        },
    )


def job_status_atom(sid: str, result_count: int) -> str:
    """A search job entity as ATOM — always DONE (the mimic completes
    instantly). splunklib's Job.is_done()/results gate on these keys.

    NOTE: unlike server/info (a feed read via entry/content/*), splunklib's
    Job._load_atom_entry reads `_load_atom(response).entry` — i.e. it expects
    the <entry> at the ROOT of the response, NOT wrapped in <feed>. So this
    builder emits a root <entry> directly.
    """
    content = {
            # eai:acl populates splunklib's entity namespace (_state.access);
            # without it, Job._proper_namespace dereferences a None access on
            # the second refresh and crashes.
            "eai:acl": {
                "owner": "nobody",
                "app": "search",
                "sharing": "global",
                "modifiable": "1",
                "can_write": "1",
            },
            "sid": sid,
            "dispatchState": "DONE",
            "isDone": "1",
            "isFailed": "0",
            "isFinalized": "0",
            "isPaused": "0",
            "isZombie": "0",
            "doneProgress": "1.0",
            "resultCount": str(result_count),
            "eventCount": str(result_count),
            "resultPreviewCount": str(result_count),
            "scanCount": str(result_count),
            "statusBuckets": "0",
            "ttl": "600",
    }
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<entry xmlns="{_ATOM_NS}" xmlns:s="{_REST_NS}">\n'
        f"  <title>{escape(sid)}</title>\n"
        '  <content type="text/xml">\n'
        f"{_sdict_xml(content)}\n"
        "  </content>\n"
        "</entry>"
    )


def results_json(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """GET .../results?output_mode=json (and oneshot) — splunklib's
    JSONResultsReader / ResultsReader consume {fields, results}.

    `fields` is the union of keys across rows (Splunk advertises every
    column it returned); `results` is the rows verbatim.
    """
    field_names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                field_names.append(key)
    return {
        "preview": False,
        "init_offset": 0,
        "messages": [],
        "fields": [{"name": name} for name in field_names],
        "results": rows,
    }
