#!/usr/bin/env python3
"""Batch 5 — more JSON-native vendors via CEF-over-syslog (L12 pattern).

Now using L13-correct dual query: `dataset =` for raw, `datamodel dataset =` for XDM.

VENDORS THIS BATCH
==================
  1. msft_azure_raw            (Microsoft Entra ID — AuditLogs branch; multi-category MR)
  2. aws_security_hub_raw       (Security Hub findings — Severity, Compliance, Resources arrays)
  3. servicenow_servicenow_raw  (ServiceNow — syslog transactions branch; multi-filter MR)
  4. vmware_carbon_black_cloud_raw (Carbon Black Cloud — alert log branch; calculated discriminator)
"""

from __future__ import annotations

import json
import os
import socket
import time
import urllib.request
from datetime import datetime, timezone

BROKER = ("10.10.0.8", 514)
TOKEN = os.environ["MCP_TOKEN"]
MCP = "http://phantom-connector-xsiam-Cortex_XSIAM:9000/mcp"

BATCH = int(time.time())
ts_bsd = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")


# ============================================================
# (1) Microsoft Entra ID — AuditLogs branch
# ============================================================
# PR routing: vendor=msft, product=Azure, target=msft_azure_raw
# PR filter: category not in (many things) AND timestamp parseable
# MR matches: filter category = "AuditLogs"
# MR field reads (top + nested):
#   category, correlationId, callerIpAddress, time, TimeGenerated, tenantId
#   properties.id, properties.category, properties.operationName,
#   properties.tenantGeo, properties.loggedByService, properties.initiatedBy.user.*,
#   properties.targetResources (array), properties.result

ENTRA_MARKER = f"entra-audit-{BATCH}"
entra_initiated_by = json.dumps({"user":{"id":f"00u{BATCH}","userPrincipalName":f"admin-{ENTRA_MARKER}@corp.example.com","displayName":"Admin CEF"}}).replace(" ", "")
entra_target_resources = json.dumps([{"id":"resource-001","displayName":"Test Resource","type":"User","userPrincipalName":"target@corp.example.com"}]).replace(" ", "")
entra_properties = json.dumps({
    "id": ENTRA_MARKER, "category": "UserManagement",
    "operationName": "Add user", "result": "success",
    "tenantGeo": "NA", "loggedByService": "Core Directory",
    "initiatedBy": json.loads(entra_initiated_by),
    "targetResources": json.loads(entra_target_resources),
}, separators=(",", ":"))

entra_ext = {
    "category": "AuditLogs",                                            # PR + MR filter
    "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),  # PR timestamp
    "tenantId": "tenant-abc-123",                                       # MR: xdm.source.cloud.project_id
    "correlationId": f"corr-{BATCH}",                                   # MR: xdm.session_context_id
    "callerIpAddress": "203.0.113.45",                                  # MR: xdm.source.ipv4
    "operationName": "Add user",                                        # MR: xdm.event.operation_sub_type
    "properties": entra_properties,                                     # MR: nested — id, category, initiatedBy.user.upn, etc.
    "resultDescription": "OK",                                          # MR: xdm.event.outcome_reason
    "resultType": "0",
}
entra_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|msft|Azure|1.0|AAD_AUDIT|UserAdd|3|"
    + " ".join(f"{k}={v}" for k, v in entra_ext.items())
)


# ============================================================
# (2) AWS Security Hub
# ============================================================
# PR routing: vendor=aws, product=security_hub (or similar), target=aws_security_hub_raw
# MR field reads:
#   Title, Description, Id, Types, Region, Severity.Label (JSON), Resources (array),
#   AwsAccountId, ProductName, Compliance.Status (JSON)

ASH_MARKER = f"ash-{BATCH}"
ash_severity = json.dumps({"Label":"HIGH","Normalized":75}).replace(" ", "")
ash_resources = json.dumps([{"Id":"arn:aws:s3:::ash-test-bucket-cef","Type":"AwsS3Bucket","Partition":"aws","Region":"us-east-1"}]).replace(" ", "")
ash_compliance = json.dumps({"Status":"FAILED"}).replace(" ", "")

ash_ext = {
    "Title": f"S3.5 Bucket should not allow public read access [{ASH_MARKER}]",   # MR: xdm.alert.name (marker)
    "Description": "S3 bucket has public read ACL granted — finding via CEF smoke", # MR: xdm.alert.description
    "Id": f"arn:aws:securityhub:us-east-1:123456789012:finding/{ASH_MARKER}",       # MR: xdm.alert.original_alert_id
    "Types": "Software and Configuration Checks/Industry and Regulatory Standards/CIS AWS Foundations Benchmark/3.2", # MR: xdm.alert.subcategory
    "Region": "us-east-1",                                                          # MR: xdm.source.zone
    "Severity": ash_severity,                                                       # MR: json_extract Severity.Label → xdm.alert.severity
    "Resources": ash_resources,                                                     # MR: nested array → xdm.target.resource.id
    "AwsAccountId": "123456789012",                                                 # MR: xdm.source.cloud.project
    "ProductName": "Security Hub",                                                  # MR: xdm.observer.product
    "Compliance": ash_compliance,                                                   # MR: xdm.event.outcome (Status enum)
}
ash_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|aws|security_hub|1.0|ASH_FINDING|S3PublicACL|3|"
    + " ".join(f"{k}={v}" for k, v in ash_ext.items())
)


# ============================================================
# (3) ServiceNow — syslog transactions branch
# ============================================================
# PR routing: vendor=servicenow, product=servicenow, target=servicenow_servicenow_raw
# MR matches: filter source_log_type = "syslog transactions"
# MR field reads:
#   source_log_type, sys_id, type, total_wait_time, transaction_processing_time,
#   interaction_id, transaction_number, output_length, db_category, additional_info,
#   sys_created_by, system_id, user_agent, url, session, protocol, gzip, sql_time,
#   db_pool, table, app_scope, origin_scope.value (nested), remote_ip

SNOW_MARKER = f"snow-{BATCH}"
snow_origin_scope = json.dumps({"value":"global","display":"Global"}).replace(" ", "")

snow_ext = {
    "source_log_type": "syslog transactions",                # MR filter requirement
    "sys_id": SNOW_MARKER,                                   # MR: xdm.event.id (marker)
    "type": "REST",                                          # MR: xdm.event.original_event_type
    "total_wait_time": "120",                                # MR: xdm.event.duration component
    "transaction_processing_time": "80",                     # MR: xdm.event.duration component
    "interaction_id": f"ix-{BATCH}",
    "transaction_number": f"tx-{BATCH}",
    "output_length": "1024",
    "db_category": "Standard",
    "sys_created_by": f"admin-{SNOW_MARKER}",                # MR: xdm.source.user.username (marker carrier)
    "system_id": "snow-instance-prod-01",                    # MR: xdm.source.user.identifier
    "user_agent": "ServiceNow REST Client",                  # MR: xdm.source.user_agent
    "url": "/api/now/table/incident?marker=" + SNOW_MARKER,  # MR: xdm.target.url
    "session": f"sess-{BATCH}",                              # MR: xdm.session_context_id
    "protocol": "HTTPS",                                     # MR: xdm.network.application_protocol
    "gzip": "true",                                          # MR: xdm.network.dns.is_truncated
    "sql_time": "5",                                         # MR: xdm.database.response_time (×1000)
    "db_pool": "default",                                    # MR: xdm.database.name
    "table": "incident",                                     # MR: xdm.database.tables
    "app_scope": "Global",                                   # MR: app context
    "origin_scope": snow_origin_scope,                       # MR: nested .value → application_name fallback
    "remote_ip": "10.20.30.40",                              # MR: xdm.source.ipv4
}
snow_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|servicenow|servicenow|1.0|SNOW_TXN|RESTCall|3|"
    + " ".join(f"{k}={v}" for k, v in snow_ext.items())
)


# ============================================================
# (4) Carbon Black Cloud — alert log branch
# ============================================================
# PR routing: vendor=carbonblack, product=defense (or similar), target=vmware_carbon_black_cloud_raw
# MR computes event_type:
#   event_type = if(to_string(flagged) != null, "audit log", to_string(severity) != null, "alert log", null)
# MR filter: filter event_type in("alert log")
# So we need `severity` set (not null) to trigger alert branch.
# MR field reads (alert branch):
#   org_key, alert_url, id, type, severity, reason, threat_id, primary_event_id,
#   device_id, device_name, device_target_value, device_policy, device_policy_id,
#   policy_applied, run_state, sensor_action, device_os, device_os_version,
#   device_username, device_external_ip, device_internal_ip, report_id, report_name,
#   report_description, report_link, process_pid, process_name, process_sha256,
#   process_md5, process_cmdline, process_username, parent_pid, ml_classification_final_verdict

CBC_MARKER = f"cbc-{BATCH}"
cbc_ext = {
    "severity": "7",                                          # required to trigger alert-log branch (also xdm.alert.severity)
    "org_key": "ORG-CEF-001",                                 # MR: xdm.source.cloud.project
    "alert_url": f"https://defense.conferdeploy.net/alert/{CBC_MARKER}",  # MR: xdm.target.url
    "id": CBC_MARKER,                                         # MR: xdm.alert.original_alert_id (marker)
    "type": "CB_ANALYTICS",                                   # MR: xdm.event.type
    "reason": "Suspicious process detected: ransomware indicator",  # MR: xdm.alert.description
    "threat_id": f"threat-{BATCH}",                           # MR: xdm.alert.original_threat_id
    "primary_event_id": f"evt-{BATCH}",                       # MR: xdm.event.id
    "device_id": "5555",                                      # MR: xdm.target.host.device_id
    "device_name": "win10-corp-host-01",                      # MR: xdm.target.host.hostname
    "device_target_value": "MISSION_CRITICAL",                # MR: xdm.alert.risks component
    "device_policy": "Restrictive_Production",                # MR: xdm.target.resource.name
    "device_policy_id": "policy-001",                         # MR: xdm.target.resource.id
    "policy_applied": "APPLIED",                              # MR: xdm.target.resource.value
    "run_state": "RAN",                                       # MR: xdm.event.operation_sub_type
    "sensor_action": "DENY",                                  # MR: drives xdm.event.outcome
    "device_os": "WINDOWS",                                   # MR: xdm.target.host.os_family (enum)
    "device_os_version": "Windows 10 Pro 22H2",               # MR: xdm.target.host.os
    "device_username": "corp\\\\alice",                       # MR: xdm.target.user.username
    "device_external_ip": "203.0.113.55",                     # MR: xdm.target.host.ipv4_addresses (external)
    "device_internal_ip": "10.5.5.55",                        # MR: xdm.target.host.ipv4_addresses (internal)
    "report_id": "watchlist-report-001",                      # MR: xdm.observer.unique_identifier
    "report_name": "Carbon Black Watchlist: Ransomware",      # MR: xdm.observer.name
    "report_description": "Detects ransomware behavior patterns",  # MR: xdm.observer.action
    "report_link": "https://cb.example.com/watchlist/001",    # MR: xdm.observer.product
    "process_pid": "4567",                                    # MR: xdm.source.process.pid
    "process_name": "C:\\\\Users\\\\alice\\\\Downloads\\\\malware.exe",  # MR: xdm.source.process.executable.path
    "process_sha256": "44d88612fea8a8f36de82e1278abb02f8c6f3a0a8c70b1cd62f0d8bf2e1f00ab",
    "process_md5": "9e107d9d372bb6826bd81d3542a419d6",
    "process_cmdline": "malware.exe --c2 evil.example.com",
    "process_username": "corp\\\\alice",                      # MR: xdm.source.user.username
    "parent_pid": "1234",                                     # MR: xdm.source.process.parent_id
    "ml_classification_final_verdict": "MALICIOUS",
}
cbc_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|carbonblack|defense|1.0|CBC_ALERT|RansomwareDetect|3|"
    + " ".join(f"{k}={v}" for k, v in cbc_ext.items())
)


SMOKES = [
    {"name": "MS Entra ID",            "dataset": "msft_azure_raw",                "event": entra_cef, "marker": ENTRA_MARKER, "raw_field": "correlationId",   "xdm_marker_field": "xdm.session_context_id"},
    {"name": "AWS Security Hub",       "dataset": "aws_security_hub_raw",          "event": ash_cef,   "marker": ASH_MARKER,   "raw_field": "Id",              "xdm_marker_field": "xdm.alert.original_alert_id"},
    {"name": "ServiceNow",             "dataset": "servicenow_servicenow_raw",     "event": snow_cef,  "marker": SNOW_MARKER,  "raw_field": "sys_id",          "xdm_marker_field": "xdm.event.id"},
    {"name": "Carbon Black Cloud",     "dataset": "vmware_carbon_black_cloud_raw", "event": cbc_cef,   "marker": CBC_MARKER,   "raw_field": "id",              "xdm_marker_field": "xdm.alert.original_alert_id"},
]


print("=" * 70)
print(f"BATCH 5 — JSON-native vendors via CEF wrapping (4 more)  ({BATCH})")
print("=" * 70)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for s in SMOKES:
    e = s["event"]
    print(f"\n[{s['name']}]  → {BROKER[0]}:{BROKER[1]}  ({len(e)} bytes)")
    print(f"  marker={s['marker']}")
    print(f"  CEF[:180]={e[:180]}{'...' if len(e) > 180 else ''}")
    if len(e) >= 1500:
        print(f"  ⚠ over UDP MTU 1500 — broker may truncate")
    for _ in range(3):
        sock.sendto(e.encode(), BROKER)
sock.close()
print(f"\nAll events sent. Waiting 120s...")
for i in range(4):
    time.sleep(30)
    print(f"  +{(i+1)*30}s")


def post(body, sid=None):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid: h["mcp-session-id"] = sid
    req = urllib.request.Request(MCP, data=json.dumps(body).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read().decode(), r.headers


def sse(s):
    for ln in s.split("\n"):
        if ln.startswith("data:"):
            try:
                f = json.loads(ln[5:].strip())
                if "result" in f:
                    c = f["result"].get("content", [])
                    if c: return json.loads(c[0].get("text", "{}"))
            except: pass
    return {}


_, h = post({"jsonrpc":"2.0","id":1,"method":"initialize",
             "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"b5","version":"1"}}})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post({"jsonrpc":"2.0","method":"notifications/initialized","params":{}}, sid)


def xql(q):
    body, _ = post({"jsonrpc":"2.0","id":99,"method":"tools/call",
                    "params":{"name":"run_xql_query","arguments":{"request":{"query":q, "tenant_timeframe":{"relativeTime":1800000}}}}}, sid)
    return sse(body)


print("\n" + "=" * 70)
print("VERIFICATION (raw landing + XDM materialization via datamodel)")
print("=" * 70)

results = []
for s in SMOKES:
    name, dataset, marker = s["name"], s["dataset"], s["marker"]
    rfield, xfield = s["raw_field"], s["xdm_marker_field"]
    print(f"\n[{name}] dataset={dataset}  marker={marker}")

    # Q1: raw landing via dataset query
    q1 = f'dataset = {dataset} | filter {rfield} contains "{marker}" or _raw_log contains "{marker}" | limit 1'
    r1 = xql(q1)
    reply1 = r1.get("reply", {})
    s1, n1 = reply1.get("status"), reply1.get("number_of_results", 0)
    raw_cols = 0
    if s1 == "SUCCESS" and n1 > 0:
        row = reply1["results"]["data"][0]
        populated = {k:v for k,v in row.items() if v not in (None,"","null")}
        raw_cols = len(populated)
        print(f"  ✅ raw LANDED ({raw_cols} cols)")
    elif s1 == "FAIL":
        print(f"  ✗ dataset doesn't exist (status=FAIL)")
        results.append({"name": name, "result": "DATASET_MISSING", "raw_cols": 0, "xdm_cols": 0})
        continue
    else:
        err = r1.get("_xql_error") or r1.get("error") or "?"
        print(f"  ⚠ raw query: status={s1}  err={str(err)[:200]}")
        if n1 == 0:
            print(f"  (n=0; PR may have rejected event — filter not satisfied?)")

    # Q2: XDM materialization via datamodel query
    q2 = f'datamodel dataset = {dataset} | filter {xfield} contains "{marker}" | limit 1'
    r2 = xql(q2)
    reply2 = r2.get("reply", {})
    s2, n2 = reply2.get("status"), reply2.get("number_of_results", 0)
    xdm_cols = 0
    if s2 == "SUCCESS" and n2 > 0:
        row = reply2["results"]["data"][0]
        populated = {k:v for k,v in row.items() if v not in (None,"","null") and k.startswith("xdm.")}
        xdm_cols = len(populated)
        print(f"  ✅ XDM populated ({xdm_cols} xdm.* fields)")
        for k in sorted(populated)[:10]:
            print(f"    {k:40} = {str(populated[k])[:70]}")
    else:
        print(f"  ⊘ XDM query: status={s2}, n={n2}")

    results.append({"name": name, "result": "LANDED" if raw_cols > 0 else "RAW_GAP", "raw_cols": raw_cols, "xdm_cols": xdm_cols})


print("\n" + "=" * 70)
print("BATCH 5 SUMMARY")
print("=" * 70)
print(f"  {'vendor':<28}  {'result':<16}  raw  xdm")
print(f"  {'-'*28}  {'-'*16}  ---  ---")
for r in results:
    icon = "✅" if r["result"] == "LANDED" and r["xdm_cols"] > 0 else "⚠" if r["result"] == "LANDED" else "✗"
    print(f"  {icon} {r['name']:<26}  {r['result']:<16}  {r.get('raw_cols','?'):>3}  {r.get('xdm_cols','?'):>3}")

landed = sum(1 for r in results if r["result"] == "LANDED")
xdm_fired = sum(1 for r in results if r.get("xdm_cols", 0) > 0)
print(f"\n  {landed}/{len(results)} landed raw, {xdm_fired}/{len(results)} fired MR (xdm.* via datamodel)")
