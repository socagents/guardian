#!/usr/bin/env python3
"""v0.17.18 Phase 4g — Microsoft Azure specialty + Abnormal + McAfee +
MongoDB Atlas.

# Targeted packs (per /tmp/phase4g_gap.py inventory)

Microsoft AzureWAF              43
Microsoft AzureAppService       24
Abnormal Security               25
McAfee ePO                      19
Microsoft Exchange Server       16
Microsoft AzureKubernetes       15
MongoDB Atlas                   15

Total: ~157 fields. Pushes coverage 84.7% → ~87.7%.

# Sources

* Azure WAF logs schema:
  https://learn.microsoft.com/en-us/azure/web-application-firewall/afds/waf-front-door-monitor
* Azure App Service logs schema:
  https://learn.microsoft.com/en-us/azure/app-service/troubleshoot-diagnostic-logs
* Microsoft Exchange Server message tracking:
  https://learn.microsoft.com/en-us/exchange/mail-flow/transport-logs/message-tracking
* Azure Kubernetes audit log schema:
  https://learn.microsoft.com/en-us/azure/aks/monitor-aks
* McAfee ePO event schema:
  https://docs.trellix.com/bundle/epolicy-orchestrator-5.10.0-product-guide/page/GUID-3DF26AA1-8BBC-4F89-A4F5-2BB81F7B4E33.html
* MongoDB Atlas audit log schema:
  https://www.mongodb.com/docs/atlas/reference/api-resources-spec/v2/#tag/Auditing
* Abnormal Security XSIAM connector schema (inferred from connector
  metadata + Abnormal's email security taxonomy)
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


# Pack-specific dictionaries (per (pack_name) — more selective than
# vendor-level since Microsoft umbrella covers many distinct packs)
PACK_DICTS: dict[str, dict[str, str]] = {
    "AzureWAF": {
        "type": "Log type (AzureFirewallApplicationRule/NetworkRule/IDPS)",
        "transactionid": "Transaction id",
        "clientip": "Client IP",
        "instanceid": "Azure instance id",
        "requesturi": "Request URI",
        "upstreamsourceport": "Upstream source port",
        "errorinfo": "Error info",
        "rulename": "Matching rule name",
        "serverrouted": "Backend server routed to",
        "originalhost": "Original Host header",
        "host": "Host header",
        "httpmethod": "HTTP method",
        "httpstatus": "HTTP response status",
        "originalrequesturiwithargs": "Original request URI with args",
        "receivedbytes": "Bytes received from client",
        "sentbytes": "Bytes sent to client",
        "sslcipher": "TLS cipher suite",
        "sslprotocol": "TLS protocol version",
        "wafmode": "WAF mode (Prevention/Detection)",
        "message": "Log message",
        "detaileddata": "Detailed data (JSON)",
        "detailedmessage": "Detailed message",
        "filedetails": "File details",
        "ruleid": "Rule id",
        "ruleGroup_s": "Rule group",
        "rulesettype": "Ruleset type (OWASP/Microsoft_DefaultRuleSet)",
        "rulesetversion": "Ruleset version",
        "durationMs": "Request duration (ms)",
        "TimeGenerated": "Log generation time (UTC)",
        "clientIP_s": "Client IP",
        "clientPort_s": "Client port",
        "socketIP_s": "Socket IP",
        "errorInfo_s": "Error info",
        "originIp_s": "Origin IP",
        "domain_s": "Domain",
        "httpStatusDetails_s": "HTTP status detail",
        "httpStatusCode_s": "HTTP status code (string)",
        "httpStatusCode_d": "HTTP status code (numeric)",
        "httpMethod_s": "HTTP method",
        "timeTaken_s": "Time taken",
        "userAgent_s": "User agent",
        "securityProtocol_s": "Security protocol (TLS version)",
        "originCryptProtocol_s": "Origin crypto protocol",
    },

    "AzureAppService": {
        "Level": "Log severity level (Critical/Error/Warning/Info)",
        "_ResourceId": "Azure resource id",
        "Result": "Operation result",
        "CsUsername": "Client/source username",
        "ListOfInfectedFiles": "List of infected files (AV scan)",
        "ScanStatus": "Antivirus scan status",
        "Path": "File or URL path",
        "Process": "Process name",
        "AppName": "App service name",
        "EventName": "Event name",
        "ProcessId": "Process id",
        "HostInstanceId": "Host instance id",
        "Protocol": "Protocol",
        "User": "User",
        "UserAddress": "User IP address",
        "UserDisplayName": "User display name",
        "Code": "Status / error code",
        "ActionName": "Action name",
        "WorkflowId": "Logic App workflow id",
        "WorkflowName": "Logic App workflow name",
        "RunId": "Workflow run id",
        "OriginRunId": "Original workflow run id (parent)",
        "StartTime": "Start time",
        "EndTime": "End time",
    },

    "MicrosoftExchangeServer": {
        "date_time": "Event datetime (UTC)",
        "client_ip": "Client IP",
        "client_hostname": "Client hostname",
        "server_ip": "Exchange server IP",
        "server_hostname": "Exchange server hostname",
        "event_id": "Message tracking event id (RECEIVE/SEND/DELIVER/FAIL/...)",
        "internal_message_id": "Exchange internal message id",
        "message_id": "RFC 822 message id",
        "network_message_id": "Network message id (cross-server correlation)",
        "recipient_address": "Recipient email address",
        "message_subject": "Email subject",
        "sender_address": "Sender email address",
        "return_path": "Return-path / envelope sender",
        "message_info": "Message info (transport status)",
        "tenant_id": "Tenant id (Exchange Online)",
        "schema_version": "Schema version",
    },

    "AzureKubernetesServices": {
        "Type": "Audit event type",
        "Stream": "Container stream (stdout/stderr)",
        "PodName": "Kubernetes pod name",
        "kind": "K8s resource kind (Pod/Deployment/Service/...)",
        "RequestObject": "K8s API request object",
        "ResponseObject": "K8s API response object",
        "AuditId": "K8s audit id",
        "Stage": "Audit stage (RequestReceived/ResponseStarted/ResponseComplete/Panic)",
        "RequestUri": "K8s API request URI",
        "Verb": "K8s API verb (get/list/watch/create/update/patch/delete)",
        "User": "K8s user (subject)",
        "SourceIps": "Source IPs (client)",
        "ObjectRef": "K8s object reference",
        "ResponseStatus": "K8s response status",
        "Annotations": "K8s annotations",
    },

    "AbnormalSecurity": {
        "autoRemediated": "Whether auto-remediation was applied",
        "postRemediated": "Whether post-delivery remediation was applied",
        "fromName": "Sender display name",
        "attackedParty": "Targeted party (recipient or org role)",
        "replyToEmails": "Reply-To addresses",
        "attackVector": "Attack vector (Phishing/BEC/Extortion/etc.)",
        "isRead": "Whether the email was read",
        "recipientAddress": "Recipient email address",
        "sentTime": "Send time",
        "attachmentNames": "Attachment filenames",
        "ccEmails": "CC recipient email addresses",
        "receivedTime": "Received time",
        "summaryInsights": "Abnormal Security threat insights summary",
        "toAddresses": "To recipient email addresses",
        "returnPath": "Return-path / envelope sender",
        "fromAddress": "From email address",
        "senderIpAddress": "Sender IP address",
        "subject": "Email subject",
        "attackType": "Attack type (Credential Phishing/Malware/BEC/...)",
        "attackStrategy": "Attack strategy",
        "abxMessageId": "Abnormal Security message id",
        "threatId,": "Abnormal Security threat id",
        "internetMessageId": "RFC 822 Internet message id",
    },

    "epo": {  # McAfee ePO
        "AnalyzerMAC": "Reporting analyzer MAC address",
        "FileMD5Hash": "File MD5 hash",
        "IPAddress": "IP address",
        "NodeName": "Node (endpoint) name",
        "SourceMAC": "Source MAC address",
        "TargetMAC": "Target MAC address",
        "TargetName": "Target object name",
        "TargetPath": "Target file path",
        "TargetSigner": "Target signer (process signer)",
        "ThreatEventID": "ePO threat event id",
        "ThreatName": "Threat / detection name",
        "ThreatCategory": "Threat category",
        "ThreatSeverity": "Threat severity",
        "ServerID": "ePO server id",
        "AnalyzerVersion": "Analyzer (agent) version",
        "AnalyzerName": "Analyzer (agent) name",
    },

    "MongoDBAtlas": {
        "acknowledgingUsername": "Username acknowledging the alert",
        "id": "Event/alert id",
        "status": "Status",
        "_ENTRY_STATUS": "Entry status",
        "publicKey": "API key public part",
        "remoteAddress": "Remote client IP",
        "targetPublicKey": "Target API key public part",
        "alertId": "Atlas alert id",
        "collection": "MongoDB collection",
        "userAlias": "User alias",
        "clusterName": "Atlas cluster name",
        "whitelistEntry": "IP whitelist entry",
        "applicationId": "Application id",
        "linkToDetails": "Link to alert details",
        "dbUserUsername": "Database user username",
    },
}


def main() -> int:
    print("=== v0.17.18 Phase 4g — Azure specialty + Abnormal + McAfee + MongoDB ===\n")
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
