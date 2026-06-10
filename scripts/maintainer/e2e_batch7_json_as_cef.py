#!/usr/bin/env python3
"""Batch 7 — 4 more JSON-native vendors via CEF wrapping.

VENDORS THIS BATCH
==================
  1. proofpoint_email_security_raw  (message branch — heavy nested JSON: msg, connection, msgParts[])
  2. oracle_cloud_infrastructure_raw (data JSON with identity, request, response, stateChange)
  3. qualys_qualys_raw               (activity_log branch — Module, Action, Details, User fields)
  4. msft_azure_ad_raw               (Azure AD sign-in logs — flat top-level + a few JSON)
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
# (1) ProofPoint Email Security — message branch
# ============================================================
# PR: vendor=proofpoint, product=email_security; timestamp on audit -> tags[]
# MR filter: event_type = "message"
# MR fields: event_type, guid, connection (JSON: sid, ip, host, protocol, tls),
#            msg (JSON: normalizedHeader.from[], to[], cc[], subject[], message-id[], return-path[]),
#            msgParts (JSON array: detectedExt, detectedMime, detectedName, md5, sha256),
#            envelope (JSON: from), `filter` (JSON: actions array, modules.av.virusNames[])
PPE_MARKER = f"ppe-{BATCH}"
ppe_connection = json.dumps({
    "sid": f"sess-{BATCH}", "ip": "203.0.113.77", "host": "sender.example.com",
    "protocol": "SMTP", "country": "US",
    "tls": {"inbound": {"cipher": "ECDHE-RSA-AES256-GCM-SHA384", "version": "TLSv1.2"}}
}).replace(" ", "")
ppe_msg = json.dumps({
    "normalizedHeader": {
        "from": ["\"Attacker\" <attacker@malicious.example>"],
        "to": [f"victim-{PPE_MARKER}@corp.example.com"],
        "cc": [f"team-{PPE_MARKER}@corp.example.com"],
        "subject": [f"Urgent invoice {PPE_MARKER}"],
        "message-id": [f"<msg-{BATCH}@malicious.example>"],
        "return-path": ["bounce@malicious.example"],
    }
}).replace(" ", "")
ppe_msg_parts = json.dumps([
    {"detectedExt": "pdf", "detectedMime": "application/pdf",
     "detectedName": "invoice.pdf", "md5": "9e107d9d372bb6826bd81d3542a419d6",
     "sha256": "44d88612fea8a8f36de82e1278abb02f8c6f3a0a8c70b1cd62f0d8bf2e1f00ab",
     "filename": f"invoice-{PPE_MARKER}.pdf"}
]).replace(" ", "")
ppe_envelope = json.dumps({"from": "attacker@malicious.example"}).replace(" ", "")
ppe_filter = json.dumps({
    "actions": [{"action": "reject", "isFinal": "true"}],
    "modules": {"av": {"virusNames": ["Trojan.Generic.PDF.malicious"]}}
}).replace(" ", "")

ppe_ext = {
    "event_type": "message",                 # MR filter requirement
    "guid": PPE_MARKER,                       # MR: xdm.event.id (marker)
    "connection": ppe_connection,             # MR: nested
    "msg": ppe_msg,                           # MR: nested with deep paths
    "msgParts": ppe_msg_parts,                # MR: nested array
    "envelope": ppe_envelope,                 # MR: nested
    "filter": ppe_filter,                     # MR: nested with actions[] + modules.av.virusNames[]
}
ppe_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|proofpoint|email_security|1.0|PPE_MSG|MessageReceived|3|"
    + " ".join(f"{k}={v}" for k, v in ppe_ext.items())
)


# ============================================================
# (2) Oracle Cloud Infrastructure — oracle_cloud_infrastructure_raw
# ============================================================
# PR: vendor=oracle, product=cloud (or similar)
# MR fields: cloudEventsVersion, contentType, eventId, eventType, eventTypeVersion,
#            data (JSON: additionalDetails, availabilityDomain, eventName, resourceId,
#                  resourceName, identity.*, request.*, response.*, stateChange.*)
OCI_MARKER = f"oci-{BATCH}"
oci_data = json.dumps({
    "additionalDetails": {"vmShape": "VM.Standard2.1", "vmInstance": "ocid-001"},
    "availabilityDomain": "PHX-AD-1",
    "eventName": "LaunchInstance",
    "resourceId": f"ocid1.instance.oc1..{OCI_MARKER}",
    "resourceName": f"web-server-{OCI_MARKER}",
    "identity": {
        "authType": "natv", "callerId": "user-12345", "callerName": "alice",
        "ipAddress": "203.0.113.88", "principalId": "principal-001",
        "tenantId": "tenant-prod-001", "userAgent": "OCI-CLI/3.0"
    },
    "request": {
        "action": "POST", "headers": {"User-Agent": "OCI-CLI"},
        "id": f"req-{BATCH}", "path": "/20160918/instances", "parameters": {}
    },
    "response": {"status": "200", "message": "Instance created"},
    "stateChange": {"current": "RUNNING", "previous": "STOPPED"}
}).replace(" ", "")
oci_ext = {
    "cloudEventsVersion": "0.1",             # MR: xdm.source.agent.content_version
    "contentType": "application/json",       # MR: xdm.network.http.content_type
    "eventId": OCI_MARKER,                   # MR: xdm.event.id (marker)
    "eventType": "com.oraclecloud.computeapi.launchinstance.end",  # MR: xdm.event.type
    "eventTypeVersion": "2.0",               # MR: xdm.source.application.version
    "data": oci_data,                        # MR: nested with all the real content
    "source": "computeApi",                  # MR: contextual
    "eventTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
}
oci_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|oracle|cloud|1.0|OCI_API|LaunchInstance|3|"
    + " ".join(f"{k}={v}" for k, v in oci_ext.items())
)


# ============================================================
# (3) Qualys — activity_log branch
# ============================================================
# PR: vendor=qualys, product=qualys (presumably)
# MR filter: event_type in ("activity_log")
# MR fields: event_type, Action, Module, Details (JSON-encoded — regex parsed), User_IP, User_Name, User_Role
QUALYS_MARKER = f"qualys-{BATCH}"
# Details is JSON-encoded inside a single string the MR regex-parses out
qualys_details = (
    f'{{"requestId":"req-{QUALYS_MARKER}","entityName":"WebApp-Prod","operation":"create",'
    f'"assetGroupId":"AG-001","name":"web-prod","businessImpact":"high","businessDivision":"IT",'
    f'"modules":"VM,WAS","format":"CSV","ID":"report-{BATCH}"}}'
)
qualys_ext = {
    "event_type": "activity_log",            # MR filter requirement
    "Action": "Create",                       # MR: xdm.observer.action (marker context)
    "Module": "WAS",                          # MR: xdm.event.type
    "Details": qualys_details,                # MR: xdm.event.description + regex-parsed fields
    "User_IP": "10.5.5.99",                   # MR: xdm.source.ipv4
    "User_Name": f"alice-{QUALYS_MARKER}",    # MR: xdm.source.user.username (marker)
    "User_Role": "Manager",                   # MR: xdm.auth.privilege_level
    "Date": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
}
qualys_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|qualys|qualys|1.0|QUALYS_AUDIT|WebAppCreate|3|"
    + " ".join(f"{k}={v}" for k, v in qualys_ext.items())
)


# ============================================================
# (4) Microsoft Azure AD — msft_azure_ad_raw (sign-in logs)
# ============================================================
# PR: vendor=msft, product="Azure AD"
# PR filter: to_string(createdDateTime) ~= ".*\d{2}:\d{2}:\d{2}.*"
# MR fields: id, originalRequestId, createdDateTime, conditionalAccessStatus, userPrincipalName,
#            userId, userDisplayName, appDisplayName, servicePrincipalName, clientAppUsed,
#            authenticationProtocol, tokenIssuerType, clientCredentialType, riskState,
#            riskDetail, riskLevelDuringSignIn, riskEventTypes_v2 (array), location (JSON),
#            status (JSON: failureReason, additionalDetails, errorCode), homeTenantId,
#            resourceTenantId, deviceDetail (JSON), processingTimeInMilliseconds,
#            callerIpAddress, ipAddress, ipAddressFromResourceProvider, autonomousSystemNumber,
#            authenticationDetails (array), authenticationProcessingDetails (array),
#            networkLocationDetails (array), appliedConditionalAccessPolicies (array),
#            authenticationMethodsUsed (array), authenticationRequirement, userType,
#            signInEventTypes (array), operatingSystem
AAD_S_MARKER = f"aad-signin-{BATCH}"
aad_s_location = json.dumps({"city": "San Francisco", "countryOrRegion": "US",
                              "geoCoordinates": {"latitude": 37.7, "longitude": -122.4}}).replace(" ", "")
aad_s_status = json.dumps({"failureReason": None, "additionalDetails": None, "errorCode": 0}).replace(" ", "")
aad_s_device = json.dumps({"deviceId": "dev-001", "displayName": "alice-mbp",
                            "operatingSystem": "macOS 14", "browser": "Chrome 120",
                            "trustType": "AzureAdJoined"}).replace(" ", "")
aad_s_ext = {
    "createdDateTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    "id": AAD_S_MARKER,                                            # MR: xdm.event.id (marker)
    "originalRequestId": f"req-{BATCH}",
    "conditionalAccessStatus": "success",                          # MR: drives outcome
    "userPrincipalName": f"alice-{AAD_S_MARKER}@corp.example.com", # MR: xdm.source.user.upn
    "userDisplayName": "Alice CEF",                                # MR: xdm.source.user.first_name
    "userId": "user-12345",
    "appDisplayName": "Salesforce",                                # MR: xdm.source.application.name
    "clientAppUsed": "Browser",                                    # MR: xdm.event.operation_sub_type
    "authenticationProtocol": "saml",                              # MR: xdm.auth.service
    "tokenIssuerType": "AzureAD",
    "clientCredentialType": "none",                                # MR: xdm.auth.auth_method
    "riskState": "none",                                           # MR: xdm.observer.action
    "riskDetail": "none",                                          # MR: xdm.alert.name
    "riskLevelDuringSignIn": "none",                               # MR: xdm.alert.severity (filtered if "none")
    "userType": "member",                                          # MR: xdm.auth.privilege_level
    "authenticationRequirement": "singleFactorAuthentication",     # MR: xdm.auth.mfa.client_details
    "homeTenantId": "tenant-corp-001",                             # MR: xdm.source.cloud.project_id
    "resourceTenantId": "tenant-corp-001",
    "callerIpAddress": "203.0.113.111",                            # MR: xdm.source.ipv4
    "ipAddress": "203.0.113.111",
    "autonomousSystemNumber": "15169",                             # MR: xdm.source.asn.as_number
    "location": aad_s_location,                                    # MR: nested location
    "status": aad_s_status,                                        # MR: nested status
    "deviceDetail": aad_s_device,                                  # MR: nested deviceDetail
    "operatingSystem": "macOS",                                    # MR: xdm.source.host.os_family
    "processingTimeInMilliseconds": "350",                         # MR: xdm.event.duration
}
aad_s_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|msft|Azure AD|1.0|AAD_SIGNIN|UserSignIn|3|"
    + " ".join(f"{k}={v}" for k, v in aad_s_ext.items())
)


SMOKES = [
    {"name": "ProofPoint Email Sec",   "dataset": "proofpoint_email_security_raw",  "event": ppe_cef,   "marker": PPE_MARKER,    "raw_field": "guid",    "xdm_field": "xdm.event.id"},
    {"name": "Oracle Cloud Infra",     "dataset": "oracle_cloud_infrastructure_raw","event": oci_cef,   "marker": OCI_MARKER,    "raw_field": "eventId", "xdm_field": "xdm.event.id"},
    {"name": "Qualys (activity_log)",  "dataset": "qualys_qualys_raw",              "event": qualys_cef,"marker": QUALYS_MARKER, "raw_field": "User_Name","xdm_field": "xdm.source.user.username"},
    {"name": "MS Azure AD (sign-in)",  "dataset": "msft_azure_ad_raw",              "event": aad_s_cef, "marker": AAD_S_MARKER,  "raw_field": "id",      "xdm_field": "xdm.event.id"},
]


print("=" * 70)
print(f"BATCH 7 — 4 more JSON-native vendors via CEF wrapping  ({BATCH})")
print("=" * 70)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for s in SMOKES:
    e = s["event"]
    print(f"\n[{s['name']}]  → {BROKER[0]}:{BROKER[1]}  ({len(e)} bytes)")
    print(f"  marker={s['marker']}")
    if len(e) >= 1500:
        print(f"  ⚠ OVER UDP MTU 1500 ({len(e)} bytes) — broker may truncate!")
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
             "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"b7","version":"1"}}})
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
        print(f"  ⊘ dataset exists, n=0 (PR may have rejected)")
    else:
        print(f"  ⚠ status={s1}, err={r1.get('_xql_error') or r1.get('error', '?')}")

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
        for k in sorted(populated)[:12]:
            print(f"    {k:42} = {str(populated[k])[:70]}")
    else:
        print(f"  ⊘ XDM: status={s2}, n={n2}")

    result = "LANDED" if raw_cols > 0 else "RAW_GAP"
    results.append({"name": name, "result": result, "raw_cols": raw_cols, "xdm_cols": xdm_cols})


print("\n" + "=" * 70)
print("BATCH 7 SUMMARY")
print("=" * 70)
print(f"  {'vendor':<28}  {'result':<16}  raw  xdm")
print(f"  {'-'*28}  {'-'*16}  ---  ---")
for r in results:
    icon = "✅" if r["result"] == "LANDED" and r["xdm_cols"] > 0 else "⚠" if r["result"] == "LANDED" else "✗"
    print(f"  {icon} {r['name']:<26}  {r['result']:<16}  {r['raw_cols']:>3}  {r['xdm_cols']:>3}")

landed = sum(1 for r in results if r["result"] == "LANDED")
xdm_fired = sum(1 for r in results if r["xdm_cols"] > 0)
print(f"\n  {landed}/{len(results)} landed raw, {xdm_fired}/{len(results)} fired MR")
