#!/usr/bin/env python3
"""Batch 10 — final 4 JSON-native vendors via CEF wrapping.

VENDORS:
  1. proofpoint_threat_response_raw   (PTR — alert event with nested emails/hosts)
  2. msft_o365_sharepoint_online_raw  (O365 SP — SiteUrl, SharePointMetaData)
  3. msft_o365_emails_raw              (O365 Emails — from/to/cc emailAddress JSON)
  4. msft_azure_waf_raw                (Azure WAF — FrontDoorAccessLog branch)
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
ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


# (1) ProofPoint Threat Response
PTR_MARKER = f"ptr-{BATCH}"
ptr_event = json.dumps({
    "id": int(BATCH),
    "category": "phish",
    "severity": "High",
    "description": f"Phishing email blocked — {PTR_MARKER}",
    "fileName": "phishing-attachment.pdf",
    "emails": [{"sender": {"email": "attacker@malicious.example"}, "messageId": f"msg-{BATCH}", "subject": "Urgent Invoice", "recipient": {"email": f"victim-{PTR_MARKER}@corp.example.com"}}],
}).replace(" ", "")
ptr_hosts = json.dumps({"attacker": ["203.0.113.180", "203.0.113.181"]}).replace(" ", "")
ptr_incident_fields = json.dumps([{"name":"category","value":"phish"},{"name":"name","value":f"Phish-{PTR_MARKER}"}]).replace(" ", "")

ptr_ext = {
    "updated_at": ts_iso,
    "id": str(BATCH),
    "event": ptr_event,
    "hosts": ptr_hosts,
    "incident_field_values": ptr_incident_fields,
}
ptr_cef = f"<134>{ts_bsd} smoke-host CEF:0|proofpoint|threat_response|1.0|PTR_ALERT|PhishBlock|3|" + " ".join(f"{k}={v}" for k, v in ptr_ext.items())


# (2) O365 SharePoint Online
SP_MARKER = f"sp-{BATCH}"
sp_metadata = json.dumps({"FileName":f"contract-{SP_MARKER}.docx","FilePathUrl":"https://corp.sharepoint.com/sites/legal/contract.docx","FileSize":"8192","From":f"alice-{SP_MARKER}@corp.example.com"}).replace(" ", "")
sp_appctx = json.dumps({"CorrelationId":f"corr-{BATCH}","ClientAppName":"OneDrive Sync","AADSessionId":f"sess-{BATCH}"}).replace(" ", "")
sp_ext = {
    "CreationTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
    "Id": SP_MARKER,
    "Operation": "FileDownloaded",
    "OrganizationId": "org-corp-001",
    "RecordType": "6",  # SharePointFileOperation
    "UserType": "0",
    "UserKey": f"alice-{SP_MARKER}",
    "UserId": f"alice-{SP_MARKER}@corp.example.com",
    "ClientIP": "203.0.113.220",
    "Workload": "OneDrive",
    "ObjectId": f"sp-doc-{SP_MARKER}",
    "ItemType": "File",
    "Site": "https://corp.sharepoint.com/sites/legal",
    "SiteUrl": "https://corp.sharepoint.com/sites/legal",
    "SourceFileName": f"contract-{SP_MARKER}.docx",
    "SourceRelativeUrl": "contract.docx",
    "SourceFileExtension": "docx",
    "ResultStatus": "Succeeded",
    "SharePointMetaData": sp_metadata,
    "AppAccessContext": sp_appctx,
    "EventSource": "SharePoint",
}
sp_cef = f"<134>{ts_bsd} smoke-host CEF:0|msft|O365 Sharepoint Online|1.0|O365_SP|FileDownloaded|3|" + " ".join(f"{k}={v}" for k, v in sp_ext.items())


# (3) O365 Emails
EMAIL_MARKER = f"email-{BATCH}"
email_from = json.dumps({"emailAddress":{"name":"Alice CEF","address":f"alice-{EMAIL_MARKER}@corp.example.com"}}).replace(" ", "")
email_to = json.dumps([{"emailAddress":{"address":f"bob-{EMAIL_MARKER}@partner.example.com"}}]).replace(" ", "")
email_cc = json.dumps([{"emailAddress":{"address":f"manager-{EMAIL_MARKER}@corp.example.com"}}]).replace(" ", "")
email_ext = {
    "id": EMAIL_MARKER,
    "subject": f"CEF email smoke {EMAIL_MARKER}",
    "sentDateTime": ts_iso,
    "receivedDateTime": ts_iso,
    "from": email_from,
    "toRecipients": email_to,
    "ccRecipients": email_cc,
    "mailboxOwner": f"alice-{EMAIL_MARKER}@corp.example.com",
    "internetMessageId": f"<msg-{BATCH}@corp.example.com>",
    "importance": "high",
    "isRead": "false",
    "hasAttachments": "true",
}
email_cef = f"<134>{ts_bsd} smoke-host CEF:0|msft|o365_emails|1.0|EMAIL_SENT|MessageSent|3|" + " ".join(f"{k}={v}" for k, v in email_ext.items())


# (4) Azure WAF — FrontDoorAccessLog branch
WAF_MARKER = f"azwaf-{BATCH}"
waf_ext = {
    "time": ts_iso,
    "Category": "FrontDoorAccessLog",
    "Resource": f"corp-frontdoor-{WAF_MARKER}",
    "ResourceGroup": "rg-frontdoor",
    "ResourceType": "FRONTDOORS",
    "operationName": "Microsoft.Cdn/frontdoor/access",
    "resourceId": f"/subscriptions/sub-001/resourceGroups/rg-frontdoor/providers/Microsoft.Cdn/profiles/corp-fd",
    "trackingReference_s": WAF_MARKER,
    "clientIP_s": "203.0.113.99",
    "httpMethod_s": "POST",
    "httpStatusCode_s": "200",
    "requestUri_s": "/api/login",
    "domain_s": f"app-{WAF_MARKER}.azurefd.net",
    "userAgent_s": "Mozilla/5.0 AzureWAF CEF",
    "originUrl_s": "https://backend.corp.example.com/api/login",
    "originIp_s": "10.5.5.250",
    "timeTaken_s": "0.045",
    "requestBytes_s": "1024",
    "responseBytes_s": "512",
    "errorInfo_s": "NoError",
    "routingRuleName_s": "default-rule",
    "endpoint_s": "corp-endpoint",
    "sni_s": f"app-{WAF_MARKER}.azurefd.net",
    "securityCipher_s": "ECDHE-RSA-AES256-GCM-SHA384",
    "originCryptProtocol_s": "TLSv1.2",
    "referer_s": "https://corp.example.com",
}
waf_cef = f"<134>{ts_bsd} smoke-host CEF:0|msft|azure_waf|1.0|AZWAF_FD|FrontDoorAccess|3|" + " ".join(f"{k}={v}" for k, v in waf_ext.items())


SMOKES = [
    {"name": "ProofPoint Threat Resp",  "dataset": "proofpoint_threat_response_raw", "event": ptr_cef,   "marker": PTR_MARKER,   "raw_field": "id",                "xdm_field": "xdm.alert.original_alert_id"},
    {"name": "O365 SharePoint Online",  "dataset": "msft_o365_sharepoint_online_raw","event": sp_cef,    "marker": SP_MARKER,    "raw_field": "Id",                "xdm_field": "xdm.event.id"},
    {"name": "O365 Emails",             "dataset": "msft_o365_emails_raw",           "event": email_cef, "marker": EMAIL_MARKER, "raw_field": "id",                "xdm_field": "xdm.event.id"},
    {"name": "Azure WAF (FrontDoor)",   "dataset": "msft_azure_waf_raw",             "event": waf_cef,   "marker": WAF_MARKER,   "raw_field": "trackingReference_s","xdm_field": "xdm.event.id"},
]


print("=" * 70)
print(f"BATCH 10 — final 4 JSON-native vendors  ({BATCH})")
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
             "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"b10","version":"1"}}})
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
        print(f"  ⚠ status={s1}")

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
print("BATCH 10 SUMMARY")
print("=" * 70)
for r in results:
    icon = "✅" if r["result"] == "LANDED" and r["xdm_cols"] > 0 else "⚠" if r["result"] == "LANDED" else "✗"
    print(f"  {icon} {r['name']:<26}  {r['result']:<14}  raw={r['raw_cols']:>3}  xdm={r['xdm_cols']:>3}")

landed = sum(1 for r in results if r["result"] == "LANDED")
xdm_fired = sum(1 for r in results if r["xdm_cols"] > 0)
print(f"\n  {landed}/{len(results)} landed raw, {xdm_fired}/{len(results)} fired MR")
