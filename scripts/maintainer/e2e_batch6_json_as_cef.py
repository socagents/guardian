#!/usr/bin/env python3
"""Batch 6 — 4 more JSON-native vendors via CEF wrapping.

VENDORS THIS BATCH
==================
  1. msft_azure_ad_audit_raw   (Azure AD Audit — retry of Entra via correct sub-dataset)
  2. aws_waf_raw                (AWS WAF — nested httpRequest with headers array)
  3. cyberark_isp_raw           (CyberArk Identity ISP — auth + customData JSON)
  4. msft_o365_general_raw      (Office 365 — RecordType-based MR)
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
# (1) Azure AD Audit — msft_azure_ad_audit_raw
# ============================================================
# PR: filter activityDateTime ~= ".*\d{2}:\d{2}:\d{2}.*"
# MR: alter parsed_fields = regexcapture from additionalDetails;
#     reads id, result, category, initiatedBy (JSON), targetResources (array),
#     activityDisplayName, loggedByService, operationType, parsed_fields.*
AAD_MARKER = f"aad-audit-{BATCH}"
aad_initiated_by = json.dumps({
    "user": {"id": f"00u{BATCH}", "displayName": "AdminCEF",
             "userPrincipalName": f"admin-{AAD_MARKER}@corp.example.com",
             "ipAddress": "203.0.113.45", "homeTenantId": "tenant-001",
             "homeTenantName": "corp-tenant"},
    "app": None,
}).replace(" ", "")
aad_target_resources = json.dumps([
    {"id": "user-target-001", "displayName": "Target User",
     "type": "User", "userPrincipalName": "target@corp.example.com"}
]).replace(" ", "")
aad_additional_details = json.dumps([
    {"key": "UserAgent", "value": "Mozilla/5.0 CEF smoke"},
    {"key": "UserType", "value": "Member"},
    {"key": "TargetTenant", "value": "corp-tenant"},
    {"key": "DeviceId", "value": "device-001"},
]).replace(" ", "")
aad_ext = {
    "activityDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    "id": AAD_MARKER,                                        # MR: xdm.event.id
    "result": "success",                                     # MR: xdm.event.outcome
    "category": "UserManagement",                            # MR: xdm.event.original_event_type
    "activityDisplayName": "Add user",                       # MR: xdm.event.operation_sub_type
    "loggedByService": "Core Directory",                     # MR: xdm.observer.type
    "operationType": "Add",                                  # MR: xdm.observer.action
    "correlationId": f"corr-{BATCH}",                        # MR: xdm.session_context_id
    "resultReason": "OK",                                    # MR: xdm.event.outcome_reason
    "initiatedBy": aad_initiated_by,                         # MR: nested JSON
    "targetResources": aad_target_resources,                 # MR: nested array
    "additionalDetails": aad_additional_details,             # MR: parsed via regexcapture
}
aad_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|msft|Azure AD Audit|1.0|AAD_AUDIT_OP|UserAdd|3|"
    + " ".join(f"{k}={v}" for k, v in aad_ext.items())
)


# ============================================================
# (2) AWS WAF — aws_waf_raw
# ============================================================
# PR: filter to_string(timestamp) ~= "\d{10}|\d{13}|\d{16}|\d{19}"
# MR: alter headers = json_extract(httpRequest, "$.headers") → []
#     reads action, httpRequest (JSON: clientIp, country, headers, httpMethod, uri, requestId),
#           terminatingruleid, httpsourceid, httpsourcename
WAF_MARKER = f"waf-{BATCH}"
waf_http_request = json.dumps({
    "clientIp": "198.51.100.42",
    "country": "US",
    "headers": [
        {"name": "Host", "value": "api.corp.example.com"},
        {"name": "User-Agent", "value": "Mozilla/5.0 CEF waf smoke"},
        {"name": "Referer", "value": "https://corp.example.com/page"},
    ],
    "httpMethod": "POST",
    "uri": f"/api/v1/login?marker={WAF_MARKER}",
    "requestId": f"req-{BATCH}",
}).replace(" ", "")
waf_ext = {
    "timestamp": str(BATCH * 1000),                          # PR: 13-digit epoch ms
    "action": "BLOCK",                                       # MR: xdm.observer.action
    "httpRequest": waf_http_request,                         # MR: nested — clientIp, country, headers, method, uri
    "terminatingruleid": f"rule-{WAF_MARKER}",               # MR: xdm.network.rule (marker)
    "httpsourceid": "arn:aws:apigateway:us-east-1::/restapis/abc123",  # MR: xdm.target.resource.id
    "httpsourcename": "corp-prod-api",                       # MR: xdm.target.resource.name
}
waf_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|aws|waf|1.0|WAF_BLOCK|BlockedRequest|3|"
    + " ".join(f"{k}={v}" for k, v in waf_ext.items())
)


# ============================================================
# (3) CyberArk Identity ISP — cyberark_isp_raw
# ============================================================
# PR + MR check: filter classification by message ("Cloud.Core.Login...") OR auditCode
# MR fields (Auth Mapping branch):
#   uuid, action, message, source, username, userId, identityType, tenantId,
#   customData (JSON with client_ip_address, success, factors, mechanism,
#               authentication_method, roles, mobile_device, internal_session_id,
#               session_guid, browser_name, entity_name, geoip_country_name, etc.)
CARK_MARKER = f"cyberark-isp-{BATCH}"
cark_custom_data = json.dumps({
    "client_ip_address": "203.0.113.55",
    "success": "True",                                       # PR success → SUCCESS outcome
    "factors": "password,mfa-push",
    "mechanism": "OTP",
    "authentication_method": "Federation",
    "roles": "User,SysAdmin",
    "mobile_device": "False",
    "internal_session_id": f"sess-{BATCH}",
    "session_guid": f"guid-{BATCH}",
    "browser_name": "Chrome",
    "entity_name": "Salesforce App",
    "device_os": "macOS",
    "user_agent": "Mozilla/5.0 CEF cyberark",
    "geoip_country_name": "United States",
    "geoip_city_name": "San Francisco",
    "geoip_latitude": "37.7",
    "geoip_longitude": "-122.4",
}).replace(" ", "")
cark_ext = {
    "uuid": CARK_MARKER,                                     # MR: xdm.event.id (marker)
    "message": "Cloud.Core.Login",                           # PR filter: in known auth messages
    "action": "User login successful via SAML federation",   # MR: xdm.event.description
    "source": "203.0.113.55",                                # MR: xdm.source.ipv4 fallback
    "username": f"alice-{CARK_MARKER}@corp.example.com",     # MR: xdm.source.user.upn (also marker)
    "userId": "user-12345",                                  # MR: xdm.source.user.identifier
    "identityType": "HUMAN",                                 # MR: drives user_type enum
    "tenantId": "tenant-001",                                # MR: xdm.source.cloud.project_id
    "customData": cark_custom_data,                          # MR: nested JSON
}
cark_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|cyberark|isp|1.0|CARK_LOGIN|LoginSuccess|3|"
    + " ".join(f"{k}={v}" for k, v in cark_ext.items())
)


# ============================================================
# (4) Office 365 General — msft_o365_general_raw
# ============================================================
# PR: 3 timestamp rules (UTC string, T_Z, T_noZ)
# MR: reads CreationTime, RecordType, OrganizationId, Operation, ObjectId, UserId, UserType,
#     ClientIP, AppAccessContext, ResultStatus, ModifiedProperties, ItemId, Severity, etc.
O365_MARKER = f"o365-{BATCH}"
o365_app_access_context = json.dumps({"CorrelationId": f"corr-{BATCH}", "ClientAppName": "Office Web App"}).replace(" ", "")
o365_modified_properties = json.dumps([
    {"Name": "SignInState", "NewValue": "Disabled", "OldValue": "Enabled"},
]).replace(" ", "")
o365_ext = {
    "CreationTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),  # PR T_noZ rule
    "Id": O365_MARKER,                                       # MR: xdm.event.id (marker)
    "Operation": "Set-Mailbox",                              # MR: xdm.event.operation_sub_type
    "OrganizationId": "org-tenant-001",                      # MR: xdm.source.cloud.project_id
    "RecordType": "1",                                       # MR: xdm.event.type (translates "1" → "ExchangeAdmin")
    "UserKey": f"alice-{O365_MARKER}",                       # MR: xdm.source.user.identifier (marker)
    "UserType": "2",                                         # MR: drives user_type + privilege_level
    "UserId": f"alice-{O365_MARKER}@corp.example.com",       # MR: xdm.source.user.upn
    "ClientIP": "203.0.113.99",                              # MR: xdm.source.ipv4
    "ClientApp": "OWA",                                      # MR: xdm.source.application.name
    "ObjectId": "<exchange-mailbox-001>",                    # MR: xdm.target.resource.name
    "ItemType": "Mailbox",                                   # MR: xdm.target.resource.type
    "ResultStatus": "Succeeded",                             # MR: xdm.event.outcome
    "AppAccessContext": o365_app_access_context,             # MR: nested JSON
    "ModifiedProperties": o365_modified_properties,          # MR: nested array
    "Workload": "Exchange",                                  # MR: xdm.observer.type
    "Severity": "Low",                                       # MR: xdm.alert.severity
}
o365_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|msft|O365 General|1.0|O365_ADMIN|SetMailbox|3|"
    + " ".join(f"{k}={v}" for k, v in o365_ext.items())
)


SMOKES = [
    {"name": "Azure AD Audit",        "dataset": "msft_azure_ad_audit_raw", "event": aad_cef,  "marker": AAD_MARKER,  "raw_field": "id",                "xdm_field": "xdm.event.id"},
    {"name": "AWS WAF",               "dataset": "aws_waf_raw",             "event": waf_cef,  "marker": WAF_MARKER,  "raw_field": "terminatingruleid", "xdm_field": "xdm.network.rule"},
    {"name": "CyberArk ISP",          "dataset": "cyberark_isp_raw",        "event": cark_cef, "marker": CARK_MARKER, "raw_field": "uuid",              "xdm_field": "xdm.event.id"},
    {"name": "Office 365 General",    "dataset": "msft_o365_general_raw",   "event": o365_cef, "marker": O365_MARKER, "raw_field": "Id",                "xdm_field": "xdm.event.id"},
]


print("=" * 70)
print(f"BATCH 6 — 4 more JSON-native vendors via CEF wrapping  ({BATCH})")
print("=" * 70)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for s in SMOKES:
    e = s["event"]
    print(f"\n[{s['name']}]  → {BROKER[0]}:{BROKER[1]}  ({len(e)} bytes)")
    print(f"  marker={s['marker']}")
    print(f"  CEF[:180]={e[:180]}{'...' if len(e) > 180 else ''}")
    if len(e) >= 1500:
        print(f"  ⚠ OVER UDP MTU 1500 — broker may truncate the event!")
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
             "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"b6","version":"1"}}})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post({"jsonrpc":"2.0","method":"notifications/initialized","params":{}}, sid)


def xql(q):
    body, _ = post({"jsonrpc":"2.0","id":99,"method":"tools/call",
                    "params":{"name":"run_xql_query","arguments":{"request":{"query":q, "tenant_timeframe":{"relativeTime":1800000}}}}}, sid)
    return sse(body)


print("\n" + "=" * 70)
print("VERIFICATION")
print("=" * 70)

results = []
for s in SMOKES:
    name, dataset, marker = s["name"], s["dataset"], s["marker"]
    rfield, xfield = s["raw_field"], s["xdm_field"]
    print(f"\n[{name}] dataset={dataset}")

    # raw
    q1 = f'dataset = {dataset} | filter {rfield} contains "{marker}" or _raw_log contains "{marker}" | limit 1'
    r1 = xql(q1)
    rep1 = r1.get("reply", {})
    s1, n1 = rep1.get("status"), rep1.get("number_of_results", 0)
    raw_cols = 0
    if s1 == "SUCCESS" and n1 > 0:
        row = rep1["results"]["data"][0]
        raw_cols = sum(1 for k,v in row.items() if v not in (None,"","null"))
        print(f"  ✅ raw LANDED ({raw_cols} cols)")
    elif s1 == "FAIL":
        print(f"  ✗ dataset doesn't exist")
        results.append({"name": name, "result": "DATASET_MISSING", "raw_cols": 0, "xdm_cols": 0})
        continue
    elif s1 == "SUCCESS":
        print(f"  ⊘ dataset exists, but our event didn't land (n=0; PR may have rejected)")
    else:
        print(f"  ⚠ raw query status={s1}")

    # xdm
    q2 = f'datamodel dataset = {dataset} | filter {xfield} contains "{marker}" | limit 1'
    r2 = xql(q2)
    rep2 = r2.get("reply", {})
    s2, n2 = rep2.get("status"), rep2.get("number_of_results", 0)
    xdm_cols = 0
    if s2 == "SUCCESS" and n2 > 0:
        row = rep2["results"]["data"][0]
        populated = {k:v for k,v in row.items() if v not in (None,"","null") and k.startswith("xdm.")}
        xdm_cols = len(populated)
        print(f"  ✅ XDM populated ({xdm_cols} fields)")
        for k in sorted(populated)[:10]:
            print(f"    {k:40} = {str(populated[k])[:70]}")
    else:
        print(f"  ⊘ XDM: status={s2}, n={n2}")

    result = "LANDED" if raw_cols > 0 else "RAW_GAP"
    results.append({"name": name, "result": result, "raw_cols": raw_cols, "xdm_cols": xdm_cols})


print("\n" + "=" * 70)
print("BATCH 6 SUMMARY")
print("=" * 70)
print(f"  {'vendor':<24}  {'result':<16}  raw  xdm")
print(f"  {'-'*24}  {'-'*16}  ---  ---")
for r in results:
    icon = "✅" if r["result"] == "LANDED" and r["xdm_cols"] > 0 else "⚠" if r["result"] == "LANDED" else "✗"
    print(f"  {icon} {r['name']:<22}  {r['result']:<16}  {r['raw_cols']:>3}  {r['xdm_cols']:>3}")

landed = sum(1 for r in results if r["result"] == "LANDED")
xdm_fired = sum(1 for r in results if r["xdm_cols"] > 0)
print(f"\n  {landed}/{len(results)} landed raw, {xdm_fired}/{len(results)} fired MR")
