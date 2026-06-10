#!/usr/bin/env python3
"""Batch 8 — 4 more JSON-native vendors via CEF wrapping.

VENDORS THIS BATCH
==================
  1. okta_sso_raw                       (Okta SSO — sister dataset to okta_okta_raw)
  2. proofpoint_tap_raw                 (ProofPoint TAP — ccAddresses array, messageParts array)
  3. msft_o365_exchange_online_raw      (O365 Exchange — RecordType + ExchangeMetaData)
  4. msft_o365_dlp_raw                  (O365 DLP — multi-MetaData JSON + EndpointMetaData)
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
# (1) Okta SSO — okta_sso_raw
# ============================================================
# Same shape as okta_okta_raw with slightly different XDM mapping (adds TCP protocol)
OKTA_SSO_MARKER = f"okta-sso-{BATCH}"
okta_sso_actor = json.dumps({"id":f"00u{BATCH}","type":"User","displayName":"BobSSO","alternateId":f"bob-{OKTA_SSO_MARKER}@corp.example.com"}).replace(" ", "")
okta_sso_client = json.dumps({"ipAddress":"198.51.100.77","userAgent":{"rawUserAgent":"Mozilla/5.0SSO","os":"Windows","browser":"FIREFOX"},"device":"Computer","geographicalContext":{"city":"NewYork","country":"USA","state":"NewYork","geolocation":{"lat":40.7,"lon":-74.0}}}).replace(" ", "")
okta_sso_outcome = json.dumps({"result":"SUCCESS","reason":""}).replace(" ", "")
okta_sso_target = json.dumps([{"id":"appinst-002","type":"AppInstance","alternateId":"Workday","displayName":"Workday HCM"}]).replace(" ", "")
okta_sso_auth_ctx = json.dumps({"authenticationProvider":{"credentialProvider":"FEDERATION","credentialType":"PASSWORD","externalSessionId":f"sess-{BATCH}"}}).replace(" ", "")
okta_sso_ext = {
    "uuid": OKTA_SSO_MARKER,
    "published": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    "eventType": "user.session.start",
    "severity": "INFO",
    "displayMessage": "User session started",
    "legacyEventType": "core.user.session.start",
    "actor": okta_sso_actor,
    "client": okta_sso_client,
    "outcome": okta_sso_outcome,
    "target": okta_sso_target,
    "authenticationContext": okta_sso_auth_ctx,
}
okta_sso_cef = f"<134>{ts_bsd} smoke-host CEF:0|okta|sso|1.0|OKTA_SSO|SessionStart|3|" + " ".join(f"{k}={v}" for k, v in okta_sso_ext.items())


# ============================================================
# (2) ProofPoint TAP — proofpoint_tap_raw
# ============================================================
# PR: filter clickTime != null or messageTime != null
# MR fields: ccAddresses (array), fromAddress, GUID, messageID, messageParts (array),
#            recipient (array), senderIP, subject, threatsInfoMap (array),
#            clickIP, messageTime, clickTime
PPT_MARKER = f"ppt-{BATCH}"
ppt_cc_addresses = json.dumps([f"cc1-{PPT_MARKER}@corp.example.com", f"cc2-{PPT_MARKER}@corp.example.com"]).replace(" ", "")
ppt_message_parts = json.dumps([
    {"filename":"invoice.pdf","md5":"9e107d9d372bb6826bd81d3542a419d6","sha256":"44d88612fea8a8f36de82e1278abb02f8c6f3a0a8c70b1cd62f0d8bf2e1f00ab"}
]).replace(" ", "")
ppt_recipient = json.dumps([f"victim-{PPT_MARKER}@corp.example.com"]).replace(" ", "")
ppt_threats = json.dumps([{"threatID":f"threat-{BATCH}","threatType":"PHISH","threatStatus":"active"}]).replace(" ", "")
ppt_ext = {
    "GUID": PPT_MARKER,
    "messageTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    "ccAddresses": ppt_cc_addresses,
    "fromAddress": f"attacker-{PPT_MARKER}@malicious.example",
    "messageID": f"<msg-{BATCH}@malicious.example>",
    "messageParts": ppt_message_parts,
    "recipient": ppt_recipient,
    "senderIP": "203.0.113.222",
    "subject": f"Urgent: {PPT_MARKER}",
    "threatsInfoMap": ppt_threats,
    "clickIP": "10.5.5.111",
}
ppt_cef = f"<134>{ts_bsd} smoke-host CEF:0|proofpoint|tap|1.0|PPT_THREAT|MessageBlocked|3|" + " ".join(f"{k}={v}" for k, v in ppt_ext.items())


# ============================================================
# (3) O365 Exchange Online — msft_o365_exchange_online_raw
# ============================================================
# MR fields: CreationTime, Id, Operation, RecordType, OrganizationId, UserKey, UserType, UserId,
#            ClientIPAddress, ClientIP, LogonType, InternalLogonType, Scope, MailboxOwnerUPN,
#            ClientMachineName, LogonUserDisplayName, OriginatingServer, ClientProcessName,
#            ClientApplication, ExchangeMetaData (JSON: BCC, CC, To, MessageID, Subject, From),
#            Item (JSON: InternetMessageId, ParentFolder.Path, ParentFolder.id, Subject),
#            ModifiedProperties (JSON), AffectedItems (JSON array),
#            ClientInfoString, PolicyDetails (JSON), ResultStatus, OperationProperties (JSON),
#            ItemId, AppAccessContext (JSON)
O365_EX_MARKER = f"o365ex-{BATCH}"
o365_ex_metadata = json.dumps({"From":f"alice-{O365_EX_MARKER}@corp.example.com","To":["recipient1@corp.example.com"],"CC":[],"BCC":[],"Subject":"Exchange CEF smoke","MessageID":f"<msg-{BATCH}@exchange>","Sent":datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")}).replace(" ", "")
o365_ex_item = json.dumps({"InternetMessageId":f"<imid-{BATCH}@exchange>","Subject":"Exchange CEF smoke","ParentFolder":{"Path":"\\Inbox","id":"folder-001"}}).replace(" ", "")
o365_ex_appctx = json.dumps({"CorrelationId":f"corr-{BATCH}","ClientAppName":"OWA"}).replace(" ", "")
o365_ex_ext = {
    "CreationTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    "Id": O365_EX_MARKER,
    "Operation": "MailItemsAccessed",
    "RecordType": "50",  # ExchangeItemAggregated
    "OrganizationId": "org-corp-001",
    "UserKey": f"alice-{O365_EX_MARKER}",
    "UserType": "2",
    "UserId": f"alice-{O365_EX_MARKER}@corp.example.com",
    "ClientIPAddress": "203.0.113.150",
    "LogonType": "0",
    "Scope": "0",
    "MailboxOwnerUPN": f"alice-{O365_EX_MARKER}@corp.example.com",
    "ClientMachineName": "alice-laptop",
    "LogonUserDisplayName": "Alice CEF",
    "OriginatingServer": "exchange01.corp.example.com",
    "ClientProcessName": "outlook.exe",
    "ClientApplication": "Outlook",
    "ExchangeMetaData": o365_ex_metadata,
    "Item": o365_ex_item,
    "ResultStatus": "Succeeded",
    "AppAccessContext": o365_ex_appctx,
    "Workload": "Exchange",
}
o365_ex_cef = f"<134>{ts_bsd} smoke-host CEF:0|msft|O365 Exchange Online|1.0|O365EX|MailAccessed|3|" + " ".join(f"{k}={v}" for k, v in o365_ex_ext.items())


# ============================================================
# (4) O365 DLP — msft_o365_dlp_raw
# ============================================================
# MR fields: CreationTime, Id, Operation, OrganizationId, RecordType, UserType, UserKey, UserId,
#            ClientIP, Workload, Scope, ObjectId, ResultStatus, ExchangeMetaData (JSON),
#            SharePointMetaData (JSON: FileName, FilePathUrl, SiteCollectionUrl, From, FileSize),
#            EndpointMetaData (JSON: EnforcementMode, FileExtension, FileType, DeviceName),
#            ExceptionInfo (JSON), PolicyDetails (JSON), AppAccessContext (JSON)
DLP_MARKER = f"dlp-{BATCH}"
dlp_sharepoint = json.dumps({"FileName":f"financials-{DLP_MARKER}.xlsx","FilePathUrl":"https://corp.sharepoint.com/sites/finance/Shared Documents/financials.xlsx","SiteCollectionUrl":"https://corp.sharepoint.com/sites/finance","From":f"alice-{DLP_MARKER}@corp.example.com","FileSize":"4096"}).replace(" ", "")
dlp_endpoint = json.dumps({"EnforcementMode":"4","FileExtension":"xlsx","FileType":"Excel","DeviceName":"alice-laptop"}).replace(" ", "")
dlp_appctx = json.dumps({"CorrelationId":f"corr-{BATCH}","ClientAppName":"Word"}).replace(" ", "")
dlp_ext = {
    "CreationTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    "Id": DLP_MARKER,
    "Operation": "DLPRuleMatch",
    "OrganizationId": "org-corp-001",
    "RecordType": "11",  # ComplianceDLPSharePoint
    "UserType": "2",
    "UserKey": f"alice-{DLP_MARKER}",
    "UserId": f"alice-{DLP_MARKER}@corp.example.com",
    "ClientIP": "10.5.5.200",
    "Workload": "OneDrive",
    "Scope": "0",
    "ObjectId": f"sharepoint-doc-{DLP_MARKER}",
    "ResultStatus": "Succeeded",
    "SharePointMetaData": dlp_sharepoint,
    "EndpointMetaData": dlp_endpoint,
    "AppAccessContext": dlp_appctx,
    "evaluationsource": "Default",
}
dlp_cef = f"<134>{ts_bsd} smoke-host CEF:0|msft|O365 DLP|1.0|O365DLP|RuleMatch|3|" + " ".join(f"{k}={v}" for k, v in dlp_ext.items())


SMOKES = [
    {"name": "Okta SSO",              "dataset": "okta_sso_raw",                       "event": okta_sso_cef, "marker": OKTA_SSO_MARKER, "raw_field": "uuid", "xdm_field": "xdm.event.id"},
    {"name": "ProofPoint TAP",         "dataset": "proofpoint_tap_raw",                 "event": ppt_cef,      "marker": PPT_MARKER,      "raw_field": "GUID", "xdm_field": "xdm.event.id"},
    {"name": "O365 Exchange Online",   "dataset": "msft_o365_exchange_online_raw",      "event": o365_ex_cef,  "marker": O365_EX_MARKER,  "raw_field": "Id",   "xdm_field": "xdm.event.id"},
    {"name": "O365 DLP",               "dataset": "msft_o365_dlp_raw",                  "event": dlp_cef,      "marker": DLP_MARKER,      "raw_field": "Id",   "xdm_field": "xdm.event.id"},
]


print("=" * 70)
print(f"BATCH 8 — 4 more JSON-native vendors via CEF wrapping  ({BATCH})")
print("=" * 70)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for s in SMOKES:
    e = s["event"]
    print(f"\n[{s['name']}]  → {BROKER[0]}:{BROKER[1]}  ({len(e)} bytes)")
    print(f"  marker={s['marker']}")
    if len(e) >= 1500:
        print(f"  ⚠ OVER UDP MTU 1500 ({len(e)} bytes)")
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
             "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"b8","version":"1"}}})
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
        print(f"  ⚠ raw status={s1}, err={(r1.get('_xql_error') or r1.get('error') or '?')[:200] if isinstance(r1.get('_xql_error') or r1.get('error') or '?', str) else '?'}")

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
            print(f"    {k:42} = {str(populated[k])[:70]}")
    else:
        print(f"  ⊘ XDM: status={s2}, n={n2}")

    result = "LANDED" if raw_cols > 0 else "RAW_GAP"
    results.append({"name": name, "result": result, "raw_cols": raw_cols, "xdm_cols": xdm_cols})


print("\n" + "=" * 70)
print("BATCH 8 SUMMARY")
print("=" * 70)
print(f"  {'vendor':<28}  {'result':<16}  raw  xdm")
print(f"  {'-'*28}  {'-'*16}  ---  ---")
for r in results:
    icon = "✅" if r["result"] == "LANDED" and r["xdm_cols"] > 0 else "⚠" if r["result"] == "LANDED" else "✗"
    print(f"  {icon} {r['name']:<26}  {r['result']:<16}  {r['raw_cols']:>3}  {r['xdm_cols']:>3}")

landed = sum(1 for r in results if r["result"] == "LANDED")
xdm_fired = sum(1 for r in results if r["xdm_cols"] > 0)
print(f"\n  {landed}/{len(results)} landed raw, {xdm_fired}/{len(results)} fired MR")
