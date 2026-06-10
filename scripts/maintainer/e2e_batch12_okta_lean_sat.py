#!/usr/bin/env python3
"""Batch 12 — focused Okta lean-saturation (target < 1500B + max XDM).

Prior Okta saturation: 1886B → truncated → only 10 XDM.
Strategy here: shorter values, denser MR-mapping coverage, single event under MTU.
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
OKTA_MARKER = f"okta-lean-{BATCH}"
ts_bsd = datetime.now(timezone.utc).strftime("%b %d %H:%M:%S")
ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# Tight Okta saturation — every key/value optimized for length
# Targets MR mappings without redundant verbosity
okta_actor = '{"id":"00uA","type":"User","displayName":"Alice","alternateId":"a@c.com"}'
okta_client = '{"ipAddress":"203.0.113.55","userAgent":{"rawUserAgent":"Chrome120","os":"MacOSX","browser":"CHROME"},"device":"Computer","geographicalContext":{"city":"SF","country":"US","state":"CA","geolocation":{"lat":37.7,"lon":-122.4}},"id":"clt1","zone":"OffN"}'
okta_outcome = '{"result":"SUCCESS","reason":"OK"}'
okta_target = '[{"id":"appi1","type":"AppInstance","alternateId":"SF","displayName":"Salesforce"}]'
okta_auth_ctx = '{"authenticationProvider":{"credentialProvider":"OKTA","credentialType":"PASSWORD","externalSessionId":"sess1"}}'
okta_tx = '{"id":"tx1","type":"WEB"}'
okta_sec = '{"asNumber":15169,"asOrg":"Google","isp":"google","domain":"g.com","isProxy":"false"}'
okta_req = '{"ipChain":[{"ip":"203.0.113.55"}]}'
okta_dbg = '{"debugData":{"deviceFingerprint":"fp1","risk":{"level":"LOW"},"behaviors":"Normal","threatSuspected":"false","originalPrincipal":{"type":"User"},"url":"https://okta.example.com"}}'
okta_ext = {
    "uuid": OKTA_MARKER,
    "published": ts_iso,
    "eventType": "user.authentication.sso",
    "legacyEventType": "core.user.session.start",
    "severity": "INFO",
    "displayMessage": f"SSO {OKTA_MARKER}",
    "actor": okta_actor,
    "client": okta_client,
    "outcome": okta_outcome,
    "target": okta_target,
    "authenticationContext": okta_auth_ctx,
    "transaction": okta_tx,
    "securityContext": okta_sec,
    "request": okta_req,
    "debugContext": okta_dbg,
}
kv = " ".join(f"{k}={v}" for k, v in okta_ext.items())
msg = f"<134>{ts_bsd} h CEF:0|okta|okta|1.0|SSO|sso|3|{kv}"

print(f"BATCH={BATCH} MARKER={OKTA_MARKER}")
print(f"CEF length: {len(msg)} bytes (under MTU 1500: {'YES' if len(msg) < 1500 else 'NO'})")

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for _ in range(3):
    sock.sendto(msg.encode(), BROKER)
sock.close()
print("Sent. Waiting 120s...")
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
             "params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"b12","version":"1"}}})
sid = h.get("mcp-session-id") or h.get("Mcp-Session-Id")
post({"jsonrpc":"2.0","method":"notifications/initialized","params":{}}, sid)

def xql(q):
    body, _ = post({"jsonrpc":"2.0","id":99,"method":"tools/call",
                    "params":{"name":"run_xql_query","arguments":{"request":{"query":q, "tenant_timeframe":{"relativeTime":1800000}}}}}, sid)
    return sse(body)

q = f'datamodel dataset = okta_okta_raw | filter xdm.event.id contains "{OKTA_MARKER}" | limit 1'
r = xql(q)
reply = r.get("reply", {})
s, n = reply.get("status"), reply.get("number_of_results", 0)
print(f"\nstatus={s}, n={n}")
if s == "SUCCESS" and n > 0:
    row = reply["results"]["data"][0]
    populated = {k:v for k,v in row.items() if v not in (None,"","null") and k.startswith("xdm.")}
    print(f"\n✅ XDM populated: {len(populated)} fields")
    for k in sorted(populated):
        print(f"  {k:42} = {str(populated[k])[:75]}")
