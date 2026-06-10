#!/usr/bin/env python3
"""v0.17.14 Phase 4d — Salesforce + Netskope + ServiceNow vendor
dictionaries bundled.

# Why

After v0.17.13 (CyberArk), the largest remaining single-vendor gaps:
  Salesforce  71
  Netskope    51
  ServiceNow  40

Each has well-documented schemas; bundling three vendors into one
release reduces CI churn.

# Sources

* Salesforce Real-Time Event Monitoring (EventLogFile event types):
  https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/sforce_api_objects_eventlogfile_eventtype.htm
* Netskope CASB + Network audit log schemas:
  https://docs.netskope.com/
* ServiceNow Transaction Log + ITSM table fields:
  https://docs.servicenow.com/
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


# Vendor → field → description
DICTS: dict[str, dict[str, str]] = {
    "Salesforce": {
        # Standard Salesforce audit fields
        "user_name": "Salesforce username",
        "user_id": "Salesforce user id (15/18-char)",
        "client_ip": "Client IP address",
        "organization_id": "Salesforce org id",
        "request_status": "Request status",
        "run_time": "Operation run time (ms)",
        "session_key": "Session key",
        "timestamp": "Event timestamp (UTC)",
        "uri": "Request URI",
        "user_type": "User type (Standard/PowerUser/Customer/Partner/...)",
        "authentication_method_reference": "Auth method reference (MFA factor used)",
        "event_type": "Event type (EventLogFile category)",
        "login_key": "Login key (login session id)",
        "login_status": "Login status (LOGIN_NO_ERROR / LOGIN_DATA_DOWNLOAD_ONLY / ...)",
        "platform_type": "Client platform type",
        "source_ip": "Source IP",
        "CreatedDate": "Record creation date",
        "TIMESTAMP_DERIVED": "Derived timestamp",
        "Application": "Application name",
        "EventUuid": "Event UUID",
        "UserType": "User type (Standard/PowerUser/Customer/Partner/...)",
        "DeviceSessionId": "Device session id",
        "Status": "Operation status",
        "OperationStatus": "Operation status",
        "EventDate": "Event date",

        # Salesforce EventLogFile "_X_" raw fields (REM standard names)
        "_METHOD_": "HTTP method (REM EventLogFile)",
        "_HTTP_METHOD_": "HTTP method (REM EventLogFile)",
        "_TIME_": "Time taken (ms)",
        "_RUN_TIME_": "Run time (ms)",
        "_TOTAL_MS_": "Total time (ms)",
        "_CLIENT_IP_": "Client IP",
        "_EXEC_TIME_": "Execution time (ms)",
        "_URL_": "Request URL",
        "_NEXT_LINK_": "Next link (pagination URL)",
        "_EXECUTE_MS_": "Execution time (ms)",
        "_FILE_TYPE_": "File type",
        "_MEDIA_TYPE_": "Media type",
        "_SIZE_BYTES_": "Size (bytes)",
        "_DB_CPU_TIME_": "DB CPU time (ms)",
        "_ENTRY_POINT_": "Entry point identifier",
        "_URI_": "Request URI",
        "_STATUS_CODE_": "HTTP status code",
        "_BROWSER_NAME_": "Browser name",
        "_USER_AGENT_": "User agent string",
        "_CALLOUT_TIME_": "Callout time (ms)",
        "_FLOW_LOAD_TIME_": "Flow load time (ms)",
        "_RECORD_ID_": "Salesforce record id",
        "_DEVICE_SESSION_ID_": "Device session id",
        "_PREVPAGE_APP_NAME_": "Previous page app name",
        "_APP_NAME_": "App name",
        "_TARGET_UI_ELEMENT_": "Target UI element",
        "_PAGE_URL_": "Page URL",
        "_DURATION_": "Event duration (ms)",
        "_ACTION_": "Action taken",
        "_ENTITY_": "Entity (object) involved",
        "_ORIGIN_": "Event origin",
        "_SEARCH_QUERY_": "Search query text",
        "_SELECT_": "SOQL/select statement",
        "_OS_NAME_": "OS name",
        "_QUIDDITY_": "Quiddity (execution context type)",
        "_DEVICE_ID_": "Device id",
        "_USER_TYPE_": "User type",
        "_CLIENT_GEO_": "Client geo location",
        "_ENTITY_NAME_": "Entity (object) name",
        "_REQUEST_SIZE_": "Request size (bytes)",
        "_RESPONSE_SIZE_": "Response size (bytes)",
        "_DB_TOTAL_TIME_": "DB total time (ms)",
        "_DEVICE_PLATFORM_": "Device platform",
        "_FILE_PREVIEW_TYPE_": "File preview type",
        "_USER_ID_": "User id",
        "_EVENT_TYPE_": "Event type",
    },

    "Netskope": {
        # Generic event
        "action": "Action taken (allow/block/alert/quarantine)",
        "activity": "Activity name (e.g. Download/Upload/View)",
        "alert": "Alert flag",
        "audit_log_event": "Audit log event name",
        "event_type": "Event type",
        "incident_id": "Incident id",
        "managed_app": "Managed application name",
        "severity_level": "Severity level (Low/Medium/High/Critical)",
        "source_log_event": "Source log event name",
        "title": "Event title",
        "type": "Event type",

        # Network / device
        "device": "Device name",
        "dsthost": "Destination hostname",
        "dstip": "Destination IP",
        "dstport": "Destination port",
        "hostname": "Hostname",
        "ip_protocol": "IP protocol",
        "os": "Operating system",
        "protocol": "Protocol",
        "session_duration": "Session duration (seconds)",
        "srcip": "Source IP",
        "srcport": "Source port",
        "timestamp": "Event timestamp",
        "total_packets": "Total packets",
        "user": "User",
        "userkey": "User key",
        "user_id": "User id",

        # CASB / file
        "ccl": "Cloud Confidence Level (low/medium/high)",
        "ccl": "Cloud Confidence Level (Netskope risk tier)",
        "ur_normalized": "Normalized user (UPN-normalized)",
        "dom": "Domain",
        "site": "Site / cloud app",
        "file_type": "File type",
        "url": "URL accessed",
        "useragent": "User agent",
        "md5": "File MD5 hash",
        "sha256": "File SHA-256 hash",
        "malware_severity": "Malware severity",
        "risk_level": "Risk level",
        "traffic_type": "Traffic type (CloudApp/Web/etc.)",
        "src_location": "Source location (city)",
        "src_country": "Source country",
        "src_region": "Source region",
        "access_method": "Access method (Client/Proxy/Tap)",
    },

    "ServiceNow": {
        # Transaction log fields
        "source_log_type": "Source log type",
        "type": "Transaction type",
        "total_wait_time": "Total wait time (ms)",
        "transaction_processing_time": "Transaction processing time (ms)",
        "interaction_id": "Interaction id",
        "transaction_number": "Transaction number",
        "output_length": "Output length (bytes)",
        "db_category": "Database category",
        "additional_info": "Additional info",
        "additional_debug_info": "Additional debug info",
        "remote_ip": "Remote client IP",
        "system_id": "ServiceNow system id",
        "user_agent": "HTTP user agent",
        "url": "Request URL",
        "session": "Session id",
        "protocol": "Protocol (HTTP/HTTPS)",
        "gzip": "Whether response was gzipped",
        "origin_scope": "Origin scope (application)",
        "db_pool": "Database connection pool",
        "sql_time": "SQL time (ms)",
        "table": "ServiceNow table",
        "app_scope": "Application scope",

        # ITSM (Incident/Problem/Change/Request) common fields
        "state": "Record state (New/In Progress/Resolved/Closed)",
        "impact": "Impact level (1=High, 2=Medium, 3=Low)",
        "urgency": "Urgency level (1=High, 2=Medium, 3=Low)",
        "approval": "Approval state (requested/approved/rejected/...)",
        "category": "Category",
        "made_sla": "Whether SLA was met",
        "priority": "Priority (1=Critical, 2=High, 3=Moderate, 4=Low, 5=Planning)",
        "knowledge": "Whether a knowledge article applies",
        "escalation": "Escalation level (0=Normal, 1=Moderate, 2=High, 3=Overdue)",
        "sys_domain": "ServiceNow domain (multi-tenancy)",
        "case_report": "Case report id",
        "time_worked": "Time worked (seconds)",
        "upon_reject": "Action upon reject (cancel/discard)",
        "sys_mod_count": "Record modification count",
        "upon_approval": "Action upon approval (proceed/wait)",
        "follow_the_sun": "Whether follow-the-sun routing applies",
        "reassignment_count": "Reassignment count",
        "description": "Record description",
    },
}


def main() -> int:
    print("=== v0.17.14 Phase 4d — Salesforce + Netskope + ServiceNow ===\n")
    import yaml
    total_filled = 0
    yamls_modified = 0
    stats_per_vendor: Counter[str] = Counter()

    for ds_dir in sorted(BUNDLE_ROOT.glob("*/")):
        yaml_path = ds_dir / "data_source.yaml"
        if not yaml_path.is_file():
            continue
        d = yaml.safe_load(yaml_path.read_text()) or {}
        vendor = d.get("vendor")
        if vendor not in DICTS:
            continue
        vdict = DICTS[vendor]
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
            desc = vdict.get(name) if name else None
            if desc:
                nf = dict(f)
                nf["description"] = desc
                new_fields.append(nf)
                total_filled += 1
                stats_per_vendor[vendor] += 1
                any_changed = True
            else:
                new_fields.append(f)
        if any_changed:
            ok, msg = update_one_yaml(yaml_path, new_fields)
            if ok:
                yamls_modified += 1

    print(f"  Total filled    : {total_filled}")
    print(f"  YAMLs modified  : {yamls_modified}")
    for v, c in stats_per_vendor.most_common():
        print(f"    {v:20s} {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
