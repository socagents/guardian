#!/usr/bin/env python3
"""Proof-of-concept: Alibaba ActionTrail (a JSON-native vendor) tested via CEF transport.

OPERATOR'S INSIGHT (2026-05-27)
================================
XSIAM's PR/MR rules read NAMED COLUMNS. Whether those columns were populated by
CEF extension extraction OR by JSON-native HTTP collector ingestion is invisible
to the rule. So for any "JSON-native" vendor, we can pack its PR/MR-expected
field names as CEF extension k=v pairs, send via the broker UDP path, and the
same PR/MR fires.

ALIBABA REVERSE ENGINEERING
============================
PR:
    [INGEST:vendor="alibaba", product="action-trail", target_dataset="alibaba_action_trail_raw",
     no_hit=keep, content_id="AlibabaActionTrail"]
    filter __time__ ~= "\d+"
    | alter _time = timestamp_seconds(to_integer(__time__));

MR fields read (from the alibaba_action_trail_raw MODEL block):
    event_eventtype, event_acsregion, event_eventid, event_eventname,
    event_resourcename, event_resourcetype, event_sourceipaddress,
    event_useridentity_type, event_useridentity_principalid,
    event_useridentity_username, event_useridentity_accesskeyid,
    event_errormessage, _vendor, _product

CEF EVENT CONSTRUCTION
======================
CEF header → vendor + product source-tag (Cortex's INGEST routing)
CEF extensions → typed columns the MR reads

Marker carrier: event_eventid (uniquely identifies the event)
"""

from __future__ import annotations

import os
import socket
import time
from datetime import datetime, timezone

BROKER = ("10.10.0.8", 514)
BATCH = int(time.time())
MARKER = f"alibaba-poc-{BATCH}"
ts_bsd = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")

# CEF extension key=value pairs matching the Alibaba MR's expected fields.
# Order: PR filter requirements first (__time__), then MR fields.
ext = {
    "__time__": str(BATCH),                                 # PR filter: \d+ epoch seconds → _time
    "event_eventtype": "ApiCall",                            # MR: xdm.event.type (matched in filter)
    "event_acsregion": "cn-shanghai",                        # MR: xdm.target.cloud.region
    "event_eventid": MARKER,                                 # MR: xdm.event.id (the marker carrier)
    "event_eventname": "ListBuckets",                        # MR: xdm.event.operation
    "event_resourcename": "test-bucket-poc",                 # MR: xdm.target.resource.name
    "event_resourcetype": "OSS::Bucket",                     # MR: xdm.target.resource.type
    "event_sourceipaddress": "10.5.5.10",                    # MR: xdm.source.ipv4
    "event_useridentity_type": "ram-user",                   # MR: xdm.source.user.user_type (enum→SERVICE_ACCOUNT)
    "event_useridentity_principalid": "211441234567890",     # MR: xdm.source.user.identifier
    "event_useridentity_username": "alice-poc",              # MR: xdm.source.user.username
    "event_errormessage": "",                                # MR: xdm.event.description (intentionally empty here)
}

kv = " ".join(f"{k}={v}" for k, v in ext.items())
# CEF header — note vendor=alibaba + product=action-trail in positions 2+3.
# These drive the INGEST routing in the alibaba PR.
msg = (
    f"<134>{ts_bsd} smoke-host CEF:0|alibaba|action-trail|1.0|"
    f"ALIBABA_API|{ext['event_eventname']}|3|{kv}"
)

print(f"=== Alibaba ActionTrail JSON-as-CEF proof ===")
print(f"BATCH={BATCH}, MARKER={MARKER}")
print(f"CEF length: {len(msg)} bytes (under 1500 UDP MTU: {'YES' if len(msg) < 1500 else 'NO'})")
print(f"CEF preview: {msg[:200]}{'...' if len(msg) > 200 else ''}")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for _ in range(3):
    sock.sendto(msg.encode(), BROKER)
sock.close()
print(f"Sent 3× UDP packets to {BROKER[0]}:{BROKER[1]}")

print(f"\nWait 120s for ingestion + XDM materialization...")
for i in range(4):
    time.sleep(30)
    print(f"  +{(i+1)*30}s")

# Query XSIAM
import json, urllib.request

TOKEN = os.environ["MCP_TOKEN"]
MCP = "http://phantom-connector-xsiam-Cortex_XSIAM:9000/mcp"

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
             "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"poc","version":"1"}}})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post({"jsonrpc":"2.0","method":"notifications/initialized","params":{}}, sid)

def xql(q):
    body, _ = post({"jsonrpc":"2.0","id":99,"method":"tools/call",
                    "params":{"name":"run_xql_query","arguments":{"request":{"query":q, "tenant_timeframe":{"relativeTime":900000}}}}}, sid)
    return sse(body)

print("\n=== Query 1: target alibaba_action_trail_raw for our marker ===")
q1 = f'dataset = alibaba_action_trail_raw | filter event_eventid contains "{MARKER}" or _raw_log contains "{MARKER}" | limit 3'
r1 = xql(q1)
reply1 = r1.get("reply", {})
status1 = reply1.get("status", "?")
n1 = reply1.get("number_of_results", 0)
print(f"  status={status1}, n={n1}")
if status1 == "SUCCESS" and n1 > 0:
    row = reply1["results"]["data"][0]
    populated = {k:v for k,v in row.items() if v not in (None, "", "null")}
    print(f"  ✅ LANDED ({len(populated)} populated cols)")
    for k in sorted(populated)[:25]:
        print(f"    {k:40} = {str(populated[k])[:80]}")
elif status1 == "FAIL":
    print(f"  ✗ alibaba_action_trail_raw doesn't exist in tenant (upstream Cortex pack not installed)")

print("\n=== Query 2: probe Fortinet dataset (control — known good vendor we just smoked via syslog) ===")
q2 = f'dataset = fortinet_fortigate_raw | limit 1 | fields _time'
r2 = xql(q2)
reply2 = r2.get("reply", {})
status2 = reply2.get("status", "?")
n2 = reply2.get("number_of_results", 0)
print(f"  status={status2}, n={n2}")

print("\n=== Query 3: search ANY dataset for the marker (catch-all hunt) ===")
q3 = f'datasets() | filter _raw_log contains "{MARKER}" | limit 5'
# Note: datasets() in XQL may not be valid syntax; falling back to broad search
q3_alt = f'preset = network_story | filter _raw_log contains "{MARKER}" | limit 1'
r3 = xql(q3)
print(f"  result keys: {list(r3.keys())}")
reply3 = r3.get("reply", {})
print(f"  status={reply3.get('status')}, n={reply3.get('number_of_results')}")
