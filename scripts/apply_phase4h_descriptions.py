#!/usr/bin/env python3
"""v0.17.19 Phase 4h — Duo + Jamf + Atlassian + ExtraHop + Okta + OneLogin.

Targeted packs:
  DuoAdminApi      19
  ExtraHop         17
  JamfProtect      17
  OneLogin         15
  Okta             12
  Atlassian/Jira   10
  Confluence Cloud  8
  Jamf (legacy)     3
  OktaAuth0         2
  OktaASA           1

Total ~104 fields. Pushes 87.8% → ~89.8%.

Sources:
* Duo Admin API event schema: https://duo.com/docs/adminapi
* ExtraHop Reveal(x) detection schema: https://docs.extrahop.com/
* Jamf Protect telemetry: https://learn.jamf.com/jamf-protect/
* Okta system log schema: https://developer.okta.com/docs/reference/api/system-log/
* OneLogin event types: https://developers.onelogin.com/api-docs/2/events/event-resource
* Atlassian audit log schema: https://developer.atlassian.com/cloud/admin/organization/audit-log/
"""

from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from extend_data_source_fields import update_one_yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_ROOT = REPO_ROOT / "bundles" / "spark" / "data-sources"


PACK_DICTS: dict[str, dict[str, str]] = {
    "DuoAdminApi": {
        "host": "Duo host (deployment)",
        "result": "Authentication result (success/failure/fraud)",
        "integration": "Duo integration name",
        "ood_software": "Out-of-date software info",
        "access_device": "Access device info (browser/OS/version)",
        "application": "Application name",
        "eventtype": "Event type",
        "factor": "Auth factor used (push/passcode/sms/phone/...)",
        "isotimestamp": "ISO 8601 timestamp",
        "action": "Admin action taken",
        "description": "Event description",
        "object": "Object affected by the admin action",
        "timestamp": "Unix timestamp",
        "username": "Duo user name",
        "context": "Auth context",
        "phone": "User phone (last 4 digits)",
        "type": "Event type",
    },

    "ExtraHop": {
        "end_time": "Detection end time",
        "mod_time": "Last modification time",
        "start_time": "Detection start time",
        "create_time": "Detection creation time",
        "recommended": "Whether detection is ExtraHop-recommended",
        "update_time": "Last update time",
        "appliance_id": "ExtraHop appliance id",
        "is_user_created": "Whether the detection was user-created",
        "status": "Detection status",
        "assignee": "Assignee (analyst)",
        "ticket_id": "Linked ticket id",
        "properties": "Detection properties (JSON)",
        "resolution": "Detection resolution",
        "participants": "Detection participants (offender/victim)",
        "mitre_tactics": "MITRE ATT&CK tactics",
        "mitre_techniques": "MITRE ATT&CK techniques",
        "recommended_factors": "Recommended risk factors",
    },

    "JamfProtect": {
        "ips": "Device IP addresses",
        "checkin": "Last checkin time",
        "created": "Record creation time",
        "hostName": "Device hostname",
        "memorySize": "Device memory size (bytes)",
        "modelName": "Device model name",
        "osString": "OS string (macOS version)",
        "serial": "Device serial number",
        "uuid": "Device UUID",
        "version": "Jamf Protect agent version",
        "signaturesVersion": "Signature database version",
        "plan": "Jamf Protect plan",
        "insightsStatsFail": "Insights checks failed count",
        "insightsStatsPass": "Insights checks passed count",
        "insightsStatsUnknown": "Insights checks unknown count",
        "scorecard": "Device scorecard",
        "lastConnectionIp": "Last connection IP",
    },

    "OneLogin": {
        "user_id": "OneLogin user id",
        "ipaddr": "Client IP address",
        "id": "Event id",
        "notes": "Event notes",
        "event_type_name": "Event type name",
        "created_at": "Event creation time",
        "user_name": "OneLogin username",
        "risk_score": "Event risk score",
        "risk_reasons": "Risk reasons",
        "app_name": "Application name",
        "actor_user_id": "Actor user id (who performed the action)",
        "otp_device_name": "OTP device name",
        "otp_device_id": "OTP device id",
    },

    "Okta": {
        "target": "Event target (user/group/app affected)",
        "debugContext": "Debug context (debugData info)",
        "severity": "Event severity (INFO/WARN/ERROR)",
        "displayMessage": "Display message (human-readable)",
        "transaction": "Transaction id (correlation)",
        "legacyEventType": "Legacy event type",
        "published": "Event publication time (UTC)",
        "client": "Client info (user agent/IP/geo)",
        "eventType": "Event type (e.g. user.session.start)",
        "authenticationContext": "Authentication context (method/credential type)",
    },

    "Jira": {
        "created": "Audit record creation time",
        "changedValues": "Values changed (before/after)",
        "summary": "Audit record summary",
        "remoteAddress": "Remote client IP",
        "authorKey": "Author user key",
        "authorAccountId": "Author Atlassian account id",
        "category": "Audit category",
        "objectItem": "Object being audited",
    },

    "AtlassianConfluenceCloud": {
        "changedvalues": "Values changed (before/after)",
        "associatedobjects": "Associated objects",
        "affectedobject": "Object affected by the action",
        "sysadmin": "Whether the actor is a sysadmin",
        "superadmin": "Whether the actor is a superadmin",
        "parsed_fields_changed_values_old": "Parsed old value",
        "parsed_fields_changed_values_new": "Parsed new value",
        "description": "Audit description",
    },

    "jamf": {  # Jamf Pro (legacy package)
        "event": "Jamf Pro event payload",
        "webhook": "Webhook info",
    },

    "OktaAuth0": {
        "ip": "Client IP",
        "user_agent": "User agent",
    },

    "OktaASA": {
        "group": "Okta ASA group",
    },
}


def main() -> int:
    print("=== v0.17.19 Phase 4h — Duo + Jamf + Atlassian + ExtraHop + Okta + OneLogin ===\n")
    import yaml
    total_filled = 0
    yamls_modified = 0
    stats: Counter[str] = Counter()

    for ds_dir in sorted(BUNDLE_ROOT.glob("*/")):
        yaml_path = ds_dir / "data_source.yaml"
        if not yaml_path.is_file():
            continue
        d = yaml.safe_load(yaml_path.read_text()) or {}
        pack = d.get("pack_name")
        if pack not in PACK_DICTS:
            continue
        pdict = PACK_DICTS[pack]
        fields = d.get("fields") or []
        any_changed = False
        new_fields: list[dict[str, Any]] = []
        for f in fields:
            if not isinstance(f, dict):
                new_fields.append(f)
                continue
            if (f.get("description") or "").strip():
                new_fields.append(f)
                continue
            name = f.get("name")
            desc = pdict.get(name) if name else None
            if desc:
                nf = dict(f)
                nf["description"] = desc
                new_fields.append(nf)
                total_filled += 1
                stats[pack] += 1
                any_changed = True
            else:
                new_fields.append(f)
        if any_changed:
            ok, msg = update_one_yaml(yaml_path, new_fields)
            if ok:
                yamls_modified += 1

    print(f"  Total filled    : {total_filled}")
    print(f"  YAMLs modified  : {yamls_modified}")
    for p, c in stats.most_common():
        print(f"    {p:35s} {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
