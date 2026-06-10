#!/usr/bin/env python3
"""v0.17.21 Phase 4j — final cleanup. Targets the 143 long-tail fields
across ~60 small packs (1-4 fields each). Closes the arc at ~100%.
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
    "AMP": {"cloud_ioc": "Cloud IoC reference"},
    "AWS-SecurityHub": {
        "Severity": "Finding severity (CRITICAL/HIGH/MEDIUM/LOW/INFORMATIONAL)",
        "Compliance": "Compliance status (PASSED/WARNING/FAILED/NOT_AVAILABLE)",
    },
    "AppSentinelsAi": {
        "type": "Event type",
        "user_info": "User info (JSON)",
    },
    "Armis": {
        "protocol": "Network protocol",
        "time": "Event time",
    },
    "AzureDevOps": {
        "ActorCUID": "Actor cloud user id",
        "Area": "Azure DevOps area / category",
        "IpAddress": "Actor IP address",
        "TimeGenerated": "Log generation time (UTC)",
    },
    "AzureFlowLogs": {
        "transportProtocol": "Transport protocol (TCP/UDP/ICMP)",
        "flowState": "Flow state (B=begin / C=continuing / E=end)",
        "deviceDirection": "Traffic direction (Inbound/Outbound)",
    },
    "BitwardenPasswordManager": {
        "ipAddress": "Client IP address",
    },
    "BloodHoundEnterprise": {
        "source_ip_address": "Source IP",
        "actor_name": "Actor name",
    },
    "Celonis": {
        "event": "Event payload",
        "authenticationEventType": "Authentication event type",
        "userId": "User id",
    },
    "CiscoCatalyst": {
        "parsed_fields": "Parsed CEF fields (JSON)",
        "_final_reporting_device_ip": "Final reporting device IP",
    },
    "CiscoStealthwatch": {
        "fullmessage": "Full event message",
    },
    "CiscoThousandEyes": {
        "aid": "ThousandEyes account id",
        "ipAddress": "IP address",
        "resources": "Affected resources",
    },
    "Darktrace": {
        "triggeredComponents": "Detection components triggered",
    },
    "DeCYFIR": {
        "principal": "Principal (user/entity)",
        "asset_comments": "Asset comments",
        "modified_by": "Last modified by",
    },
    "DigitalGuardian": {
        "dg_comment": "Digital Guardian comment",
        "inc_mtime": "Incident modification time",
        "dg_tenant": "Digital Guardian tenant",
    },
    "ForcepointDLP": {
        "_collector_source": "Phantom collector source",
        "detected_by": "Detected by (policy/rule)",
        "file_name": "File name",
        "timeStamp": "Event timestamp",
    },
    "Forcepoint": {
        "cefVersion": "CEF format version",
    },
    "GenesysCloud": {
        "context": "Event context",
        "remoteIp": "Remote IP",
    },
    "GitLab": {
        "created_at": "Event creation time",
    },
    "GoogleChrome": {
        "events": "Event list (JSON)",
        "event": "Event details",
    },
    "GoogleCloudLogging": {
        "textPayload": "Log message (text payload)",
    },
    "GoogleCloudSCC": {
        "finding": "SCC finding details",
        "resource": "Affected GCP resource",
    },
    "GoogleDrive": {
        "events": "Event list (JSON)",
        "actor": "Actor performing the event",
        "id": "Event id",
    },
    "GuardiCore": {
        "cs14": "Device custom string 14 (see cs14Label)",
        "drpoc": "Disaster-recovery POC",
    },
    "HPEArubaCentral": {
        "bssid": "Access point BSSID",
        "ts": "Event timestamp",
        "timestamp": "Event timestamp",
    },
    "HelloWorld": {
        "created_time": "Event creation time",
    },
    "IBMDirectoryServer": {
        "client": "Client identifier",
    },
    "IBMGuardium": {
        "cefDeviceEventClassId": "CEF device event class id",
    },
    "IBMMaaS360Security": {
        "IP_Address": "Device IP address",
        "Roles_Added": "Roles added",
        "Roles_Deleted": "Roles removed",
    },
    "IBMSecurityVerify": {
        "geoip": "GeoIP location",
        "servicename": "Service name",
    },
    "IBMStorageScale": {
        "user": "User",
        "returnCode": "Return code",
    },
    "IllusiveNetworks": {
        "cefname": "CEF event name",
        "cefDeviceEventClassId": "CEF device event class id",
    },
    "Incapsula": {
        "sip": "Source IP",
        "ver": "Log format version",
    },
    "IronscalesEventCollector": {
        "first_reported_date": "First reported date",
        "reports": "Report count",
    },
    "LenelS2NetBox": {
        "reasoncode": "Reason code",
    },
    "LinuxEventsCollection": {
        "_log_source_file_name": "Source log file name",
    },
    "LookoutMobileEndpointSecurity": {
        "actor": "Actor (user/device)",
    },
    "ManageEngine-ADAudit": {
        "type": "Event type",
    },
    "MicrosoftADFS": {
        "EVENT": "Windows event payload",
        "winlog": "Windows event log metadata",
        "MESSAGE": "Event message",
    },
    "MicrosoftCloudAppSecurity": {
        "stories": "Threat stories",
        "timestamp": "Event timestamp",
    },
    "MicrosoftDNS": {
        "task": "Windows task category",
        "opcode": "Windows opcode",
        "computer_name": "Computer name",
    },
    "MicrosoftECM": {
        "_log_source_file_name": "Source log file name",
    },
    "MicrosoftIISWebServer": {
        "parsed_fields": "Parsed IIS fields (JSON)",
    },
    "MicrosoftIntune": {
        "time": "Event time",
    },
    "MicrosoftWindowsAMSI": {
        "opcode": "Windows opcode",
        "time_created": "Event creation time",
    },
    "Monday": {
        "data": "Event data payload",
        "os_version": "OS version",
    },
    "NetBox": {
        "user": "User",
    },
    "NetmotionVPN": {
        "ecs": "Elastic common schema metadata",
        "event": "Event details",
        "winlog": "Windows event log metadata",
        "message": "Event message",
    },
    "Office365": {
        "ActionId": "Office 365 action id",
    },
    "OnePassword": {
        "session": "Session metadata",
    },
    "Portnox": {
        "description": "Event description",
        "device_ip": "Device IP",
        "group": "Device group",
        "cefVersion": "CEF format version",
    },
    "ProofpointEmailSecurity": {
        "msgParts": "Message parts",
        "filter": "Filter applied",
        "envelope": "SMTP envelope (mail-from/rcpt-to)",
    },
    "ProofpointIsolation": {
        "zone": "Isolation zone",
        "isiFrame": "Isolation frame info",
        "categories": "URL categories",
    },
    "ProofpointThreatResponse": {
        "hosts": "Hosts involved",
    },
    "RadwareCloudDDoSProtectionServices": {
        "averageByteRate": "Average byte rate (bytes/sec)",
        "triggerOrigin": "Trigger origin",
    },
    "ReblazeWAF": {
        "parsed_fields": "Parsed WAF fields (JSON)",
        "parsed_fields_get_headers": "Parsed GET request headers",
    },
    "RetarusSecureEmailGateway": {
        "ts": "Event timestamp",
        "sourceIp": "Source IP",
        "direction": "Mail direction (in/out)",
        "metaData": "Email metadata",
    },
    "RunZero": {
        "source_name": "Source name",
        "source_id": "Source id",
    },
    "SafeNet_Trusted_Access": {
        "id": "Event id",
        "timeStamp": "Event timestamp",
        "context": "Event context",
        "details": "Event details",
    },
    "SaviyntEIC": {
        "IP_Address": "IP address",
        "Message": "Event message",
    },
    "Silverfort": {
        "cs7": "Device custom string 7 (see cs7Label)",
        "cs11": "Device custom string 11 (see cs11Label)",
        "destinationservicename": "Destination service name",
    },
    "Slack": {
        "date_create": "Event creation date",
        "actor": "Actor performing the event",
    },
    "SymantecBlueCoatProxySG": {
        "parsed_fields": "Parsed proxy fields (JSON)",
        "raw_log_cleaned": "Cleaned raw log text",
    },
    "SymantecCloudSOC": {
        "locations": "User locations",
        "browsers": "Browsers used",
        "devices": "Devices used",
        "host": "Host",
    },
    "TrendMicroEmailSecurity": {
        "timestamp": "Event timestamp",
    },
    "UbiquitiUnifi": {
        "UNIFIclientIp": "UniFi client IP",
    },
    "Zoom": {
        "time": "Event time",
    },
    "qualys": {
        "User_IP": "User IP",
    },
}


def main() -> int:
    print("=== v0.17.21 Phase 4j — final cleanup ===\n")
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
    print(f"  Packs covered   : {len(stats)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
