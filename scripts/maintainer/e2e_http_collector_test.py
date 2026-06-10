#!/usr/bin/env python3
"""Send an Okta-shaped event to XSIAM via HTTP Collector + verify it lands.

The operator already configured an HTTP Collector destination
(https://api-ayman.xdr.eu.paloaltonetworks.com/logs/v1/event) with
auth_id=101 + auth_key. We POST JSON events directly; XSIAM's HTTP
collector tags them with whatever source the destination's "source"
field declares and the parsing rule maps to a dataset.
"""
import json, os, ssl, time, urllib.request
from datetime import datetime, timezone

TOKEN = os.environ["MCP_TOKEN"]
XSIAM_BASE = "http://phantom-connector-xsiam-Cortex_XSIAM:9000"
COLLECTOR_URL = "https://api-ayman.xdr.eu.paloaltonetworks.com/logs/v1/event"
AUTH_KEY = "MTAyOlB4cXQ3azRTZTV0dDBIRUI1OWIzNnlrMHpBQlEzam43R3VCS3pPbDlad3pvZHM5NER5TE54SXBzbkhKWGpHd2VxT09TV2JKQXlsdU5oYUVNSGdyWktMOWltVEQyc3NqSUdpYW1jNk85NkFkWUVpdkc2czZHSnl6TDlqVXZYTVh5"
SSL_CTX = ssl.create_default_context(); SSL_CTX.check_hostname=False; SSL_CTX.verify_mode=ssl.CERT_NONE

SMOKE = f"smk-okta-http-{int(time.time())}"

# Build an Okta-shaped event matching the schema columns
# (client, actor, eventType, outcome, target, displayMessage, etc.)
event = {
    "uuid": SMOKE,
    "published": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
    "eventType": "user.authentication.auth_via_mfa",
    "severity": "INFO",
    "legacyEventType": "core.user.factor.attempt_success",
    "displayMessage": f"Authentication of user via MFA marker_{SMOKE}",
    "actor": {
        "id": f"00u{SMOKE[-8:]}",
        "type": "User",
        "alternateId": "jdoe@example.com",
        "displayName": "John Doe",
    },
    "client": {
        "ipAddress": "192.0.2.45",
        "userAgent": {"rawUserAgent": "Mozilla/5.0", "os": "Linux", "browser": "Firefox"},
        "geographicalContext": {"country": "United States"},
    },
    "outcome": {"result": "SUCCESS", "reason": None},
    "target": [
        {"id": f"00app{SMOKE[-6:]}", "type": "AppInstance",
         "alternateId": "Okta Dashboard", "displayName": "Okta Dashboard"},
    ],
    "request": {"ipChain": [{"ip": "192.0.2.45", "geographicalContext": {"country": "US"}}]},
    "securityContext": {"asNumber": 12345, "asOrg": "ExampleNet", "isp": "ExampleISP",
                        "domain": ".example.com", "isProxy": False},
    "transaction": {"id": f"txn-{SMOKE[-8:]}"},
    "debugContext": {"debugData": {"requestUri": "/api/login"}},
    "authenticationContext": {"authenticationStep": 0, "rootSessionId": "100sess"},
}

# POST one event to the HTTP collector
print(f"SMOKE_ID={SMOKE}")
print(f"POST to {COLLECTOR_URL}")
req = urllib.request.Request(
    COLLECTOR_URL,
    data=json.dumps([event]).encode(),
    method="POST",
    headers={
        "Content-Type": "application/json",
        "Authorization": AUTH_KEY,
    },
)
try:
    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as r:
        print(f"  status={r.status}")
        print(f"  body  ={r.read().decode()[:500]}")
except Exception as e:
    print(f"  ERROR: {e}")
    body = getattr(e, "read", lambda: b"")().decode("utf-8", "replace") if hasattr(e, "read") else ""
    print(f"  body  ={body[:500]}")

# Wait + query
print("\nwait 90s ...")
for i in range(3):
    time.sleep(30); print(f"  {(i+1)*30}s")

def xs_post(b, sid=None):
    h={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json',
       'Accept':'application/json, text/event-stream'}
    if sid: h['mcp-session-id']=sid
    r=urllib.request.Request(f'{XSIAM_BASE}/mcp',data=json.dumps(b).encode(),headers=h,method='POST')
    with urllib.request.urlopen(r,timeout=120) as resp:
        return resp.read().decode(), resp.headers

def sse(s):
    for ln in s.split('\n'):
        ln=ln.strip()
        if ln.startswith('data:'):
            try:
                f=json.loads(ln[5:].strip())
                if 'result' in f:
                    c=f['result'].get('content',[])
                    if c: return json.loads(c[0].get('text','{}'))
            except: pass
    return {}

_, hh = xs_post({'jsonrpc':'2.0','id':1,'method':'initialize',
                 'params':{'protocolVersion':'2024-11-05','capabilities':{},
                           'clientInfo':{'name':'q','version':'1.0'}}})
sid = hh.get('mcp-session-id') or hh.get('Mcp-Session-Id')
xs_post({'jsonrpc':'2.0','method':'notifications/initialized','params':{}}, sid)

def xql(q):
    body, _ = xs_post({'jsonrpc':'2.0','id':99,'method':'tools/call',
                       'params':{'name':'run_xql_query','arguments':{'request':{'query':q}}}}, sid)
    return sse(body)

# Q1: Look in okta_okta_raw + various other catchall datasets
for ds in ('okta_okta_raw', 'cisco_asa_raw', 'phantom_logs_raw', 'demisto_logs_raw'):
    # Filter on whatever JSON contains the smoke marker
    q = f'dataset = {ds} | filter to_string(uuid) contains "{SMOKE}" or to_string(_raw_log) contains "{SMOKE}" or to_string(displayMessage) contains "{SMOKE}" | limit 2'
    r = xql(q)
    reply = r.get('reply', {})
    n = reply.get('number_of_results', 0)
    status = reply.get('status')
    if status == 'SUCCESS' and n > 0:
        data = reply['results']['data']
        print(f'\n>>> FOUND in {ds}: {n} rows')
        for row in data:
            non_empty = {k: v for k, v in row.items() if v not in (None, "", "null") and not k.startswith("_")}
            for k, v in list(non_empty.items())[:8]:
                print(f'    {k}: {str(v)[:120]}')
    elif status == 'SUCCESS':
        print(f'  {ds}: 0 rows')
    else:
        err = reply.get('error', {})
        msg = list(err.values())[0] if err else '?'
        print(f'  {ds}: FAIL {msg}')

# Try datamodel on okta if any rows landed
q3 = (
    f'datamodel dataset = okta_okta_raw | '
    f'filter to_string(uuid) contains "{SMOKE}" | '
    f'fields xdm.event.id, xdm.event.original_event_type, xdm.event.outcome, '
    f'xdm.source.user.username, xdm.source.ipv4 | limit 3'
)
print(f"\n[datamodel okta_okta_raw]")
r3 = xql(q3)
reply3 = r3.get('reply', {})
if reply3.get('status') == 'SUCCESS':
    n = reply3.get('number_of_results', 0)
    print(f'  rows: {n}')
    for row in reply3.get('results', {}).get('data', []):
        non_null = {k: v for k, v in row.items() if v not in (None, "", "null")}
        print(f'  populated: {non_null}')
else:
    err = reply3.get('error', {})
    print(f'  FAIL: {err}')
