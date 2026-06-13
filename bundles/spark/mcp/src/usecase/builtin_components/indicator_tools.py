"""Indicator MCP tools — agent-facing IoC extraction + lookup (v0.2.0).

The agent records the indicators (IoCs) it extracts during an investigation,
and imports the SOAR's already-extracted indicators on case-fetch. Each is
deduped by (value, type), linked to the issue it was seen in, and shown in the
Investigation UI (Indicators subpage + the issue's Extracted-indicators
section).

Catalog-vs-credential boundary (root CLAUDE.md): indicators are investigation
metadata — NOT secrets, NOT platform catalogue membership. So these tools are
on the **safe (catalog) side** and ARE agent-callable. They read/write only
`investigation_store` — no SecretStore access.

Convention (mirrors investigation_tools): plain sync functions that fetch the
store via the `investigation_store()` singleton and return a JSON-able dict.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

from usecase.investigation_store import investigation_store


def _store():
    s = investigation_store()
    if s is None:
        return None, {"error": "investigation store not initialized on this MCP runtime"}
    return s, None


def indicator_upsert(
    value: str,
    type: str,
    issue_id: str | None = None,
    dbot_score: int | None = None,
    enrichment: Any = None,
    source: str = "guardian",
) -> dict[str, Any]:
    """Record an extracted IoC (indicator) and link it to an Issue.

    Call this for EACH indicator you extract or enrich during an investigation
    — and for each indicator the SOAR already extracted on a fetched case (pass
    source="xsoar"). Deduped by (value, type): re-seeing an IoC updates it +
    links the new issue, never duplicating. Shows on the Investigation →
    Indicators subpage and the issue's Extracted-indicators section.

    Args:
        value: The IoC value (e.g. "185.234.219.12", "evil.com", a SHA256, a CVE id).
        type: One of ip / domain / url / file_hash / email / cve / host / account.
        issue_id: The Issue this IoC was seen in (from issue_create) — links them.
        dbot_score: Optional reputation 0-3 (0 unknown · 1 good · 2 suspicious · 3 bad).
        enrichment: Optional dict OR JSON string of enrichment detail (sources,
            ASN, country, VT hits, …). Stored as JSON.
        source: "guardian" (you extracted it) or "xsoar" (imported from the SOAR).

    Example: indicator_upsert(value="185.234.219.12", type="ip", issue_id="<id>",
             dbot_score=3, enrichment={"country":"AT","vt_hits":5}, source="guardian")

    Returns: {"indicator": {...}} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    enr = None
    if enrichment is not None:
        enr = enrichment if isinstance(enrichment, str) else json.dumps(enrichment)
    try:
        ind = s.upsert_indicator(
            value=value, type=type, issue_id=issue_id,
            dbot_score=dbot_score, enrichment=enr, source=source or "guardian",
        )
    except ValueError as e:
        return {"error": str(e)}
    return {"indicator": dataclasses.asdict(ind)}


def indicators_list(type: str | None = None, issue_id: str | None = None) -> dict[str, Any]:
    """List indicators (IoCs), optionally filtered by type or by issue.

    Each comes with an `issue_count`. Use to check whether an IoC was already
    seen across other cases (cross-case correlation) before concluding.

    Args:
        type: filter to ip / domain / url / file_hash / email / cve / host / account.
        issue_id: filter to the indicators linked to a specific Issue.

    Returns: {"indicators": [...], "count": n}.
    """
    s, err = _store()
    if err:
        return err
    inds = s.list_indicators(type=type, issue_id=issue_id)
    return {"indicators": inds, "count": len(inds)}


def indicator_get(indicator_id: str) -> dict[str, Any]:
    """Fetch one indicator with the issues it appears in + its relationships.

    Returns: {"indicator": {..., "issues": [...], "relationships": [...]}}
    or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    ind = s.get_indicator(indicator_id)
    if ind is None:
        return {"error": f"indicator {indicator_id!r} not found"}
    ind["relationships"] = s.list_relationships(indicator_id)
    return {"indicator": ind}


def indicator_relate(
    indicator_id: str,
    relationship_type: str,
    target: str,
    target_type: str,
    description: str | None = None,
) -> dict[str, Any]:
    """Relate an indicator to another entity — the **attribution** action.

    Record a STIX-style relationship from an indicator to a target: another
    indicator, a MITRE ATT&CK technique, a malware/tool, a campaign, an
    intrusion-set, or a threat-actor. Use it to attribute an IoC (e.g. an IP
    `attributed-to` a threat-actor, a domain `resolves-to` an IP, an indicator
    `indicates` a malware family or `uses` a technique). Edges show on the
    indicator detail and feed the issue's Relations canvas.

    The relationship_type is a STIX verb stored verbatim, so it round-trips
    with the SOAR's EntityRelationship enum + MITRE ATT&CK. Common verbs:
    resolves-to · communicates-with · beacons-to · indicates · attributed-to ·
    uses · drops · downloads · related-to · variant-of · derived-from.

    Args:
        indicator_id: The source indicator (from indicators_list / indicator_get).
        relationship_type: STIX verb (e.g. "attributed-to", "resolves-to", "uses").
        target: The target's value — an indicator value, a technique id ("T1071.004"),
            a malware/campaign/actor name.
        target_type: STIX SDO type of the target — one of indicator, attack-pattern,
            malware, tool, campaign, intrusion-set, threat-actor, vulnerability, identity.
        description: Optional note (why the relationship holds).

    Returns: {"relationship": {...}} or {"error": ...}.
    """
    s, err = _store()
    if err:
        return err
    if s.get_indicator(indicator_id) is None:
        return {"error": f"indicator {indicator_id!r} not found"}
    try:
        edge = s.add_relationship(
            source_id=indicator_id, source_type="indicator",
            target_value=target, target_type=target_type,
            relationship_type=relationship_type, description=description, source="guardian",
        )
    except ValueError as e:
        return {"error": str(e)}
    return {"relationship": edge}
