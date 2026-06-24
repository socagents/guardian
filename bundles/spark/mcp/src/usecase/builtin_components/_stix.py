"""STIX 2.1 bundle assembly from the structured investigation record (stage D).

Pure assembly — no external calls, no new deps (the runtime has no `stix2`
library). IDs are deterministic (uuid5 over the source value), so re-exporting
the same Issue/Case yields a byte-identical bundle. The Guardian record maps to
STIX as: Issue → `incident`; technique_mappings → `attack-pattern` (with the
MITRE external reference); indicators → `indicator` (a STIX pattern); the C
rollup's threat_actor → `threat-actor`; the Case → `campaign` + `grouping`; and
the relationships graph → `relationship` objects. A `report` / `grouping` SDO
wraps everything so the bundle reads as one investigation.
"""
from __future__ import annotations

import uuid
from typing import Any

# Fixed namespace so uuid5 ids are stable across runs/processes.
_NS = uuid.UUID("6f3b1e2a-9c4d-5e6f-8a7b-0c1d2e3f4a5b")
_GUARDIAN_TS = "2026-01-01T00:00:00.000Z"


def _sid(stype: str, key: str) -> str:
    return f"{stype}--{uuid.uuid5(_NS, f'{stype}:{key}')}"


def _ts(value: str | None) -> str:
    """Coerce a stored 'YYYY-MM-DDTHH:MM:SSZ' to a STIX RFC3339 timestamp."""
    if not value:
        return _GUARDIAN_TS
    return value if "." in value else value.replace("Z", ".000Z")


def _identity() -> dict:
    return {
        "type": "identity", "spec_version": "2.1", "id": _sid("identity", "guardian"),
        "created": _GUARDIAN_TS, "modified": _GUARDIAN_TS,
        "name": "Guardian", "identity_class": "system",
        "description": "Guardian incident-investigation agent",
    }


_GUARDIAN_ID = _sid("identity", "guardian")


def _ind_pattern(value: str, itype: str) -> str:
    v = (value or "").replace("\\", "\\\\").replace("'", "\\'")
    return {
        "ip": f"[ipv4-addr:value = '{v}']",
        "domain": f"[domain-name:value = '{v}']",
        "url": f"[url:value = '{v}']",
        "email": f"[email-addr:value = '{v}']",
        "file_hash": f"[file:hashes.'SHA-256' = '{v}']",
    }.get(itype, f"[x-guardian-indicator:value = '{v}']")


def _attack_pattern(technique_id: str, tactic: str | None) -> dict:
    ap = {
        "type": "attack-pattern", "spec_version": "2.1",
        "id": _sid("attack-pattern", technique_id),
        "created": _GUARDIAN_TS, "modified": _GUARDIAN_TS,
        "created_by_ref": _GUARDIAN_ID, "name": technique_id,
        "external_references": [{"source_name": "mitre-attack", "external_id": technique_id}],
    }
    if tactic:
        ap["kill_chain_phases"] = [{"kill_chain_name": "mitre-attack", "phase_name": tactic}]
    return ap


def _indicator(ind) -> dict:
    return {
        "type": "indicator", "spec_version": "2.1",
        "id": _sid("indicator", f"{ind.type}:{ind.value}"),
        "created": _ts(ind.created_at), "modified": _ts(ind.updated_at),
        "created_by_ref": _GUARDIAN_ID,
        "name": f"{ind.type}: {ind.value}",
        "pattern": _ind_pattern(ind.value, ind.type),
        "pattern_type": "stix", "valid_from": _ts(ind.first_seen),
    }


def _relationship(src_ref: str, rel_type: str, tgt_ref: str) -> dict:
    return {
        "type": "relationship", "spec_version": "2.1",
        "id": _sid("relationship", f"{src_ref}|{rel_type}|{tgt_ref}"),
        "created": _GUARDIAN_TS, "modified": _GUARDIAN_TS,
        "created_by_ref": _GUARDIAN_ID,
        "relationship_type": rel_type, "source_ref": src_ref, "target_ref": tgt_ref,
    }


def _issue_objects(store, issue) -> tuple[dict, list[dict]]:
    """Return (incident_sdo, [all related objects]) for one Issue."""
    incident = {
        "type": "incident", "spec_version": "2.1",
        "id": _sid("incident", issue.id),
        "created": _ts(issue.created_at), "modified": _ts(issue.updated_at),
        "created_by_ref": _GUARDIAN_ID,
        "name": issue.title,
        "description": (issue.summary or issue.conclusions or "")[:4000],
    }
    objs: list[dict] = []

    # indicators (deduped by stix id within this bundle)
    ind_sdo_by_value: dict[str, str] = {}
    for ind in store.list_indicators_for_issue(issue.id):
        sdo = _indicator(ind)
        objs.append(sdo)
        ind_sdo_by_value[ind.value] = sdo["id"]
        objs.append(_relationship(sdo["id"], "related-to", incident["id"]))

    # attack-patterns
    ap_id_by_technique: dict[str, str] = {}
    for t in store.list_technique_mappings(issue.id):
        ap = _attack_pattern(t.technique_id, t.tactic)
        objs.append(ap)
        ap_id_by_technique[t.technique_id] = ap["id"]
        objs.append(_relationship(incident["id"], "related-to", ap["id"]))

    # stored relationship graph → STIX relationships.
    #
    # #INV-F4 — previously the target ref was resolved ONLY via the
    # indicator-value map, so any edge whose target is an attack-pattern /
    # malware / threat-actor / campaign (target_value like 'T1071.004' or a
    # malware name, never an indicator value) silently resolved to None and
    # the edge was dropped. Now we resolve the target ref by target_type:
    # indicator targets via the value map (as before), attack-pattern targets
    # via the technique→SDO map built above. We still require BOTH ends to be
    # real objects in THIS bundle (fail-closed: no dangling target_ref that
    # would make the bundle fail STIX validation), so an edge to an SDO not
    # present in the bundle is still skipped — but matched attack-pattern
    # edges now connect instead of vanishing.
    for r in store.list_relationships():
        src = store.get_indicator(r["source_id"])
        if not src:
            continue
        src_ref = ind_sdo_by_value.get(src["value"])
        if not src_ref:
            continue
        tgt_type = (r.get("target_type") or "").lower()
        tgt_value = r["target_value"]
        if tgt_type in ("attack-pattern", "attack_pattern", "technique"):
            tgt_ref = ap_id_by_technique.get(tgt_value)
        else:
            # indicator (and any other value-keyed) target
            tgt_ref = ind_sdo_by_value.get(tgt_value)
        if src_ref and tgt_ref:
            objs.append(_relationship(src_ref, r["relationship_type"], tgt_ref))

    return incident, objs


def _dedup(objects: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for o in objects:
        if o["id"] in seen:
            continue
        seen.add(o["id"])
        out.append(o)
    return out


def build_issue_bundle(store, issue) -> dict:
    identity = _identity()
    incident, objs = _issue_objects(store, issue)
    refs = [incident["id"]] + [o["id"] for o in objs if o["type"] != "relationship"]
    report = {
        "type": "report", "spec_version": "2.1", "id": _sid("report", issue.id),
        "created": _ts(issue.created_at), "modified": _ts(issue.updated_at),
        "created_by_ref": _GUARDIAN_ID, "name": f"Investigation: {issue.title}",
        "report_types": ["incident"], "published": _ts(issue.updated_at),
        "object_refs": refs,
    }
    objects = _dedup([identity, report, incident] + objs)
    return {"type": "bundle", "id": _sid("bundle", issue.id), "objects": objects}


def build_case_bundle(store, case) -> dict:
    identity = _identity()
    members = store.list_issues(case_id=case.id)
    campaign = {
        "type": "campaign", "spec_version": "2.1", "id": _sid("campaign", case.id),
        "created": _ts(case.created_at), "modified": _ts(case.updated_at),
        "created_by_ref": _GUARDIAN_ID, "name": case.title,
        "description": (case.campaign_summary or case.description or "")[:4000],
    }
    objects: list[dict] = [identity, campaign]

    if case.threat_actor:
        ta = {
            "type": "threat-actor", "spec_version": "2.1",
            "id": _sid("threat-actor", case.threat_actor),
            "created": _ts(case.created_at), "modified": _ts(case.updated_at),
            "created_by_ref": _GUARDIAN_ID, "name": case.threat_actor,
            "threat_actor_types": ["unknown"],
        }
        objects.append(ta)
        objects.append(_relationship(campaign["id"], "attributed-to", ta["id"]))

    for issue in members:
        incident, objs = _issue_objects(store, issue)
        objects.append(incident)
        objects.extend(objs)
        objects.append(_relationship(incident["id"], "related-to", campaign["id"]))

    objects = _dedup(objects)
    grouping = {
        "type": "grouping", "spec_version": "2.1", "id": _sid("grouping", case.id),
        "created": _ts(case.created_at), "modified": _ts(case.updated_at),
        "created_by_ref": _GUARDIAN_ID, "name": f"Campaign: {case.title}",
        "context": "suspicious-activity",
        "object_refs": [o["id"] for o in objects if o["type"] != "relationship"],
    }
    objects.append(grouping)
    return {"type": "bundle", "id": _sid("bundle", f"case:{case.id}"), "objects": _dedup(objects)}
