#!/usr/bin/env python3
"""v0.17.20 Phase 4i — long-tail vendor coverage (packs with >=5 gap).

Closing in on full coverage. After v0.17.19 (89.9%), the remaining
515 fields cluster across ~100 packs with 1-21 fields each. This
phase tackles every pack with >=5 missing fields — ~30 packs,
~350 fields. Pushes coverage to ~96%.

Sources are vendor docs (linked in CHANGELOG) + the original
modeling-rule context already fetched in v0.17.8.
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
    "Absolute": {
        "actorDisplayId": "Actor display id",
        "actorDisplayName": "Actor display name",
        "secondaryObjectType": "Secondary object type",
        "secondaryObjectDisplayName": "Secondary object display name",
        "secondaryObjectDisplayId": "Secondary object display id",
        "objectProperties": "Object properties (JSON)",
    },

    "AdminByRequest": {
        "auditLogURL": "URL to the audit log entry",
        "eventLevel": "Event severity level",
        "additionalData": "Additional context (JSON)",
        "userName": "User name",
        "auditlogLink": "Link to audit log entry",
        "approvedBy": "Admin who approved the request",
        "approvedByEmail": "Approver email",
        "deniedBy": "Admin who denied the request",
        "deniedByEmail": "Denier email",
        "deniedReason": "Reason the request was denied",
    },

    "AlibabaActionTrail": {
        "__time__": "Log ingestion time",
        "event_acsregion": "Alibaba Cloud region",
        "event_eventid": "ActionTrail event id",
        "event_eventname": "ActionTrail event name",
        "event_eventtype": "ActionTrail event type (ConsoleOperation/ApiCall/...)",
        "event_resourcename": "Resource name affected",
        "event_resourcetype": "Resource type affected",
        "event_sourceipaddress": "Source IP of the request",
        "event_useridentity_type": "User identity type (root/RAM/service)",
        "event_useridentity_principalid": "Principal id (RAM user/role)",
        "event_useridentity_username": "User name",
    },

    "Armis": {
        "accessSwitch": "Switch the device is connected to",
        "boundaries": "Network boundaries / segments",
        "category": "Device category",
        "ipAddress": "Device IP address",
        "macAddress": "Device MAC address",
        "names": "Device hostnames",
        "operatingSystemVersion": "OS version",
        "riskLevel": "Armis risk level (High/Medium/Low)",
    },

    "AzureSecurityCenter": {
        "_collector_type": "Phantom collector type",
        "AlertSeverity": "Defender for Cloud alert severity",
        "DestinationDeviceAddress": "Destination device IP",
        "AlertName": "Alert name",
        "SourceDeviceAddress": "Source device IP",
        "TimeGenerated": "Log generation time (UTC)",
    },

    "BitSight": {
        "assets": "Affected assets (JSON list)",
        "pcap_id": "Packet capture id (forensic evidence)",
        "severity_category": "Severity category (minor/moderate/material/severe)",
        "last_seen": "Last observation time",
        "first_seen": "First observation time",
        "_alert_data": "Alert data (JSON)",
        "risk_vector": "BitSight risk vector (Spam/Botnet/Patching/...)",
        "evidence_key": "Evidence key (forensic ref)",
        "affects_rating": "Whether the finding affects the BitSight rating",
        "asset_overrides": "Asset overrides applied",
        "remediation_history": "Remediation history (JSON list)",
        "attributed_companies": "Attributed companies (subsidiaries)",
        "rolledup_observation_id": "Rolled-up observation id",
        "impacts_risk_vector_details": "Risk vector impact details",
    },

    "Box": {
        "source": "Event source",
        "additional_details": "Additional event details (JSON)",
        "created_by": "User who created the event",
        "event_id": "Box event id",
        "event_type": "Box event type",
        "ip_address": "Source IP",
        "created_at": "Event creation time",
    },

    "CheckpointFirewall": {
        # Residual fields not covered by CEF standard
        "loguid": "Check Point log uid",
        "cefDeviceEventClassId": "CEF device event class id",
        "session_id_": "Check Point session id",
        "duration": "Connection duration (seconds)",
        "dns_type": "DNS query type (A/AAAA/MX/...)",
        "dns_query": "DNS query name",
        "inzone": "Source zone",
        "outzone": "Destination zone",
        "auth_status": "Authentication status",
        "action_reason": "Action reason",
        "session_id": "Check Point session id",
        "cp_severity": "Check Point severity",
    },

    "Code42": {
        "actorIpAddress": "Actor IP address",
        "destination": "Destination of the file/event",
        "event": "Event details (JSON)",
        "file": "File details (name/path/hash/size)",
        "process": "Process details",
        "responseControls": "Response controls triggered",
        "risk": "Risk score / risk indicators",
        "source": "Source of the file/event",
        "type_": "Event type",
        "user": "User",
    },

    "CohesityHelios": {
        "action": "Action taken",
        "entityName": "Entity name (cluster/protected job)",
        "alertTypeBucket": "Alert type bucket (security/availability/performance)",
        "alertState": "Alert state (open/suppressed/resolved)",
        "alertCategory": "Alert category",
        "severity": "Alert severity",
        "alertDocument": "Alert document (JSON)",
        "newRecord": "Whether this is a new record",
        "alertName": "Alert name",
        "alertCode": "Alert code",
        "clusterName": "Cohesity cluster name",
        "alertId": "Alert id",
    },

    "CommvaultBackupSolutions": {
        "alert_name": "Commvault alert name",
        "commcellname": "CommCell name",
        "client": "Backup client name",
        "details": "Alert details",
        "detected_criteria": "Detection criteria",
        "type": "Alert type",
        "opid": "Operation id",
    },

    "CorelightZeek": {
        "id": "Connection id (UID)",
        "_path": "Zeek log file path (conn/dns/http/...)",
        "status_code": "Protocol-specific status code",
        "_system_name": "Zeek sensor system name",
        "cipher": "TLS cipher suite",
        "ts": "Event timestamp",
    },

    "CybelAngel": {
        "ip": "Affected IP",
        "liveness": "Whether the asset is live",
        "risks": "Risks detected",
        "severity": "Threat severity",
        "hostnames": "Hostnames",
        "tags": "Tags",
        "asset_urls": "Asset URLs",
        "status": "Threat status",
        "registrant_name": "Domain registrant name",
        "registrant_organisation": "Domain registrant organisation",
        "mx": "MX records",
        "ns": "NS records",
        "ip_address": "IP address",
    },

    "CyberArkEPM": {
        "PermissionDescription": "Permission description",
        "accessAction": "Access action (grant/deny/elevate)",
        "winEventType": "Windows event type",
        "packageName": "Package name (software)",
        "runAsUsername": "Run-as username (elevated)",
        "sourceProcessUsername": "Source process username",
        "bundleName": "macOS bundle name",
        "bundleVersion": "macOS bundle version",
        "processCommandLine": "Process command line",
        "sourceWSName": "Source workstation name",
    },

    "CyberArkPAS": {
        "command": "Command executed",
        "sessionId": "Session id",
        "customData": "Custom data (JSON)",
        "cloudProvider": "Cloud provider",
        "cloudWorkspacesAndRoles": "Cloud workspaces and roles",
        "cloudIdentities": "Cloud identities",
        "cloudAssets": "Cloud assets",
        "safe": "PAS safe name",
        "accountName": "Privileged account name",
        "targetPlatform": "Target platform",
        "targetAccount": "Target account",
        "correlationId": "Correlation id",
        "isDr": "Whether this is a disaster-recovery operation",
        "originRegion": "Origin region",
    },

    "DigitalShadows": {
        "_ENTRY_STATUS": "Entry status",
        "alert": "Alert details",
        "incident": "Incident details",
        "triage_item": "Triage item",
        "triage_item_id": "Triage item id",
        "mitre_tactics": "MITRE ATT&CK tactics",
        "mitre_techniques": "MITRE ATT&CK techniques",
        "classification": "Threat classification",
    },

    "Docusign": {
        "action": "Action taken",
        "groupList": "Group list",
        "isAdmin": "Whether the user is an admin",
        "isNAREnabled": "Whether non-admin reporting is enabled",
        "result": "Action result",
        "source_log_type": "Source log type",
        "uri": "Request URI",
    },

    "Dragos_Platform": {
        "src_asset_ip": "Source asset IP",
        "asset_ip": "Asset IP",
        "src_asset_mac": "Source asset MAC",
        "asset_mac": "Asset MAC",
        "src_asset_id": "Source asset id",
        "asset_id": "Asset id",
        "asset_hostname": "Asset hostname",
    },

    "Dropbox": {
        "actor": "Actor performing the action",
        "assets": "Assets affected",
        "context": "Event context",
        "details": "Event details",
        "event_category": "Event category",
        "event_type": "Event type",
        "origin": "Event origin (geo/IP/device)",
        "timestamp": "Event timestamp",
    },

    "Druva": {
        "timeStamp": "Event timestamp",
        "initiator": "Event initiator (user/system)",
        "inSyncDataSourceID": "InSync data source id",
        "inSyncUserName": "InSync username",
        "severity": "Event severity",
    },

    "Exabeam": {
        "priority": "Notable session priority",
        "useCases": "Use cases triggered",
        "rules": "Rules triggered",
        "mitres": "MITRE ATT&CK mappings",
        "srcIp": "Source IP",
        "srcHost": "Source hostname",
        "user": "User",
        "destIp": "Destination IP",
        "destHost": "Destination hostname",
    },

    "FireEyeETP": {
        "id": "ETP event id",
        "_ENTRY_STATUS": "Entry status",
        "included": "Included related resources",
        "event_id": "Event id",
        "_TIME": "Event time",
    },

    "ForcepointEmailSecurity": {
        "trueSrc": "True source IP (post-NAT)",
        "fnameAndfileHash": "File name + hash composite",
        "cefDeviceEventClassId": "CEF device event class id",
        "localSpamScore": "Local spam score",
        "from": "From email address",
        "to": "To email address",
        "deliveryCode": "Delivery code",
    },

    "FortinetFortiwebVM": {
        "original_src": "Original source IP (pre-NAT)",
        "http_retcode": "HTTP response code",
        "http_method": "HTTP method",
        "http_response_bytes": "HTTP response bytes",
        "http_request_bytes": "HTTP request bytes",
        "log_timestamp": "Log timestamp",
    },

    "GenetecSecurityCenter": {
        "AuditTrailModificationType": "Audit trail modification type",
        "SourceApplicationAsString": "Source application name",
        "SourceApplicationType": "Source application type",
        "Type": "Event type",
        "Value": "Event value / payload",
    },

    "GitGuardian": {
        "tags": "Incident tags",
        "who": "Who triggered / resolved",
        "status": "Incident status",
        "assignee": "Assignee",
        "repo_name": "Repository name",
        "commit_sha": "Commit SHA",
        "api_url": "GitGuardian API URL",
    },

    "GitHub": {
        "actor_location": "Actor location (geo)",
        "org": "GitHub organisation",
        "repo": "Repository (owner/name)",
        "created_at": "Event creation time",
        "actor": "GitHub actor (user) performing the action",
        "action": "Action taken",
    },

    "GitLab": {
        "id": "Event id",
        "author_id": "Author user id",
        "entity_id": "Entity id (project/group/user)",
        "entity_type": "Entity type",
        "details": "Event details (JSON)",
    },

    "IBMGuardium": {
        "Activity": "Database activity",
        "Action_taken": "Action taken (allow/block/quarantine)",
        "Performed_by": "User who performed the activity",
        "Context_description": "Context description",
        "DB_user": "Database user",
    },

    "KeeperSecurity": {
        "to_username": "To username",
        "recipient": "Recipient",
        "node": "Node name",
        "role_id": "Role id",
        "team_uid": "Team uid",
        "shared_folder_uid": "Shared folder uid",
        "plan": "Account plan",
        "gateway_uid": "Gateway uid",
        "secret_uid": "Secret uid",
        "report_name": "Report name",
        "name": "Object name",
    },

    "KnowBe4_KMSAT": {
        "id": "Event id",
        "risk": "Risk score",
        "occurred_date": "When the event occurred",
        "user": "User involved",
        "external_id": "External id",
        "event_type": "Event type",
        "account_id": "KnowBe4 account id",
        "description": "Event description",
        "source": "Event source",
    },

    "ManageEngine": {
        "hostName": "Host name",
        "eventId": "Event id",
        "module": "ManageEngine module",
        "priority": "Event priority",
        "application": "Application",
        "computerName": "Computer name",
        "domainName": "Domain name",
        "viewerIP": "Viewer IP",
        "userIP": "User IP",
        "userName": "User name",
        "remarks": "Remarks",
    },

    "MicrosoftADFS": {
        "time_created": "Event creation time",
        "_collector_type": "Phantom collector type",
        "event_data": "Event data (JSON)",
        "opcode": "Windows opcode",
        "channel": "Windows event channel",
        "computer_name": "Computer name",
        "event_action": "Event action",
    },

    "MicrosoftEntraID": {
        "Type": "Log type (SigninLogs / AuditLogs / ...)",
        "activitystatusvalue": "Activity status value",
        "activitysubstatusvalue": "Activity sub-status value",
        "HTTPRequest": "HTTP request details",
        "Level": "Log level",
        "operationnamevalue": "Operation name value",
        "ruleName": "Conditional access rule name",
        "time": "Event time",
    },

    "MicrosoftGraphSecurity": {
        "_reporting_device_name": "Reporting device name",
        "providerAlertId": "Provider alert id",
        "incidentWebUrl": "Incident web URL",
        "evidence": "Alert evidence",
        "classification": "Alert classification",
        "createdDateTime": "Alert creation datetime",
    },

    "NVIDIA_DOCA_Argus": {
        "vendor_name": "Vendor name",
        "product_name": "Product name",
        "product_version": "Product version",
        "occurred_message_time_iso_8601_ns": "Event time (ISO-8601 with nanoseconds)",
        "bluefield_network_interface_name": "BlueField network interface name",
        "bluefield_network_interface_mac_address": "BlueField network interface MAC",
        "bluefield_network_interface_ipv4_address": "BlueField network interface IPv4",
        "bluefield_network_interface_ipv6_address": "BlueField network interface IPv6",
        "unique_identifier": "Unique event identifier",
        "os_version": "OS version",
        "workload_network_interface_name": "Workload network interface name",
        "workload_network_interface_mac_address": "Workload network interface MAC",
        "workload_network_interface_ipv4_address": "Workload network interface IPv4",
        "name": "Event name",
        "process_details": "Process details (JSON)",
        "network_connection_details": "Network connection details (JSON)",
        "workload_information": "Workload information (JSON)",
        "bluefield_system_information": "BlueField system information (JSON)",
    },

    "ProofpointThreatResponse": {
        "id": "TRAP incident id",
        "updated_at": "Last update time",
        "users": "Users involved in the incident",
        "event": "Event payload (JSON)",
        "incident_field_values": "Incident custom field values",
    },

    "RecordedFuture": {
        "id": "Recorded Future entity id",
        "hits": "Hits / matches count",
        "url": "URL associated",
        "rule": "Rule that matched",
        "type": "Entity type",
        "title": "Alert title",
        "ai_insights": "AI-generated insights",
    },

    "SailPointIdentityNow": {
        "created": "Event creation time",
        "objects": "Objects affected",
        "ipaddress": "Client IP",
        "actor": "Actor (user)",
        "target": "Target (object affected)",
    },

    "Shodan": {
        "expiration": "Subscription expiration",
        "size": "Account size / limit",
        "created": "Account/object creation time",
        "expires": "Expiration time",
        "triggers": "Configured triggers",
        "notifiers": "Configured notifiers",
        "has_triggers": "Whether triggers are configured",
    },

    "SymantecEndpointSecurity": {
        "user": "User affected",
        "message": "Event message",
        "scan_name": "Scan name",
        "count": "Detection count",
        "attacks": "Attack details (JSON)",
    },

    "WithSecure": {
        "severity": "Severity",
        "engine": "Detection engine",
        "id": "Event id",
        "action": "Action taken",
        "source": "Event source",
    },

    "ZeroNetworksSegment": {
        "callerIpAddress": "Caller IP",
        "userRole": "User role",
        "auditType": "Audit type",
        "enforcementSource": "Enforcement source",
        "destinationEntitiesList": "Destination entities involved",
        "protocol": "Protocol",
        "state": "Connection state",
        "inboundRuleMatches": "Inbound rule matches",
        "outboundRuleMatches": "Outbound rule matches",
    },

    "qualys": {
        "IP": "Asset IPv4 address",
        "IPV6": "Asset IPv6 address",
        "OS_CPE": "Asset OS (CPE format)",
        "METADATA": "Asset metadata (JSON)",
        "CLOUD_PROVIDER_TAGS": "Cloud provider tags",
        "CLOUD_RESOURCE_ID": "Cloud resource id",
    },
}


def main() -> int:
    print("=== v0.17.20 Phase 4i — long-tail vendor coverage (~30 packs) ===\n")
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
    for p, c in stats.most_common(20):
        print(f"    {p:35s} {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
